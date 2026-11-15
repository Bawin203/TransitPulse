import re
import math
import difflib
from datetime import datetime, time, timedelta
import speech_recognition as sr
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from itertools import islice

from my_graph import load_data, build_graph, get_critical_stations
from simulator import run_msa_simulation, allocate_bus_bridges

st.set_page_config(page_title="TransitPulse | Bengaluru & Regional Transit OS", page_icon="🚇", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    #MainMenu, footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}
    .block-container { padding-top: 1.3rem; padding-bottom: 2.5rem; max-width: 1380px; }
    .hero-title {
        font-size: 2.2rem; font-weight: 800; letter-spacing: -0.03em;
        background: linear-gradient(90deg, #ffffff 0%, #79c0ff 55%, #56d364 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.15rem;
    }
    .hero-sub { color: #8b949e; font-size: 0.94rem; margin-bottom: 1.1rem; }
    .planner-box {
        background: rgba(22, 27, 34, 0.78); backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px;
        padding: 16px 20px 12px 20px; margin-bottom: 1.1rem; box-shadow: 0 8px 24px rgba(0,0,0,0.28);
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #161b22, #1d2430); border: 1px solid #30363d;
        padding: 14px 18px; border-radius: 14px; box-shadow: 0 6px 18px rgba(0,0,0,0.22);
    }
    .alert-banner {
        padding: 13px 18px; border-radius: 12px;
        background: linear-gradient(90deg, rgba(248,81,73,0.18) 0%, rgba(61,20,24,0.72) 100%);
        border: 1px solid rgba(248,81,73,0.5); border-left: 5px solid #f85149; color: #ffdcd7; margin-bottom: 0.85rem; font-size: 0.94rem;
    }
    .official-notice {
        padding: 12px 18px; border-radius: 12px;
        background: linear-gradient(90deg, rgba(210,153,34,0.18) 0%, rgba(56,39,10,0.72) 100%);
        border: 1px solid rgba(210,153,34,0.5); border-left: 5px solid #d29922; color: #f8e3a1; margin-bottom: 0.85rem; font-size: 0.93rem;
    }
    .ok-banner {
        padding: 13px 18px; border-radius: 12px;
        background: linear-gradient(90deg, rgba(63,185,80,0.16) 0%, rgba(18,45,28,0.65) 100%);
        border: 1px solid rgba(63,185,80,0.45); border-left: 5px solid #3fb950; color: #aff5b4; margin-bottom: 1.1rem; font-size: 0.94rem;
    }
    .route-card {
        background: linear-gradient(145deg, #161b22 0%, #1b222c 100%); border: 1px solid #30363d;
        border-radius: 14px; padding: 15px 18px; margin-bottom: 14px;
    }
    .card-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 9px; }
    .pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; }
    .pill-rec { background: rgba(46,160,67,0.2); color: #56d364; border: 1px solid rgba(46,160,67,0.45); }
    .pill-alt { background: rgba(210,153,34,0.2); color: #e3b341; border: 1px solid rgba(210,153,34,0.45); }
    .pill-fare { background: rgba(163,113,247,0.18); color: #d2a8ff; border: 1px solid rgba(163,113,247,0.4); }
    .pill-crowd-hi { background: rgba(248,81,73,0.18); color: #ff7b72; border: 1px solid rgba(248,81,73,0.4); }
    .pill-crowd-ok { background: rgba(46,160,67,0.15); color: #7ee787; border: 1px solid rgba(46,160,67,0.35); }
    .time-row { font-size: 1.03rem; font-weight: 700; color: #f0f6fc; margin-bottom: 9px; }
    .leg-box { background: rgba(13,17,23,0.65); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 10px 14px; font-size: 0.88rem; color: #c9d1d9; line-height: 1.62; }
    .leg-step { margin-bottom: 4px; }
    div.stButton > button { white-space: nowrap; border-radius: 10px; padding: 0.45rem 0.9rem; font-weight: 600; border: 1px solid #30363d; background: #161b22; }
</style>
""", unsafe_allow_html=True)

LANG = {
    "English": {
        "speech_code": "en-IN", "portal_label": "Select Portal:",
        "commuter_portal": "Commuter Dashboard", "admin_portal": "Authority Control Room",
        "commuter_title": "TransitPulse Regional Transit OS",
        "commuter_sub": "Bengaluru Urban, Rural, Tumakuru, Kolar, Chikkaballapur & Ramanagara — Step-by-Step Detours, Anonymous Push Alerts & Voice AI",
        "admin_title": "TransitPulse: Authority Control Room",
        "admin_sub": "Unified Transit Operations (BMRCL · BMTC · KSRTC) — Incident Verification & Fleet Dispatch",
        "alert_active": "⚠️ Verified Disruption Alert: Operations suspended at {hubs}. All routes below have automatically adapted.",
        "alert_ok": "✅ All Hubs Operational: Normal Namma Metro, BMTC & KSRTC Regional services running smoothly.",
        "tab_route": "🧭 Route Planner & Live Map", "tab_report": "🚨 Report Breakdown", "tab_chat": "🤖 Transit AI (Text & Voice)",
        "orig_label": "Start Location / Landmark", "dest_label": "End Location / Landmark", "time_label": "Departure Time",
        "alt_header": "Step-by-Step Recommended & Alternative Paths", "map_header": "Focused Journey & Boarding Map",
        "chat_header": "Accent-Resilient Regional Transit Assistant",
        "chat_sub": "Speak naturally or type in English, Kannada, or Hindi (handles accents, broken words & landmarks like IKEA, Manyata, Tumkur).",
        "chat_placeholder": "Ask e.g. 'Go from IKEA to Whitefield', 'How much will it cost?', or 'Tumkur to Majestic'",
        "login_header": "🔐 Authority Login", "user_label": "Username", "pass_label": "Password",
        "login_btn": "Login", "logout_btn": "Logout",
    },
    "ಕನ್ನಡ (Kannada)": {
        "speech_code": "kn-IN", "portal_label": "ಪೋರ್ಟಲ್ ಆಯ್ಕೆಮಾಡಿ:",
        "commuter_portal": "ಪ್ರಯಾಣಿಕರ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "admin_portal": "ಪ್ರಾಧಿಕಾರ ನಿಯಂತ್ರಣ ಕೊಠಡಿ",
        "commuter_title": "ಟ್ರಾನ್ಸಿಟ್‌ಪಲ್ಸ್ ಪ್ರಾದೇಶಿಕ ಸಾರಿಗೆ ಪೋರ್ಟಲ್",
        "commuter_sub": "ಬೆಂಗಳೂರು ನಗರ, ಗ್ರಾಮಾಂತರ, ತುಮಕೂರು, ಕೋಲಾರ, ಚಿಕ್ಕಬಳ್ಳಾಪುರ ಮತ್ತು ರಾಮನಗರ — ಹಂತ-ಹಂತದ ಮಾರ್ಗ ಮತ್ತು ದರ ಮಾಹಿತಿ",
        "admin_title": "ಟ್ರಾನ್ಸಿಟ್‌ಪಲ್ಸ್: ಪ್ರಾಧಿಕಾರ ನಿಯಂತ್ರಣ ಕೊಠಡಿ",
        "admin_sub": "ಬಿಎಂಆರ್‌ಸಿಎಲ್ / ಬಿಎಂಟಿಸಿ / ಕೆಎಸ್‌ಆರ್‌ಟಿಸಿ ನೆಟ್‌ವರ್ಕ್ ನಿರ್ವಹಣೆ",
        "alert_active": "⚠️ ದೃಢೀಕೃತ ಸಂಚಾರ ವ್ಯತ್ಯಯ: {hubs} ನಿಲ್ದಾಣದಲ್ಲಿ ಸೇವೆ ಸ್ಥಗಿತಗೊಂಡಿದೆ. ಎಲ್ಲಾ ಮಾರ್ಗಗಳನ್ನು ನವೀಕರಿಸಲಾಗಿದೆ.",
        "alert_ok": "✅ ಎಲ್ಲಾ ನಿಲ್ದಾಣಗಳು ಕಾರ್ಯನಿರ್ವಹಿಸುತ್ತಿವೆ: ನಮ್ಮ ಮೆಟ್ರೋ, ಬಿಎಂಟಿಸಿ ಮತ್ತು ಕೆಎಸ್‌ಆರ್‌ಟಿಸಿ ಬಸ್‌ಗಳು ಸಾಮಾನ್ಯವಾಗಿ ಸಂಚರಿಸುತ್ತಿವೆ.",
        "tab_route": "🧭 ಮಾರ್ಗ ಯೋಜಕ ಮತ್ತು ನಕ್ಷೆ", "tab_report": "🚨 ತೊಂದರೆ ವರದಿ ಮಾಡಿ", "tab_chat": "🤖 ಸಾರಿಗೆ ಸಹಾಯಕ (ಧ್ವನಿ ಮತ್ತು ಪಠ್ಯ)",
        "orig_label": "ಪ್ರಾರಂಭದ ಸ್ಥಳ (Start)", "dest_label": "ತಲುಪುವ ಸ್ಥಳ (End)", "time_label": "ಹೊರಡುವ ಸಮಯ (Time)",
        "alt_header": "ಹಂತ-ಹಂತದ ಶಿಫಾರಸು ಮತ್ತು ಪರ್ಯಾಯ ಮಾರ್ಗಗಳು", "map_header": "ಮಾರ್ಗ ಮತ್ತು ಬದಲಾವಣೆ ನಕ್ಷೆ",
        "chat_header": "ಪ್ರಾದೇಶಿಕ ಸಾರಿಗೆ ಸಹಾಯಕ",
        "chat_sub": "ಮಾರ್ಗಗಳು, ಸ್ಥಳಗಳು (IKEA, Wonderla), ದರ ಅಥವಾ ಸಂಚಾರ ವ್ಯತ್ಯಯದ ಬಗ್ಗೆ ಕೇಳಿ.",
        "chat_placeholder": "ಉದಾ: 'IKEA ಇಂದ Whitefield ಗೆ ದಾರಿ', 'ಎಷ್ಟು ದರ ಆಗುತ್ತದೆ?'",
        "login_header": "🔐 ಪ್ರಾಧಿಕಾರ ಲಾಗಿನ್", "user_label": "ಬಳಕೆದಾರ ಹೆಸರು", "pass_label": "ಪಾಸ್‌ವರ್ಡ್",
        "login_btn": "ಲಾಗಿನ್", "logout_btn": "ಲಾಗ್ ಔಟ್",
    },
    "हिन्दी (Hindi)": {
        "speech_code": "hi-IN", "portal_label": "पोर्टल चुनें:",
        "commuter_portal": "यात्री डैशबोर्ड", "admin_portal": "प्राधिकरण नियंत्रण कक्ष",
        "commuter_title": "ट्रांज़िटपल्स क्षेत्रीय परिवहन पोर्टल",
        "commuter_sub": "बेंगलुरु शहरी, ग्रामीण, तुमकुरु, कोलार, चिक्कबल्लापुर और रामनगर — चरण-दर-चरण मार्ग और किराया",
        "admin_title": "ट्रांज़िटपल्स: प्राधिकरण नियंत्रण कक्ष",
        "admin_sub": "बीएमआरसीएल / बीएमटीसी / केएसआरटीसी नेटवर्क प्रबंधन और शटल ऑप्टिमाइज़र",
        "alert_active": "⚠️ सत्यापित सेवा व्यवधान: {hubs} पर संचालन बंद है। सभी मार्ग स्वचालित रूप से अपडेट कर दिए गए हैं।",
        "alert_ok": "✅ सभी स्टेशन चालू हैं: नम्मा मेट्रो, बीएमटीसी और केएसआरटीसी सेवाएं सामान्य रूप से चल रही हैं।",
        "tab_route": "🧭 रूट प्लानर और लाइव मैप", "tab_report": "🚨 खराबी की सूचना दें", "tab_chat": "🤖 परिवहन सहायक (आवाज़ और टेक्स्ट)",
        "orig_label": "प्रारंभिक स्थान / लैंडमार्क", "dest_label": "गंतव्य स्थान / लैंडमार्क", "time_label": "प्रस्थान समय (Time)",
        "alt_header": "चरण-दर-चरण सुझाए गए और वैकल्पिक मार्ग", "map_header": "रूट और ट्रांसफर मानचित्र",
        "chat_header": "क्षेत्रीय परिवहन सहायक",
        "chat_sub": "मार्ग, लैंडमार्क (IKEA, Manyata), किराया या देरी के बारे में हिंदी, कन्नड़ या अंग्रेजी में पूछें।",
        "chat_placeholder": "जैसे: 'IKEA से Whitefield कैसे जाएं?' या 'किराया कितना होगा?'",
        "login_header": "🔐 प्राधिकरण लॉगिन", "user_label": "यूज़रनेम", "pass_label": "पासवर्ड",
        "login_btn": "लॉगिन", "logout_btn": "लॉगआउट",
    }
}

ONBOARDING_T = {
    "English": {
        "tour_btn": "❓ Quick Tour",
        "welcome_h": "👋 Welcome to TransitPulse Regional Transit OS!",
        "welcome_p": "Before you begin planning your journey across Bengaluru and neighboring districts, <b>are you a new user?</b>",
        "yes_btn": "✨ Yes, I'm New (Show Feature Guide)",
        "no_btn": "⚡ No, Skip Intro & Open Dashboard",
        "guide_h": "### 🗺️ Quick Guide: Everything You Can Do on TransitPulse",
        "c1_t": "1. 🧭 Smart Landmark & 6-District Route Planner",
        "c1_b": "Search any Metro station, BMTC/KSRTC hub, or landmark (like <b>IKEA</b>, <b>Manyata Tech Park</b>, <b>Wonderla</b>, or <b>Tumakuru</b>), filter by Fastest/Cheapest/Step-Free, and swap with <b>⇄</b>.",
        "c2_t": "2. 🔔 Zero-Login Anonymous Push & Expandable 2G Map",
        "c2_b": "Enable <b>100% Anonymous Browser Push Alerts</b> (no login, no phone number, zero PII) for lock-screen disruption notices, or toggle <b>Rural 2G Mode</b> with an expandable schematic map.",
        "c3_t": "3. 🚨 Live Breakdown Reporting to Control Room",
        "c3_b": "Spotted a train fault, bus breakdown, or road blockage? Submit an alert in the <b>Report Breakdown</b> tab. Once verified by an authority, live banners and routes update automatically.",
        "c4_t": "4. 🤖 Accent-Resilient Voice & Text Transit AI",
        "c4_b": "Speak naturally or type in <b>English, Kannada, or Hindi</b>—our phonetic matcher understands broken words and accents to give step-by-step directions, buffers, and 2026 fares.",
        "launch_btn": "🚀 Got It — Launch Commuter Dashboard"
    },
    "ಕನ್ನಡ (Kannada)": {
        "tour_btn": "❓ ಮಾರ್ಗದರ್ಶಿ (Tour)",
        "welcome_h": "👋 ಟ್ರಾನ್ಸಿಟ್‌ಪಲ್ಸ್ ಪ್ರಾದೇಶಿಕ ಸಾರಿಗೆ ಪೋರ್ಟಲ್‌ಗೆ ಸುಸ್ವಾಗತ!",
        "welcome_p": "ಬೆಂಗಳೂರು ಮತ್ತು ನೆರೆಯ ಜಿಲ್ಲೆಗಳಲ್ಲಿ ನಿಮ್ಮ ಪ್ರಯಾಣವನ್ನು ಪ್ರಾರಂಭಿಸುವ ಮೊದಲು, <b>ನೀವು ಹೊಸ ಬಳಕೆದಾರರೇ?</b>",
        "yes_btn": "✨ ಹೌದು, ನಾನು ಹೊಸಬರು (ಮಾರ್ಗದರ್ಶಿ ತೋರಿಸಿ)",
        "no_btn": "⚡ ಇಲ್ಲ, ನೇರವಾಗಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ತೆರೆಯಿರಿ",
        "guide_h": "### 🗺️ ತ್ವರಿತ ಮಾರ್ಗದರ್ಶಿ: ಟ್ರಾನ್ಸಿಟ್‌ಪಲ್ಸ್ ವೈಶಿಷ್ಟ್ಯಗಳು",
        "c1_t": "1. 🧭 ಸ್ಮಾರ್ಟ್ ಲ್ಯಾಂಡ್‌ಮಾರ್ಕ್ ಮತ್ತು 6-ಜಿಲ್ಲೆಗಳ ಮಾರ್ಗ ಯೋಜಕ",
        "c1_b": "ಯಾವುದೇ ಮೆಟ್ರೋ ನಿಲ್ದಾಣ, ಬಸ್ ನಿಲ್ದಾಣ ಅಥವಾ ಪ್ರಮುಖ ಸ್ಥಳಗಳನ್ನು (<b>IKEA</b>, <b>Manyata Tech Park</b>, <b>Wonderla</b>, <b>ತುಮಕೂರು</b>) ಹುಡುಕಿ ಮತ್ತು <b>⇄</b> ಮೂಲಕ ದಿಕ್ಕನ್ನು ಬದಲಾಯಿಸಿ.",
        "c2_t": "2. 🔔 ಅನಾಮಧೇಯ ಪುಶ್ ಅಧಿಸೂಚನೆ ಮತ್ತು ಗ್ರಾಮೀಣ 2G ನಕ್ಷೆ",
        "c2_b": "ಲಾಗಿನ್ ಅಥವಾ ಫೋನ್ ಸಂಖ್ಯೆ ಇಲ್ಲದೆಯೇ <b>Anonymous Push Alerts</b> ಆನ್ ಮಾಡಿ, ಅಥವಾ ವಿಸ್ತರಿಸಬಹುದಾದ <b>Rural 2G Mode</b> ನಕ್ಷೆಯನ್ನು ಬಳಸಿ.",
        "c3_t": "3. 🚨 ನಿಯಂತ್ರಣ ಕೊಠಡಿಗೆ ನೇರ ತೊಂದರೆ ವರದಿ (Breakdown Report)",
        "c3_b": "ರೈಲು ಅಥವಾ ಬಸ್ ಸ್ಥಗಿತ ಅಥವಾ ರಸ್ತೆ ತಡೆಯನ್ನು ಗಮನಿಸಿದ್ದೀರಾ? <b>ತೊಂದರೆ ವರದಿ ಮಾಡಿ</b> ಟ್ಯಾಬ್‌ನಲ್ಲಿ ತಿಳಿಸಿ. ಪ್ರಾಧಿಕಾರ ದೃಢೀಕರಿಸಿದ ತಕ್ಷಣ ಎಲ್ಲಾ ಮಾರ್ಗಗಳು ನವೀಕರಣಗೊಳ್ಳುತ್ತವೆ.",
        "c4_t": "4. 🤖 ಕನ್ನಡ, ಇಂಗ್ಲಿಷ್ ಮತ್ತು ಹಿಂದಿ ಧ್ವನಿ ಮತ್ತು ಪಠ್ಯ ಸಹಾಯಕ",
        "c4_b": "ಮಾರ್ಗಗಳು, ದರದ ಅಂದಾಜು ಅಥವಾ ಜನದಟ್ಟಣೆಯ ಬಗ್ಗೆ <b>ಕನ್ನಡ, ಇಂಗ್ಲಿಷ್ ಅಥವಾ ಹಿಂದಿಯಲ್ಲಿ</b> ಟೈಪ್ ಮಾಡಿ ಅಥವಾ ಮಾತನಾಡಿ ಮಾಹಿತಿ ಪಡೆಯಿರಿ.",
        "launch_btn": "🚀 ಅರ್ಥವಾಯಿತು — ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ಪ್ರಾರಂಭಿಸಿ"
    },
    "हिन्दी (Hindi)": {
        "tour_btn": "❓ त्वरित गाइड (Tour)",
        "welcome_h": "👋 ट्रांज़िटपल्स क्षेत्रीय परिवहन पोर्टल में आपका स्वागत है!",
        "welcome_p": "बेंगलुरु और आसपास के जिलों में अपनी यात्रा की योजना बनाने से पहले, <b>क्या आप एक नए उपयोगकर्ता हैं?</b>",
        "yes_btn": "✨ हाँ, मैं नया हूँ (फीचर गाइड दिखाएं)",
        "no_btn": "⚡ नहीं, सीधे डैशबोर्ड खोलें (Skip)",
        "guide_h": "### 🗺️ त्वरित गाइड: ट्रांज़िटपल्स की सभी विशेषताएं",
        "c1_t": "1. 🧭 स्मार्ट लैंडमार्क और 6-जिला रूट प्लानर",
        "c1_b": "किसी भी मेट्रो स्टेशन, बस हब या प्रमुख स्थान (जैसे <b>IKEA</b>, <b>Manyata Tech Park</b>, <b>Wonderla</b>, या <b>तुमकुरु</b>) को खोजें और <b>⇄</b> से दिशा बदलें।",
        "c2_t": "2. 🔔 बिना लॉगिन पुश नोटिफिकेशन और ग्रामीण 2G मैप",
        "c2_b": "बिना फोन नंबर या अकाउंट के <b>Anonymous Browser Push Alerts</b> चालू करें, या ज़ूम होने वाले <b>Rural 2G Mode</b> मैप का उपयोग करें।",
        "c3_t": "3. 🚨 कंट्रोल रूम को लाइव खराबी की सूचना दें",
        "c3_b": "ट्रेन या बस खराब होने या सड़क जाम की सूचना <b>खराबी की सूचना दें</b> टैब में भेजें। अधिकारी द्वारा पुष्टि होते ही सभी मार्ग अपने आप अपडेट हो जाएंगे।",
        "c4_t": "4. 🤖 त्रिभाषी वॉयस और टेक्स्ट परिवहन सहायक",
        "c4_b": "रूट, किराया या भीड़भाड़ के बारे में <b>हिंदी, कन्नड़ या अंग्रेजी</b> में बोलकर या लिखकर तुरंत जानकारी प्राप्त करें।",
        "launch_btn": "🚀 समझ गया — यात्री डैशबोर्ड खोलें"
    }
}

AUTHORITY_MANUAL = {
    "English": {
        "title": "📘 Authority Control Room Standard Operating Manual (SOP)",
        "steps": [
            ("1. Verify Citizen Breakdown Reports", "When commuters report a train fault or road blockage, it appears in **Incident Verification** on Tab 1. Routes do **not** change until you click **✅ Confirm & Push**—preventing false alarms."),
            ("2. Broadcast Proactive Alerts & Anonymous Push", "Open **Publish Direct Proactive Alert**, select the station and reason, and click **Publish**. Subscribed commuters receive an instant lock-screen push alert with zero login."),
            ("3. Reopen Resolved Hubs", "Once track or road clearance is confirmed, click **✅ Reopen** next to the active incident banner to restore normal routing."),
            ("4. Optimize Metro Headway & Reserve Bus Fleet", "In Tab 2 (**Fleet, Manual & Audit**), lower the **BMRCL Metro Headway** or toggle **ORR Bus Priority Lanes**, then click **Execute Fleet Dispatch Orders** and export the CSV Shift Report.")
        ]
    },
    "ಕನ್ನಡ (Kannada)": {
        "title": "📘 ಪ್ರಾಧಿಕಾರ ನಿಯಂತ್ರಣ ಕೊಠಡಿ ಕಾರ್ಯಾಚರಣೆ ಕೈಪಿಡಿ (SOP)",
        "steps": [
            ("1. ಪ್ರಯಾಣಿಕರ ದೂರುಗಳನ್ನು ಪರಿಶೀಲಿಸಿ", "ಪ್ರಯಾಣಿಕರು ಕಳುಹಿಸುವ ತೊಂದರೆ ವರದಿಗಳು ಟ್ಯಾಬ್ 1 ರಲ್ಲಿ ಕಾಣಿಸುತ್ತವೆ. ನೀವು **✅ Confirm & Push** ಒತ್ತುವವರೆಗೆ ಮಾರ್ಗಗಳು ಬದಲಾಗುವುದಿಲ್ಲ."),
            ("2. ನೇರ ಎಚ್ಚರಿಕೆ ಮತ್ತು ಅನಾಮಧೇಯ ಪುಶ್", "ನಿಯಂತ್ರಣ ಕೊಠಡಿಯಿಂದಲೇ ನೇರವಾಗಿ ನಿಲ್ದಾಣದ ಸ್ಥಗಿತವನ್ನು ಪ್ರಕಟಿಸಬಹುದು. ಇದರಿಂದ ಪ್ರಯಾಣಿಕರಿಗೆ ತಕ್ಷಣವೇ ಅಧಿಸೂಚನೆ ತಲುಪುತ್ತದೆ."),
            ("3. ನಿಲ್ದಾಣವನ್ನು ಪುನಃ ತೆರೆಯಿರಿ", "ಸಮಸ್ಯೆ ಬಗೆಹರಿದ ನಂತರ **✅ Reopen** ಬಟನ್ ಒತ್ತಿ ಸಾಮಾನ್ಯ ಸಂಚಾರವನ್ನು ಪುನರಾರಂಭಿಸಿ."),
            ("4. ಮೆಟ್ರೋ ಹೆಡ್‌ವೇ ಮತ್ತು ಬಸ್ ನಿಯೋಜನೆ", "ಟ್ಯಾಬ್ 2 ರಲ್ಲಿ ಮೆಟ್ರೋ ಸಮಯದ ಅಂತರವನ್ನು ಕಡಿಮೆ ಮಾಡಿ, ಹೆಚ್ಚುವರಿ ಶಟಲ್ ಬಸ್‌ಗಳನ್ನು ನಿಯೋಜಿಸಿ ಮತ್ತು ಶಿಫ್ಟ್ ವರದಿಯನ್ನು (CSV) ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ.")
        ]
    },
    "हिन्दी (Hindi)": {
        "title": "📘 प्राधिकरण नियंत्रण कक्ष संचालन मैनुअल (SOP)",
        "steps": [
            ("1. यात्री रिपोर्टों की पुष्टि करें", "यात्रियों द्वारा भेजी गई खराबी की सूचनाएं टैब 1 में दिखाई देती हैं। जब तक आप **✅ Confirm & Push** पर क्लिक नहीं करते, तब तक मार्ग नहीं बदलते।"),
            ("2. सीधा प्रोएक्टिव अलर्ट और पुश नोटिफिकेशन", "कंट्रोल रूम से सीधे किसी भी स्टेशन के बंद होने की सूचना प्रकाशित करें। बिना लॉगिन के यात्रियों के डिवाइस पर तुरंत पुश अलर्ट पहुंच जाएगा।"),
            ("3. स्टेशन को पुनः चालू करें", "समस्या ठीक होने पर सक्रिय अलर्ट के पास **✅ Reopen** पर क्लिक करके सामान्य सेवा बहाल करें।"),
            ("4. मेट्रो हेडवे और बस फ्लीट ऑप्टिमाइज़ेशन", "टैब 2 में **Metro Headway** कम करें या **Bus Priority Lanes** चालू करें, डिपो से शटल बसें भेजें और शिफ्ट रिपोर्ट (CSV) डाउनलोड करें।")
        ]
    }
}

LANDMARKS = {
    "IKEA Nagasandra": {"hub": "NGS", "feeder_mode": "Walk (Direct Footbridge)", "mins": 3, "fare_min": 0, "fare_max": 0, "aliases": ["ikea", "ikae", "ikia", "ikea nagasandra", "ಐಕಿಯಾ", "आइकिया"]},
    "Manyata Tech Park": {"hub": "HBL", "feeder_mode": "BMTC Feeder / Auto", "mins": 8, "fare_min": 15, "fare_max": 35, "aliases": ["manyata", "manyata tech park", "manyatha", "ಮಾನ್ಯತಾ", "मान्यता"]},
    "Orion Mall / WTC": {"hub": "MLM", "feeder_mode": "Walk (Direct Footbridge)", "mins": 5, "fare_min": 0, "fare_max": 0, "aliases": ["orion", "orion mall", "world trade center", "wtc", "ಓರಿಯನ್"]},
    "Phoenix Marketcity / VR": {"hub": "MDP", "feeder_mode": "Walk (Direct Footbridge)", "mins": 4, "fare_min": 0, "fare_max": 0, "aliases": ["phoenix", "phoenix marketcity", "vr bengaluru", "ಫೀನಿಕ್ಸ್"]},
    "Wonderla Amusement Park": {"hub": "BDD", "feeder_mode": "KSRTC Feeder / Auto", "mins": 10, "fare_min": 20, "fare_max": 50, "aliases": ["wonderla", "wonder la", "ವಂಡರ್ಲಾ", "वंडरला"]},
    "Nandi Hills Top": {"hub": "NDH", "feeder_mode": "KSRTC Hill Shuttle / Taxi", "mins": 20, "fare_min": 35, "fare_max": 100, "aliases": ["nandi hills", "nandi betta", "ನಂದಿ ಬೆಟ್ಟ", "नंदी हिल्स"]},
    "IISc Bengaluru": {"hub": "YPR", "feeder_mode": "BMTC Feeder / Auto", "mins": 7, "fare_min": 15, "fare_max": 30, "aliases": ["iisc", "indian institute of science", "tata institute"]},
    "PES University (RR Campus)": {"hub": "BSK", "feeder_mode": "BMTC Feeder (401/500D)", "mins": 10, "fare_min": 15, "fare_max": 30, "aliases": ["pes", "pes university", "pesit"]},
    "RV College of Engineering": {"hub": "KNG", "feeder_mode": "Metro Feeder / Auto", "mins": 6, "fare_min": 10, "fare_max": 25, "aliases": ["rvce", "rv college"]},
    "Infosys / Wipro E-City": {"hub": "ELC", "feeder_mode": "E-City Feeder Shuttle", "mins": 5, "fare_min": 10, "fare_max": 20, "aliases": ["infosys", "wipro electronic city", "infosys campus"]},
    "Bagmane Tech Park": {"hub": "BYP", "feeder_mode": "BMTC Feeder / Auto", "mins": 7, "fare_min": 15, "fare_max": 30, "aliases": ["bagmane", "bagmane tech park"]},
    "Embassy TechVillage": {"hub": "BLD", "feeder_mode": "ORR Shuttle / Walk", "mins": 6, "fare_min": 10, "fare_max": 25, "aliases": ["embassy tech village", "etv", "cessna"]},
    "Forum / Nexus Mall Koramangala": {"hub": "KRMG", "feeder_mode": "Walk / Feeder", "mins": 5, "fare_min": 0, "fare_max": 15, "aliases": ["nexus mall", "forum mall"]},
    "Commercial Street": {"hub": "SHV", "feeder_mode": "Walk", "mins": 6, "fare_min": 0, "fare_max": 0, "aliases": ["commercial street", "ಕಮರ್ಷಿಯಲ್ ಸ್ಟ್ರೀಟ್"]},
    "Brigade Road / Church Street": {"hub": "MGR", "feeder_mode": "Walk", "mins": 3, "fare_min": 0, "fare_max": 0, "aliases": ["brigade road", "church street"]},
}

for k, v in [
    ("admin_user", "authority1"), ("admin_password", "12345"), ("admin_authenticated", False),
    ("closed_stations", []), ("demand_pct", 0), ("capacity_pct", 0), ("bus_freq_mult", 1.0),
    ("metro_headway_min", 5.0), ("bus_priority_lane", False), ("reserve_bus_budget", 25),
    ("audit_log", []), ("chat_history", []), ("bot_context", {"last_orig": None, "last_dest": None}),
    ("last_audio_id", None), ("dep_time", time(9, 0)), ("pending_reports", []),
    ("official_notices", []), ("orig_select", "LM::IKEA Nagasandra"), ("dest_select", "HUB::WFD"),
    ("onboarding_status", "ask"), ("push_subscribed", False), ("alert_scope", "My Selected Route"),
    ("last_pushed_notice_id", None), ("rural_mode", False), ("rural_map_expanded", False)
]:
    if k not in st.session_state:
        st.session_state[k] = v

def log_authority_action(action_title, detail_txt, impact_txt="Graph re-optimized"):
    st.session_state.audit_log.insert(0, {
        "Timestamp": datetime.now().strftime("%H:%M:%S"),
        "Operator": st.session_state.admin_user,
        "Action": action_title,
        "Details": detail_txt,
        "System Impact": impact_txt
    })

st.sidebar.markdown("## 🚇 TransitPulse")
selected_lang = st.sidebar.selectbox("🌐 Language / ಭಾಷೆ / भाषा", list(LANG.keys()), index=0)
T = LANG[selected_lang]

pending_cnt = len(st.session_state.pending_reports)
admin_label = f"{T['admin_portal']} ({pending_cnt} 🔔)" if pending_cnt > 0 else T["admin_portal"]
portal_choice = st.sidebar.radio(T["portal_label"], [T["commuter_portal"], admin_label], index=0)
is_admin_portal = portal_choice != T["commuter_portal"]
st.sidebar.divider()

nodes_raw, _, _ = load_data()
station_ids = list(nodes_raw["node_id"])
raw_name_map = dict(zip(nodes_raw["node_id"], nodes_raw["name"]))
def st_name(nid): return raw_name_map.get(nid, nid)

ALL_LOCATION_KEYS = [f"LM::{lm}" for lm in LANDMARKS.keys()] + [f"HUB::{nid}" for nid in station_ids]
def format_loc_key(key):
    if key.startswith("LM::"):
        lm = key.replace("LM::", "")
        return f"📌 {lm} (via {st_name(LANDMARKS[lm]['hub']).split('[')[0].strip()})"
    nid = key.replace("HUB::", "")
    return f"🚉 {st_name(nid)} ({nid})"

def resolve_location_key(key):
    if key.startswith("LM::"):
        lm = key.replace("LM::", "")
        info = LANDMARKS[lm]
        return info["hub"], lm, info
    nid = key.replace("HUB::", "")
    return nid, st_name(nid).split("[")[0].strip(), None

if is_admin_portal:
    if not st.session_state.admin_authenticated:
        st.sidebar.subheader(T["login_header"])
        u_in = st.sidebar.text_input(T["user_label"])
        p_in = st.sidebar.text_input(T["pass_label"], type="password")
        if st.sidebar.button(T["login_btn"], use_container_width=True):
            if u_in == st.session_state.admin_user and p_in == st.session_state.admin_password:
                st.session_state.admin_authenticated = True
                log_authority_action("Session Login", "Operator authenticated", "Access granted")
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials.")
    else:
        st.sidebar.success(f"Operator: **{st.session_state.admin_user}**")
        if st.sidebar.button(T["logout_btn"], use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()
        st.sidebar.subheader("Hub Outages & Stress")
        valid_defaults = [s for s in st.session_state.closed_stations if s in station_ids]
        new_closed = st.sidebar.multiselect("Suspended Stations:", options=station_ids, default=valid_defaults, format_func=lambda x: f"{x} — {st_name(x)}")
        if new_closed != st.session_state.closed_stations:
            st.session_state.closed_stations = new_closed
            log_authority_action("Hub Constraint Update", f"Closed: {', '.join(new_closed) if new_closed else 'None'}", "Routes updated")
        st.session_state.demand_pct = st.sidebar.slider("OD Passenger Demand (%)", -20, 30, st.session_state.demand_pct, step=5)
        st.session_state.capacity_pct = st.sidebar.slider("Overall Link Capacity (%)", -30, 30, st.session_state.capacity_pct, step=5)

def get_time_surge(t_obj):
    mins = t_obj.hour * 60 + t_obj.minute
    if (480 <= mins <= 630) or (1050 <= mins <= 1230): return 1.15, "Peak Rush Hour (+15% crowd)"
    elif 630 < mins < 1050: return 0.90, "Midday Moderate Flow"
    return 0.75, "Off-Peak Smooth Flow"

time_mult, time_badge = get_time_surge(st.session_state.dep_time)
demand_scale = (1.0 + (st.session_state.demand_pct / 100.0)) * (time_mult if not is_admin_portal else 1.0)
capacity_scale = 1.0 + (st.session_state.capacity_pct / 100.0)
closed_stations = st.session_state.closed_stations

nodes, edges, od = load_data(demand_scale=demand_scale, capacity_scale=capacity_scale)
edges.loc[edges["mode"] == "Metro", "capacity"] *= (5.0 / st.session_state.metro_headway_min)
edges.loc[edges["mode"].str.contains("Bus", na=False), "capacity"] *= st.session_state.bus_freq_mult

depots = pd.read_csv("depots.csv")
G_base = build_graph(nodes, edges)

def sanitize_bpr_times(graph, bus_priority=False):
    for u, v, d in graph.edges(data=True):
        base_t = float(d.get("base_time", d.get("time", 5.0)))
        cap = max(1.0, float(d.get("capacity", 100.0)))
        load = float(d.get("load", 0.0))
        vc = load / cap
        if str(d.get("mode", "")) == "Metro":
            d["time"] = round(base_t * (1.0 + min(0.35, 0.12 * (vc ** 2))), 1)
        else:
            alpha = 0.22 if bus_priority else 0.38
            max_mult = 1.55 if bus_priority else 2.15
            d["time"] = round(base_t * min(max_mult, 1.0 + alpha * (vc ** 2)), 1)
    return graph

G_normal, _, _, _ = run_msa_simulation(G_base, od, closed_stations=[])
G_normal = sanitize_bpr_times(G_normal, bus_priority=False)
G_sim, routed_paths, unserved_list, _ = run_msa_simulation(G_base, od, closed_stations=closed_stations)
G_sim = sanitize_bpr_times(G_sim, bus_priority=st.session_state.bus_priority_lane)
allocations, remaining_unserved = allocate_bus_bridges(G_base, G_sim, depots, unserved_list, closed_stations=closed_stations)

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2)**2
    return 2 * r * math.asin(math.sqrt(a))

def find_nearest_open_hub(graph, blocked_hub):
    if blocked_hub not in G_base.nodes: return None, 0.0
    b_node = G_base.nodes[blocked_hub]
    best_hub, best_km = None, 1e9
    for nid in graph.nodes():
        if nid != blocked_hub and nid not in closed_stations:
            n_data = G_base.nodes[nid]
            d_km = haversine_km(b_node["lat"], b_node["lon"], n_data["lat"], n_data["lon"])
            if d_km < best_km: best_km, best_hub = d_km, nid
    return best_hub, best_km

def build_resilient_routing_graph(sim_graph):
    G_detour = sim_graph.copy()
    arterial_bypasses = [
        ("ULS", "DML", "BMTC Bus", 7, 500), ("DML", "BYP", "BMTC Bus", 9, 500),
        ("BYP", "MDP", "BMTC Bus", 11, 550), ("MDP", "ITPL", "BMTC Bus", 12, 550),
        ("ITPL", "WFD", "BMTC Bus", 7, 550), ("MRT", "ITPL", "BMTC Bus", 14, 550),
        ("MRT", "WFD", "BMTC Bus", 18, 550), ("CUB", "SHV", "BMTC Bus", 5, 500),
        ("SRP", "MGD", "BMTC Bus", 8, 500), ("CKP", "MGD", "BMTC Bus", 7, 500),
    ]
    for u, v, mode, t_min, cap in arterial_bypasses:
        if u in G_detour.nodes and v in G_detour.nodes and u not in closed_stations and v not in closed_stations:
            if not G_detour.has_edge(u, v):
                G_detour.add_edge(u, v, mode=mode, base_time=t_min, time=float(t_min), load=cap * 0.45, capacity=float(cap))
            if not G_detour.has_edge(v, u):
                G_detour.add_edge(v, u, mode=mode, base_time=t_min, time=float(t_min), load=cap * 0.45, capacity=float(cap))

    for c_hub in closed_stations:
        if c_hub not in G_base.nodes: continue
        open_neighbors = [nbr for nbr in G_base.neighbors(c_hub) if nbr in G_detour.nodes and nbr not in closed_stations]
        for i in range(len(open_neighbors)):
            for j in range(i + 1, len(open_neighbors)):
                n1, n2 = open_neighbors[i], open_neighbors[j]
                t1 = G_base[n1][c_hub].get("base_time", 5) if G_base.has_edge(n1, c_hub) else 5
                t2 = G_base[c_hub][n2].get("base_time", 5) if G_base.has_edge(c_hub, n2) else 5
                bt = round((t1 + t2) * 1.35 + 4.0, 1)
                if not G_detour.has_edge(n1, n2):
                    G_detour.add_edge(n1, n2, mode="BMTC Emergency Shuttle", base_time=bt, time=bt, load=320.0, capacity=600.0)
                if not G_detour.has_edge(n2, n1):
                    G_detour.add_edge(n2, n1, mode="BMTC Emergency Shuttle", base_time=bt, time=bt, load=320.0, capacity=600.0)
    return G_detour

def build_step_by_step_route(graph, path, start_feeder=None, end_feeder=None, start_label="", end_label="", use_pass=False):
    raw_legs, total_time, fare_min, fare_max = [], 0.0, 0, 0
    if start_feeder:
        hub_clean = st_name(start_feeder["hub"]).split("[")[0].strip()
        raw_legs.append({"mode": start_feeder["feeder_mode"], "from": start_label, "to": hub_clean, "stops": [start_label, hub_clean], "mins": start_feeder["mins"], "f_min": start_feeder["fare_min"], "f_max": start_feeder["fare_max"], "is_feeder": True})
        total_time += start_feeder["mins"]; fare_min += start_feeder["fare_min"]; fare_max += start_feeder["fare_max"]

    if len(path) >= 2:
        curr_mode, curr_stops, curr_mins = graph[path[0]][path[1]]["mode"], [path[0], path[1]], graph[path[0]][path[1]]["time"]
        for i in range(1, len(path) - 1):
            u, v = path[i], path[i + 1]
            m, t = graph[u][v]["mode"], graph[u][v]["time"]
            if m == curr_mode: curr_stops.append(v); curr_mins += t
            else:
                raw_legs.append({"mode": curr_mode, "stops_ids": curr_stops, "mins": round(curr_mins, 1)})
                curr_mode, curr_stops, curr_mins = m, [u, v], t
        raw_legs.append({"mode": curr_mode, "stops_ids": curr_stops, "mins": round(curr_mins, 1)})

    total_metro_hops = sum(len(lg["stops_ids"]) - 1 for lg in raw_legs if "stops_ids" in lg and lg["mode"] == "Metro")
    unified_metro_fare = min(90, max(10, 10 + total_metro_hops * 5)) if total_metro_hops > 0 else 0
    if use_pass and unified_metro_fare > 0: unified_metro_fare = max(10, int(round(unified_metro_fare * 0.90)))

    metro_fare_assigned = 0
    metro_legs_indices = [idx for idx, lg in enumerate(raw_legs) if "stops_ids" in lg and lg["mode"] == "Metro"]
    formatted_legs = []
    for idx, lg in enumerate(raw_legs):
        if lg.get("is_feeder"): formatted_legs.append(lg); continue
        hops, m = len(lg["stops_ids"]) - 1, lg["mode"]
        if m == "Metro":
            if idx == metro_legs_indices[-1]: l_min = max(0, unified_metro_fare - metro_fare_assigned)
            else:
                l_min = int(round(unified_metro_fare * (hops / max(1, total_metro_hops))))
                metro_fare_assigned += l_min
            l_max = l_min
        elif "Bus" in m or "Shuttle" in m:
            if "KIA" in lg["stops_ids"]: l_min, l_max = (210, 260) if use_pass else (240, 290)
            else:
                base_bmtc = min(45, max(10, 8 + hops * 4))
                ac_bmtc = min(65, base_bmtc + 15)
                l_min = int(base_bmtc * 0.85) if use_pass else base_bmtc
                l_max = int(ac_bmtc * 0.90) if use_pass else ac_bmtc
        else:
            base_reg = min(130, max(30, 25 + hops * 18))
            max_reg = min(190, base_reg + 35)
            l_min = int(base_reg * 0.90) if use_pass else base_reg
            l_max = int(max_reg * 0.90) if use_pass else max_reg

        fare_min += l_min; fare_max += l_max; total_time += lg["mins"]
        stop_names = [st_name(s).split("[")[0].strip() for s in lg["stops_ids"]]
        formatted_legs.append({"mode": m, "from": stop_names[0], "to": stop_names[-1], "stops": stop_names, "mins": lg["mins"], "f_min": l_min, "f_max": l_max})

    if end_feeder:
        hub_clean = st_name(end_feeder["hub"]).split("[")[0].strip()
        formatted_legs.append({"mode": end_feeder["feeder_mode"], "from": hub_clean, "to": end_label, "stops": [hub_clean, end_label], "mins": end_feeder["mins"], "f_min": end_feeder["fare_min"], "f_max": end_feeder["fare_max"]})
        total_time += end_feeder["mins"]; fare_min += end_feeder["fare_min"]; fare_max += end_feeder["fare_max"]
    return formatted_legs, round(total_time, 1), fare_min, fare_max

def get_alternative_paths(graph, source, target, k=3, priority="⚡ Fastest"):
    G_detour = build_resilient_routing_graph(graph)
    eff_source, eff_target = source, target
    prefix_bridge, suffix_bridge = None, None
    if source in closed_stations:
        alt_s, km_s = find_nearest_open_hub(G_detour, source)
        if not alt_s: return []
        eff_source = alt_s; prefix_bridge = (source, alt_s, max(6, int(round(km_s * 3.5 + 4))))
    if target in closed_stations:
        alt_t, km_t = find_nearest_open_hub(G_detour, target)
        if not alt_t: return []
        eff_target = alt_t; suffix_bridge = (alt_t, target, max(6, int(round(km_t * 3.5 + 4))))
    if prefix_bridge and not G_detour.has_edge(prefix_bridge[0], prefix_bridge[1]):
        G_detour.add_edge(prefix_bridge[0], prefix_bridge[1], mode="BMTC Emergency Shuttle", base_time=prefix_bridge[2], time=float(prefix_bridge[2]), load=250.0, capacity=600.0)
    if suffix_bridge and not G_detour.has_edge(suffix_bridge[0], suffix_bridge[1]):
        G_detour.add_edge(suffix_bridge[0], suffix_bridge[1], mode="BMTC Emergency Shuttle", base_time=suffix_bridge[2], time=float(suffix_bridge[2]), load=250.0, capacity=600.0)

    try:
        raw_paths = list(islice(nx.shortest_simple_paths(G_detour, eff_source, eff_target, weight="time"), k + 4))
        scored = []
        for p in raw_paths:
            full_p = ([prefix_bridge[0]] + p if prefix_bridge else p) + ([suffix_bridge[1]] if suffix_bridge else [])
            raw_t = nx.path_weight(G_detour, full_p, weight="time")
            transfers = sum(1 for i in range(1, len(full_p) - 1) if G_detour[full_p[i-1]][full_p[i]]["mode"] != G_detour[full_p[i]][full_p[i+1]]["mode"])
            max_vc = max((G_detour[full_p[i]][full_p[i+1]]["load"] / G_detour[full_p[i]][full_p[i+1]]["capacity"]) * 100 for i in range(len(full_p)-1)) if len(full_p) > 1 else 0
            modes = list(dict.fromkeys(G_detour[full_p[i]][full_p[i+1]]["mode"] for i in range(len(full_p)-1)))
            _, _, f_min, _ = build_step_by_step_route(G_detour, full_p)
            non_metro_hops = sum(1 for i in range(len(full_p)-1) if G_detour[full_p[i]][full_p[i+1]]["mode"] != "Metro")

            if priority == "💳 Cheapest (₹)": score = (f_min * 10) + raw_t
            elif priority == "🟢 Least Crowded": score = (max_vc * 2.5) + raw_t
            elif priority == "♿ Step-Free / Well-Lit": score = (transfers * 15) + (non_metro_hops * 8) + raw_t
            else: score = raw_t + (transfers * 4.5)
            scored.append((score, {"path": full_p, "graph": G_detour, "time": round(raw_t, 1), "max_vc": round(max_vc, 0), "modes": " + ".join(modes), "transfers": transfers}))
        scored.sort(key=lambda x: x[0])
        results = []
        for idx, (_, item) in enumerate(scored[:k]):
            item["rank"] = idx + 1; results.append(item)
        return results
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []

def render_focused_map(height=490, active_route=None, orig_label="", dest_label="", show_all_bg=False):
    fig = go.Figure()
    if show_all_bg or not active_route:
        for u, v, data in G_sim.edges(data=True):
            u_n, v_n = G_base.nodes[u], G_base.nodes[v]
            vc_pct = (data["load"] / data["capacity"]) * 100
            if active_route:
                c, w = "rgba(150, 165, 180, 0.25)", 1.5
            else:
                c = "#f85149" if vc_pct > 100 else ("#a371f7" if data["mode"] == "Metro" else ("#58a6ff" if "Regional" in data["mode"] else "#3fb950"))
                w = 4 if vc_pct > 100 else 2
            fig.add_trace(go.Scattermap(
                lat=[u_n["lat"], v_n["lat"]], lon=[u_n["lon"], v_n["lon"]],
                mode="lines", line=dict(width=w, color=c),
                hoverinfo="text", text=f"{st_name(u)} → {st_name(v)} ({data['mode']}): {vc_pct:.0f}% load",
                showlegend=False
            ))

    if closed_stations:
        c_lats = [G_base.nodes[c]["lat"] for c in closed_stations if c in G_base.nodes]
        c_lons = [G_base.nodes[c]["lon"] for c in closed_stations if c in G_base.nodes]
        c_txts = [f"🚫 BLOCKED: {st_name(c)}" for c in closed_stations if c in G_base.nodes]
        fig.add_trace(go.Scattermap(
            lat=c_lats, lon=c_lons, mode="markers+text",
            marker=dict(size=14, color="#f85149"),
            text=["🚫" for _ in c_lats], textposition="top center",
            hovertext=c_txts, hoverinfo="text", name="Blocked Hub"
        ))

    center_lat, center_lon, zoom_lvl = 12.9850, 77.6000, 10.5
    if active_route and len(active_route["path"]) >= 2:
        r_graph = active_route.get("graph", G_sim)
        path = active_route["path"]
        p_nodes = [G_base.nodes[n] for n in path if n in G_base.nodes]
        center_lat = sum(n["lat"] for n in p_nodes) / len(p_nodes)
        center_lon = sum(n["lon"] for n in p_nodes) / len(p_nodes)
        span = max(max(n["lat"] for n in p_nodes) - min(n["lat"] for n in p_nodes), max(n["lon"] for n in p_nodes) - min(n["lon"] for n in p_nodes))
        zoom_lvl = 12.2 if span < 0.12 else (11.0 if span < 0.28 else 9.5)

        legend_shown = set()
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            u_n, v_n = G_base.nodes[u], G_base.nodes[v]
            mode = r_graph[u][v]["mode"] if r_graph.has_edge(u, v) else "Bus"
            t_min = r_graph[u][v]["time"] if r_graph.has_edge(u, v) else 5

            if mode == "Metro": seg_color, label_name = "#a371f7", "🟣 Namma Metro"
            elif "Shuttle" in mode: seg_color, label_name = "#d29922", "🟡 Emergency Shuttle"
            elif "Regional" in mode: seg_color, label_name = "#58a6ff", "🔵 Regional KSRTC/Rail"
            else: seg_color, label_name = "#3fb950", "🟢 BMTC Bus"

            show_leg = label_name not in legend_shown
            legend_shown.add(label_name)
            fig.add_trace(go.Scattermap(
                lat=[u_n["lat"], v_n["lat"]], lon=[u_n["lon"], v_n["lon"]],
                mode="lines", line=dict(width=6, color=seg_color),
                name=label_name, showlegend=show_leg,
                hoverinfo="text", text=f"{label_name}: {st_name(u).split('[')[0].strip()} ➔ {st_name(v).split('[')[0].strip()} ({t_min} min)"
            ))

        tr_lats, tr_lons, tr_hover, tr_labels = [], [], [], []
        for i in range(1, len(path) - 1):
            prev_m = r_graph[path[i-1]][path[i]]["mode"]
            next_m = r_graph[path[i]][path[i+1]]["mode"]
            if prev_m != next_m:
                hn = G_base.nodes[path[i]]
                hclean = st_name(path[i]).split("[")[0].strip()
                tr_lats.append(hn["lat"]); tr_lons.append(hn["lon"])
                tr_labels.append(f"🔄 {hclean}")
                tr_hover.append(f"🔄 TRANSFER AT {hclean}: Get off {prev_m} ➔ Board {next_m}")
        if tr_lats:
            fig.add_trace(go.Scattermap(
                lat=tr_lats, lon=tr_lons, mode="markers+text",
                marker=dict(size=14, color="#ffa657"),
                text=tr_labels, textposition="top center", textfont=dict(color="#ffffff", size=11),
                hovertext=tr_hover, hoverinfo="text", name="🟠 Transfer (Get Off/On)"
            ))

        s_n = G_base.nodes[path[0]]
        s_mode = r_graph[path[0]][path[1]]["mode"]
        s_title = orig_label or st_name(path[0]).split("[")[0].strip()
        fig.add_trace(go.Scattermap(
            lat=[s_n["lat"]], lon=[s_n["lon"]], mode="markers+text",
            marker=dict(size=16, color="#2ea043"),
            text=[f"🟢 START: {s_title}"], textposition="bottom center", textfont=dict(color="#7ee787", size=12),
            hovertext=[f"🟢 START: {s_title} — Board {s_mode}"], hoverinfo="text", name="🟢 Start"
        ))

        e_n = G_base.nodes[path[-1]]
        e_mode = r_graph[path[-2]][path[-1]]["mode"]
        e_title = dest_label or st_name(path[-1]).split("[")[0].strip()
        fig.add_trace(go.Scattermap(
            lat=[e_n["lat"]], lon=[e_n["lon"]], mode="markers+text",
            marker=dict(size=16, color="#f85149"),
            text=[f"🔴 END: {e_title}"], textposition="top center", textfont=dict(color="#ff7b72", size=12),
            hovertext=[f"🔴 END: {e_title} — Get off {e_mode}"], hoverinfo="text", name="🔴 End"
        ))

    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=zoom_lvl),
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01, bgcolor="rgba(13,17,23,0.82)", font=dict(color="white", size=11))
    )
    st.plotly_chart(fig, use_container_width=True)

def render_offline_schematic_map(expanded=False):
    h = 540 if expanded else 320
    fig = px.scatter(
        nodes, x="lon", y="lat", text="node_id" if expanded else None, hover_name="name",
        color=nodes["node_id"].apply(lambda x: "Closed" if x in closed_stations else "Operational"),
        color_discrete_map={"Closed": "#f85149", "Operational": "#58a6ff"}
    )
    fig.update_traces(marker=dict(size=11 if expanded else 8, line=dict(width=1.2, color="white")), textposition="top center", textfont=dict(size=9))
    for u, v, data in G_sim.edges(data=True):
        u_n, v_n = G_sim.nodes[u], G_sim.nodes[v]
        vc_pct = (data["load"] / data["capacity"]) * 100
        fig.add_scatter(x=[u_n["lon"], v_n["lon"]], y=[u_n["lat"], v_n["lat"]], mode="lines",
                        line=dict(color="#f85149" if vc_pct > 100 else "#2ea043", width=3 if vc_pct > 100 else 1.5),
                        hoverinfo="skip", showlegend=False)
    fig.update_layout(height=h, margin=dict(l=5, r=5, t=5, b=5), plot_bgcolor="#0d1117", paper_bgcolor="#0d1117", xaxis_title="", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

TRANSIT_DOMAIN_KEYWORDS = [
    "route", "way", "reach", "go", "travel", "from", "to", "bus", "metro", "train", "ksrtc", "bmtc",
    "fare", "price", "cost", "ticket", "rupee", "rs", "crowd", "busy", "traffic", "buffer", "delay",
    "time", "alternative", "other", "option", "second", "step", "breakdown", "closed", "open", "status",
    "shuttle", "station", "stop", "airport", "nandi", "ikea", "ikae", "ikia", "manyata", "wonderla", "orion",
    "phoenix", "infosys", "wipro", "pes", "iisc", "rvce", "bagmane", "embassy", "forum", "nexus",
    "ಮಾರ್ಗ", "ಬಸ್", "ಮೆಟ್ರೋ", "ದರ", "ಜನದಟ್ಟಣೆ", "ನಿಲ್ದಾಣ", "मार्ग", "बस", "मेट्रो", "किराया", "भीड़", "स्टेशन"
]

def consonant_skeleton(s):
    s = re.sub(r"[^a-z]", "", s.lower())
    s = re.sub(r"(.)\1+", r"\1", s)
    return re.sub(r"[aeiouh]", "", s)

ENTITY_ALIASES = {f"LM::{lm}": info["aliases"] for lm, info in LANDMARKS.items()}
for nid in station_ids:
    clean_base = st_name(nid).split("[")[0].strip().lower()
    words = [nid.lower(), clean_base, clean_base.replace(" ", "")] + [p.strip() for p in re.split(r"[/()\-]", clean_base) if len(p.strip()) >= 3]
    ENTITY_ALIASES[f"HUB::{nid}"] = list(dict.fromkeys(words))

for k, v in {
    "HUB::TMK": ["tumkur", "tumakuru", "tumkuru", "ತುಮಕೂರು", "तुमकुरु"], "HUB::KLR": ["kolar", "ಕೋಲಾರ", "कोलार"],
    "HUB::CKB": ["chikkaballapur", "chikballapur", "ಚಿಕ್ಕಬಳ್ಳಾಪುರ", "चिक्कबल्लापुर"], "HUB::RMN": ["ramanagara", "ramnagar", "ರಾಮನಗರ", "रामनगर"],
    "HUB::CNP": ["channapatna", "ಚನ್ನಪಟ್ಟಣ", "चन्नपटना"], "HUB::BDD": ["bidadi", "ಬಿಡದಿ", "बिदादी"],
    "HUB::NLM": ["nelamangala", "ನೆಲಮಂಗಲ", "नेलमंगला"], "HUB::DBP": ["doddaballapura", "doddaballapur", "ದೊಡ್ಡಬಳ್ಳಾಪುರ"],
    "HUB::MAJ": ["majestic", "ಮೆಜೆಸ್ಟಿಕ್", "मैजेस्टिक"], "HUB::YPR": ["yeshwanthpur", "yeshwantpur", "yeshwanth pur", "ಯಶವಂತಪುರ", "यशवंतपुर"],
    "HUB::WFD": ["whitefield", "white field", "kadugodi", "ವೈಟ್‌ಫೀಲ್ಡ್", "व्हाइटफील्ड"], "HUB::IND": ["indiranagar", "indranagar", "indira nagar", "ಇಂದಿರಾನಗರ", "इंदिरानगर"],
    "HUB::ELC": ["electronic city", "e city", "ಎಲೆಕ್ಟ್ರಾನಿಕ್ ಸಿಟಿ"], "HUB::KIA": ["airport", "kial", "kempegowda airport", "ವಿಮಾನ ನಿಲ್ದಾಣ", "हवाई अड्डा"],
    "HUB::HBL": ["hebbal", "ಹೆಬ್ಬಾಳ", "हेब्बाल"], "HUB::MGR": ["mg road", "ಎಂ.ಜಿ. ರಸ್ತೆ", "एम.जी. रोड"],
    "HUB::KRMG": ["koramangala", "kormangala", "ಕೋರಮಂಗಲ", "कोरमंगला"],
}.items():
    if k in ENTITY_ALIASES: ENTITY_ALIASES[k].extend(v)

SKELETON_MAP = {}
for ek, aliases in ENTITY_ALIASES.items():
    for a in aliases:
        sk = consonant_skeleton(a)
        if len(sk) >= 3: SKELETON_MAP.setdefault(sk, ek)

STOP_FILLERS = {"want", "wanna", "gonna", "from", "reach", "travel", "going", "need", "please", "tell", "show", "route", "much", "cost", "fare", "price", "take", "metro", "bus", "train", "station", "stop"}

def extract_entities(query):
    q_clean = re.sub(r"[^\w\s\u0C80-\u0CFF\u0900-\u097F]", " ", query.lower())
    q_norm = q_clean.replace("white field", "whitefield").replace("indira nagar", "indiranagar").replace("yeshwanth pur", "yeshwanthpur").replace("electronic city", "electroniccity")
    tokens, hits = q_norm.split(), []
    for ent_key, aliases in ENTITY_ALIASES.items():
        for alias in aliases:
            a_norm = alias.replace(" ", "") if len(alias) > 5 else alias
            if len(a_norm) <= 3:
                if re.search(rf"\b{re.escape(a_norm)}\b", q_norm): hits.append((q_norm.find(a_norm), ent_key)); break
            else:
                pos = q_norm.find(a_norm)
                if pos != -1: hits.append((pos, ent_key)); break
    already = {h[1] for h in hits}
    ngrams = [(i, tokens[i]) for i in range(len(tokens)) if tokens[i] not in STOP_FILLERS and len(tokens[i]) >= 3]
    ngrams += [(i, tokens[i] + tokens[i+1]) for i in range(len(tokens)-1) if tokens[i] not in STOP_FILLERS and tokens[i+1] not in STOP_FILLERS]
    for idx_pos, gram in ngrams:
        sk = consonant_skeleton(gram)
        if len(sk) >= 3 and sk in SKELETON_MAP and SKELETON_MAP[sk] not in already:
            hits.append((idx_pos * 10, SKELETON_MAP[sk])); already.add(SKELETON_MAP[sk]); continue
        if len(gram) < 4: continue
        for ent_key, aliases in ENTITY_ALIASES.items():
            if ent_key in already: continue
            if difflib.get_close_matches(gram, [a.replace(" ", "") for a in aliases if len(a) >= 4], n=1, cutoff=0.72):
                hits.append((idx_pos * 10, ent_key)); already.add(ent_key); break
    hits.sort(key=lambda x: x[0])
    ordered = []
    for _, ek in hits:
        if ek not in ordered: ordered.append(ek)
    if len(ordered) >= 2:
        return (ordered[1], ordered[0]) if re.search(r"\b(to|reach|towards)\b.*\bfrom\b", q_clean) else (ordered[0], ordered[1])
    return (ordered[0], None) if len(ordered) == 1 else (None, None)

def generate_guarded_bot_reply(query, lang):
    q = query.lower().strip()
    e1, e2 = extract_entities(q)
    if not (e1 or e2 or any(kw in q for kw in TRANSIT_DOMAIN_KEYWORDS) or any(g in q for g in ["hi", "hello", "help", "namaskara", "namaste"])):
        return "🛡️ **Out-of-Scope Guardrail:** I am specialized strictly for **Bengaluru & Regional Transit (Metro, BMTC, KSRTC & Suburban Rail)**."
    if e1 and e2:
        st.session_state.bot_context["last_orig"], st.session_state.bot_context["last_dest"] = e1, e2
    ctx_orig, ctx_dest = st.session_state.bot_context.get("last_orig"), st.session_state.bot_context.get("last_dest")
    wants_fare = any(w in q for w in ["fare", "price", "cost", "ticket", "rupee", "much", "ದರ", "किराया"])
    wants_alt = any(w in q for w in ["alternative", "backup", "other", "second", "option", "cheaper", "ಪರ್ಯಾಯ", "वैकल्पिक"])
    wants_steps = any(w in q for w in ["step", "how", "leg", "transfer", "change", "ಹಂತ", "कैसे"])
    if not (e1 and e2) and (wants_fare or wants_alt or wants_steps) and ctx_orig and ctx_dest:
        e1, e2 = ctx_orig, ctx_dest

    if e1 and e2:
        h1, name1, f1 = resolve_location_key(e1)
        h2, name2, f2 = resolve_location_key(e2)
        alts = get_alternative_paths(G_sim, h1, h2, k=3)
        if not alts: return f"❌ No surviving transit link found between **{name1}** and **{name2}**."
        chosen_idx = 1 if (wants_alt and len(alts) > 1) else 0
        chosen = alts[chosen_idx]
        norm_time = nx.path_weight(G_normal, nx.shortest_path(G_normal, h1, h2, weight="time"), weight="time")
        buffer_mins = max(0.0, chosen["time"] - norm_time)
        legs, tot_mins, f_min, f_max = build_step_by_step_route(chosen.get("graph", G_sim), chosen["path"], start_feeder=f1, end_feeder=f2, start_label=name1, end_label=name2)
        fare_str = f"₹{f_min}" if f_min == f_max else f"₹{f_min} – ₹{f_max}"
        if wants_fare and not (e1 != ctx_orig and e2 != ctx_dest):
            return f"💳 **Estimated Fare ({name1} ➔ {name2}):** **{fare_str}**\nTotal time: **~{tot_mins} min** (includes **+{buffer_mins:.1f} min** buffer)."
        step_lines = [
            f"**{idx}. [{lg['mode']}]** **{lg['from']}** ➔ **{lg['to']}**"
            + (f" *(via {' → '.join(lg['stops'][1:-1])})*" if len(lg["stops"]) > 2 else "")
            + f" — *{lg['mins']} min* ({'₹' + str(lg['f_min']) if lg['f_min'] == lg['f_max'] else '₹' + str(lg['f_min']) + '–₹' + str(lg['f_max'])})"
            for idx, lg in enumerate(legs, 1)
        ]
        title_tag = "🟡 Alternative Route #2" if chosen_idx == 1 else "✅ Recommended Route"
        return f"*Interpreted: **{name1} ➔ {name2}***\n\n{title_tag}: **{name1} ➔ {name2}**\n⏱️ **Total Time:** {tot_mins} min *(+{buffer_mins:.1f} min buffer)* &nbsp;|&nbsp; 💳 **Est. Fare:** {fare_str}\n\n" + "\n".join(step_lines)

    closed_txt = ", ".join(st_name(s).split("[")[0].strip() for s in closed_stations) if closed_stations else "None"
    return f"🚇 **TransitPulse Regional AI** (**{len(station_ids)} Hubs** across 6 Districts) | Active Closures: **{closed_txt}**\nAsk e.g. *'IKEA to Whitefield'*, *'Tumakuru to Indiranagar'*, or *'How much will that cost?'*"

# ==============================================================================
# PORTAL 1: COMMUTER DASHBOARD
# ==============================================================================
if not is_admin_portal:
    OB = ONBOARDING_T[selected_lang]
    top_h1, top_h2 = st.columns([5.2, 1])
    with top_h1:
        st.markdown(f"<div class='hero-title'>{T['commuter_title']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='hero-sub'>{T['commuter_sub']}</div>", unsafe_allow_html=True)
    with top_h2:
        if st.session_state.onboarding_status == "done":
            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
            if st.button(OB["tour_btn"], use_container_width=True):
                st.session_state.onboarding_status = "tour"; st.rerun()

    if st.session_state.onboarding_status == "ask":
        st.markdown(f"<div class='planner-box' style='border: 1px solid rgba(88, 166, 255, 0.45); padding: 26px 28px;'><h3 style='margin-top:0; color:#f0f6fc;'>{OB['welcome_h']}</h3><p style='color:#c9d1d9; font-size:1.02rem; margin-bottom:16px;'>{OB['welcome_p']}</p></div>", unsafe_allow_html=True)
        ob_c1, ob_c2, _ = st.columns([1.3, 1.35, 1.35], gap="medium")
        if ob_c1.button(OB["yes_btn"], use_container_width=True):
            st.session_state.onboarding_status = "tour"; st.rerun()
        if ob_c2.button(OB["no_btn"], use_container_width=True):
            st.session_state.onboarding_status = "done"; st.rerun()
        st.stop()

    elif st.session_state.onboarding_status == "tour":
        st.markdown(OB["guide_h"])
        g1, g2 = st.columns(2, gap="medium")
        with g1:
            st.markdown(f"<div class='route-card'><div class='time-row'>{OB['c1_t']}</div><div class='leg-box'>{OB['c1_b']}</div></div><div class='route-card'><div class='time-row'>{OB['c2_t']}</div><div class='leg-box'>{OB['c2_b']}</div></div>", unsafe_allow_html=True)
        with g2:
            st.markdown(f"<div class='route-card'><div class='time-row'>{OB['c3_t']}</div><div class='leg-box'>{OB['c3_b']}</div></div><div class='route-card'><div class='time-row'>{OB['c4_t']}</div><div class='leg-box'>{OB['c4_b']}</div></div>", unsafe_allow_html=True)
        if st.button(OB["launch_btn"], use_container_width=True):
            st.session_state.onboarding_status = "done"; st.rerun()
        st.stop()

    if st.session_state.official_notices:
        latest_notice = st.session_state.official_notices[-1]
        notice_uid = f"{latest_notice['station']}_{latest_notice['time']}_{latest_notice['reason']}"
        orig_h, _, _ = resolve_location_key(st.session_state.orig_select)
        dest_h, _, _ = resolve_location_key(st.session_state.dest_select)
        matches_scope = (st.session_state.alert_scope == "All 6 Districts" or latest_notice["station"] in (orig_h, dest_h))

        if st.session_state.push_subscribed and matches_scope and st.session_state.last_pushed_notice_id != notice_uid:
            st.session_state.last_pushed_notice_id = notice_uid
            push_title = f"🚨 TransitPulse Alert: {st_name(latest_notice['station']).split('[')[0].strip()}"
            push_body = f"{latest_notice['reason']} — {latest_notice['details']}"
            st.toast(f"📲 Anonymous Push Sent: {push_title}", icon="🔔")
            components.html(f"""<script>if ("Notification" in window) {{ if (Notification.permission === "granted") {{ new Notification({repr(push_title)}, {{ body: {repr(push_body)} }}); }} else if (Notification.permission !== "denied") {{ Notification.requestPermission().then(p => {{ if (p === "granted") new Notification({repr(push_title)}, {{ body: {repr(push_body)} }}); }}); }} }}</script>""", height=0)

    b_col1, b_col2 = st.columns([2.35, 1.05], gap="medium")
    with b_col1:
        if closed_stations:
            st.markdown(f"<div class='alert-banner'>{T['alert_active'].format(hubs=', '.join(st_name(s).split('[')[0].strip() for s in closed_stations))}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='ok-banner'>{T['alert_ok']}</div>", unsafe_allow_html=True)
        for notice in reversed(st.session_state.official_notices[-2:]):
            st.markdown(f"<div class='official-notice'>📢 <b>OFFICIAL NOTICE ({notice['time']}):</b> <b>{st_name(notice['station'])}</b> — {notice['reason']}. <i>{notice['details']}</i></div>", unsafe_allow_html=True)

    with b_col2:
        with st.container(border=True):
            sub_on = st.toggle("🔔 Anonymous Browser Push", value=st.session_state.push_subscribed)
            if sub_on != st.session_state.push_subscribed:
                st.session_state.push_subscribed = sub_on
                if sub_on:
                    components.html("<script>if ('Notification' in window && Notification.permission !== 'granted') { Notification.requestPermission(); }</script>", height=0)
                st.rerun()
            if st.session_state.push_subscribed:
                st.session_state.alert_scope = st.radio("Watchlist:", ["My Selected Route", "All 6 Districts"], horizontal=True, label_visibility="collapsed")
                st.caption("🔒 No Login · Zero PII · Device-Only Token")
            else:
                st.caption("🔒 100% Anonymous · No Phone/Login Needed")

    c_tab1, c_tab2, c_tab3 = st.tabs([T["tab_route"], T["tab_report"], T["tab_chat"]])

    with c_tab1:
        st.markdown("<div class='planner-box'>", unsafe_allow_html=True)
        p1, p_swap, p2, p3, p4 = st.columns([1.35, 0.26, 1.35, 0.85, 0.95], gap="small")
        with p1:
            orig_key = st.selectbox(f"📍 {T['orig_label']}", ALL_LOCATION_KEYS, index=ALL_LOCATION_KEYS.index(st.session_state.orig_select) if st.session_state.orig_select in ALL_LOCATION_KEYS else 0, format_func=format_loc_key)
            st.session_state.orig_select = orig_key
        with p_swap:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("⇄", help="Swap Start & End Locations", use_container_width=True):
                st.session_state.orig_select, st.session_state.dest_select = st.session_state.dest_select, st.session_state.orig_select
                st.rerun()
        with p2:
            dest_key = st.selectbox(f"🏁 {T['dest_label']}", ALL_LOCATION_KEYS, index=ALL_LOCATION_KEYS.index(st.session_state.dest_select) if st.session_state.dest_select in ALL_LOCATION_KEYS else 1, format_func=format_loc_key)
            st.session_state.dest_select = dest_key
        with p3:
            st.session_state.dep_time = st.time_input(f"🕒 {T['time_label']}", value=st.session_state.dep_time, step=900)
        with p4:
            route_priority = st.selectbox("🎯 Priority", ["⚡ Fastest", "💳 Cheapest (₹)", "🟢 Least Crowded", "♿ Step-Free / Well-Lit"])

        opt_r1, opt_r2, opt_r3 = st.columns([1.1, 1.1, 1.8])
        with opt_r1: use_pass = st.toggle("💳 Smart Card / Pass Discount", value=False)
        with opt_r2: st.session_state.rural_mode = st.toggle("📶 Rural 2G / Low-Data Mode", value=st.session_state.rural_mode)
        with opt_r3: st.caption(f"Window: **{time_badge}** • **{st.session_state.dep_time.strftime('%I:%M %p')}** • **6 Districts**")
        st.markdown("</div>", unsafe_allow_html=True)

        orig_hub, orig_label, orig_feeder = resolve_location_key(orig_key)
        dest_hub, dest_label, dest_feeder = resolve_location_key(dest_key)
        alt_paths = get_alternative_paths(G_sim, orig_hub, dest_hub, k=3, priority=route_priority) if orig_key != dest_key else []

        if st.session_state.rural_mode and st.session_state.rural_map_expanded:
            mh1, mh2 = st.columns([4, 1])
            mh1.subheader("📡 Rural 2G Schematic Graph (Expanded)")
            if mh2.button("🗕 Minimize Map", use_container_width=True):
                st.session_state.rural_map_expanded = False; st.rerun()
            render_offline_schematic_map(expanded=True)

        left_p, right_p = st.columns([1.22, 1.08], gap="large")
        with left_p:
            st.subheader(T["alt_header"])
            if orig_key == dest_key:
                st.info("Start and end locations are identical.")
            elif not alt_paths:
                st.error("No surviving rail/bus path exists. Use deployed emergency shuttle bridges.")
            else:
                if orig_hub in closed_stations or dest_hub in closed_stations:
                    st.warning("⚠️ Your selected start/end hub is suspended. Automatically bridging via nearest open station:")
                norm_time = nx.path_weight(G_normal, nx.shortest_path(G_normal, orig_hub, dest_hub, weight="time"), weight="time")
                dep_dt = datetime.combine(datetime.today(), st.session_state.dep_time)
                for item in alt_paths:
                    buffer_mins = max(0.0, item["time"] - norm_time)
                    legs, tot_mins, f_min, f_max = build_step_by_step_route(item.get("graph", G_sim), item["path"], start_feeder=orig_feeder, end_feeder=dest_feeder, start_label=orig_label, end_label=dest_label, use_pass=use_pass)
                    arr_dt = dep_dt + timedelta(minutes=tot_mins)
                    pill_cls = "pill-rec" if item["rank"] == 1 else "pill-alt"
                    badge_txt = f"★ {route_priority.split(' ')[1].upper()}" if item["rank"] == 1 else f"OPTION #{item['rank']}"
                    crowd_cls = "pill-crowd-hi" if item["max_vc"] > 100 else "pill-crowd-ok"
                    crowd_txt = f"High Buffer ({int(item['max_vc'])}% load)" if item["max_vc"] > 100 else f"Smooth ({int(item['max_vc'])}% load)"
                    total_fare_badge = f"₹{f_min}" if f_min == f_max else f"₹{f_min} – ₹{f_max}"
                    legs_block = "".join([
                        f"<div class='leg-step'><b>{i}.</b> Take <b>{lg['mode']}</b> from <b>{lg['from']}</b> ➔ <b>{lg['to']}</b>"
                        + (f" <span style='color:#8b949e;'>(via {' → '.join(lg['stops'][1:-1])})</span>" if len(lg["stops"]) > 2 else "")
                        + f" <span style='color:#79c0ff;'>({lg['mins']} min • {'₹' + str(lg['f_min']) if lg['f_min'] == lg['f_max'] else '₹' + str(lg['f_min']) + '–₹' + str(lg['f_max'])})</span></div>"
                        for i, lg in enumerate(legs, 1)
                    ])
                    st.markdown(f"""
                    <div class="route-card">
                        <div class="card-header">
                            <div><span class="pill {pill_cls}">{badge_txt}</span> <span class="pill pill-fare">💳 Est. {total_fare_badge}</span></div>
                            <span class="pill {crowd_cls}">{crowd_txt}</span>
                        </div>
                        <div class="time-row">⏱️ {tot_mins} min <span style="color:#e3b341; font-size:0.88rem; font-weight:600;">(includes +{buffer_mins:.1f} min buffer)</span> &nbsp;•&nbsp; <span style="color:#79c0ff; font-size:0.92rem;">{dep_dt.strftime('%I:%M %p')} ➔ {arr_dt.strftime('%I:%M %p')}</span></div>
                        <div class="leg-box">{legs_block}</div>
                    </div>
                    """, unsafe_allow_html=True)

        with right_p:
            if st.session_state.rural_mode:
                if not st.session_state.rural_map_expanded:
                    rm1, rm2 = st.columns([2.2, 1])
                    rm1.subheader("📡 Rural 2G Schematic Map")
                    if rm2.button("🔍 Expand Map", use_container_width=True):
                        st.session_state.rural_map_expanded = True; st.rerun()
                    render_offline_schematic_map(expanded=False)
                st.subheader("📄 Lightweight Plain-Text Detour")
                if alt_paths:
                    r0 = alt_paths[0]
                    compact_msg = f"TransitPulse: {orig_hub}->{dest_hub} via {'->'.join(r0['path'][:4])} ({r0['time']}m). Closed:{','.join(closed_stations) or 'None'}."
                else:
                    compact_msg = f"TransitPulse Alert: {orig_hub}->{dest_hub} disrupted."
                st.code(compact_msg, language="text")
                pocket_csv = pd.DataFrame([{"From": st_name(u), "To": st_name(v), "Mode": d["mode"], "Time (min)": d["time"]} for u, v, d in G_sim.edges(data=True)]).to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Offline Detour Guide (CSV)", data=pocket_csv, file_name="transitpulse_offline_guide.csv", mime="text/csv", use_container_width=True)
            else:
                mh_c1, mh_c2 = st.columns([2.2, 1])
                mh_c1.subheader(T["map_header"])
                show_bg = mh_c2.toggle("Show Full Network", value=False)
                st.caption("🟢 **Start** · 🔴 **End** · 🟠 **Get Off/Board Transfer** &nbsp;|&nbsp; 🟣 **Metro** · 🟢 **BMTC Bus** · 🟡 **Emergency Shuttle**")
                render_focused_map(height=490, active_route=alt_paths[0] if alt_paths else None, orig_label=orig_label, dest_label=dest_label, show_all_bg=show_bg)

    with c_tab2:
        st.subheader("🚨 Notify Authorities of a Breakdown or Disruption")
        st.info("Network routes will adapt immediately once an authority verifies your report.")
        r_col1, r_col2 = st.columns([1.15, 1])
        with r_col1:
            with st.form("breakdown_report_form", clear_on_submit=True):
                rep_station = st.selectbox("Affected Station / Regional Hub:", options=station_ids, format_func=lambda x: f"{st_name(x)} ({x})")
                rep_type = st.selectbox("Incident Category:", ["Metro Train Breakdown / Track Fault", "Signal / Power Failure", "BMTC / KSRTC Bus Breakdown / Accident", "Highway Blockade / Waterlogging"])
                rep_desc = st.text_input("Additional Details (Optional):", placeholder="e.g., Bus breakdown near Hebbal flyover...")
                if st.form_submit_button("📤 Send Alert to Authority Control Room", use_container_width=True):
                    rep = {"id": f"RPT-{len(st.session_state.pending_reports) + 101}", "time": datetime.now().strftime("%I:%M %p"), "station": rep_station, "type": rep_type, "details": rep_desc.strip() or "Reported on-site."}
                    st.session_state.pending_reports.append(rep)
                    st.success(f"✅ Report **{rep['id']}** sent for **{st_name(rep_station)}**. Awaiting authority confirmation.")
        with r_col2:
            st.markdown("#### ⏳ Reports Awaiting Authority Verification")
            if st.session_state.pending_reports:
                for p_rep in reversed(st.session_state.pending_reports):
                    st.warning(f"**{p_rep['id']}** ({p_rep['time']}) — **{st_name(p_rep['station'])}**: {p_rep['type']}")
            else:
                st.caption("No unverified reports in queue.")

    with c_tab3:
        st.subheader(T["chat_header"])
        st.caption(T["chat_sub"])
        b1, b2, b3, b4 = st.columns(4, gap="small")
        quick_prompt = None
        if b1.button("📌 IKEA ➔ Whitefield", use_container_width=True): quick_prompt = "I want to go from IKEA to Whitefield"
        if b2.button("🚌 Tumkur ➔ Indiranagar", use_container_width=True): quick_prompt = "Route from Tumakuru to Indiranagar"
        if b3.button("💳 Est. Fare & Alt", use_container_width=True): quick_prompt = "How much will that cost and show alternative route"
        if b4.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []; st.session_state.last_audio_id = None; st.rerun()

        audio_clip = st.audio_input(f"🎤 Record Voice Query ({T['speech_code']})")
        voice_text = None
        if audio_clip is not None:
            audio_id = f"{audio_clip.name}_{audio_clip.size}"
            if st.session_state.get("last_audio_id") != audio_id:
                st.session_state.last_audio_id = audio_id
                recognizer = sr.Recognizer()
                try:
                    with sr.AudioFile(audio_clip) as source: audio_data = recognizer.record(source)
                    voice_text = recognizer.recognize_google(audio_data, language=T["speech_code"])
                except Exception as e:
                    st.warning(f"Voice transcription notice ({e}). Use text input below.")

        chat_box = st.container(height=360)
        with chat_box:
            if not st.session_state.chat_history:
                with st.chat_message("assistant"): st.markdown(generate_guarded_bot_reply("help", selected_lang))
            for role, msg in st.session_state.chat_history:
                with st.chat_message(role): st.markdown(msg)

        typed_q = st.chat_input(T["chat_placeholder"])
        final_q = voice_text or quick_prompt or typed_q
        if final_q:
            st.session_state.chat_history.append(("user", f"🎤 {voice_text}" if voice_text else final_q))
            st.session_state.chat_history.append(("assistant", generate_guarded_bot_reply(final_q, selected_lang)))
            st.rerun()

# ==============================================================================
# PORTAL 2: ULTRA-CLEAN 2-TAB AUTHORITY CONTROL ROOM + TRILINGUAL MANUAL
# ==============================================================================
else:
    if not st.session_state.admin_authenticated:
        st.markdown("<div class='hero-title'>🔒 Authority Control Room Access</div>", unsafe_allow_html=True)
        st.info("Enter your operator credentials in the left sidebar to access the control room.")
        st.stop()

    st.markdown(f"<div class='hero-title'>{T['admin_title']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hero-sub'>{T['admin_sub']}</div>", unsafe_allow_html=True)

    active_edges = [(u, v, d) for u, v, d in G_sim.edges(data=True) if d["load"] > 0]
    overloaded_edges = [(u, v, d) for u, v, d in active_edges if d["load"] > d["capacity"]]
    avg_load_pct = round(sum((d["load"] / d["capacity"]) * 100 for _, _, d in active_edges) / max(1, len(active_edges)), 1)
    total_buses_dispatched = sum(a["Buses Dispatched"] for a in allocations)
    resilience_score = max(12, min(100, int(100 - (len(overloaded_edges) * 3.5) - (len(closed_stations) * 8) - max(0, (avg_load_pct - 75) * 0.4))))
    co2_saved_tons = round(((sum(d["load"] for _, _, d in active_edges) / 3.5) * 11.5 * 0.14) / 1000.0, 1)

    k1, k2, k3 = st.columns(3)
    k1.metric("Network Resilience", f"{resilience_score}/100", delta="Optimal" if resilience_score >= 80 else "Stressed", delta_color="normal" if resilience_score >= 80 else "inverse")
    k2.metric("Overloaded Links", f"{len(overloaded_edges)} corridors", delta=f"{len(st.session_state.pending_reports)} pending citizen alerts", delta_color="inverse" if overloaded_edges else "off")
    k3.metric("Reserve Fleet & CO₂ Impact", f"{total_buses_dispatched} / {st.session_state.reserve_bus_budget} buses", delta=f"🌱 {co2_saved_tons}t CO₂ saved")

    tab1_label = f"🗺️ Live Command & Alerts ({len(st.session_state.pending_reports)})" if st.session_state.pending_reports else "🗺️ Live Command & Alerts"
    a_tab1, a_tab2 = st.tabs([tab1_label, "🚌 Fleet, Manual & Audit"])

    with a_tab1:
        col_m, col_r = st.columns([1.25, 1], gap="large")
        with col_m:
            st.subheader("Geospatial 6-District Stress Map")
            render_focused_map(height=470, show_all_bg=True)

            with st.expander("⚡ Quick Crisis Simulation Triggers"):
                c1, c2, c3 = st.columns(3, gap="small")
                if c1.button("🚇 Majestic Fault", use_container_width=True):
                    if "MAJ" not in st.session_state.closed_stations: st.session_state.closed_stations.append("MAJ")
                    st.session_state.official_notices.append({"time": datetime.now().strftime("%I:%M %p"), "station": "MAJ", "reason": "Simulated Interchange Outage", "details": "Shuttle bridges active."})
                    log_authority_action("Crisis Trigger: MAJ Outage", "Suspended MAJ", "Rerouted commuters")
                    st.rerun()
                if c2.button("🌧️ ORR Waterlogging", use_container_width=True):
                    st.session_state.demand_pct, st.session_state.capacity_pct = 20, -20
                    log_authority_action("Crisis Trigger: ORR Rain", "Demand +20%, Cap -20%", "Bottlenecks flagged")
                    st.rerun()
                if c3.button("🟢 Reset All", use_container_width=True):
                    st.session_state.closed_stations, st.session_state.demand_pct, st.session_state.capacity_pct = [], 0, 0
                    st.session_state.bus_freq_mult, st.session_state.metro_headway_min, st.session_state.bus_priority_lane = 1.0, 5.0, False
                    log_authority_action("System Reset", "Restored normal ops", "Nominal")
                    st.rerun()

        with col_r:
            st.subheader("🚨 Incident Verification & Alerts")
            if st.session_state.pending_reports:
                for idx, rep in enumerate(list(st.session_state.pending_reports)):
                    with st.container(border=True):
                        st.markdown(f"**{rep['id']}** ({rep['time']}) — 📍 **{st_name(rep['station'])}**")
                        st.caption(f"{rep['type']} • {rep['details']}")
                        b1, b2 = st.columns(2)
                        if b1.button(f"✅ Confirm & Push ({rep['station']})", key=f"conf_{rep['id']}", use_container_width=True):
                            if rep["station"] not in st.session_state.closed_stations: st.session_state.closed_stations.append(rep["station"])
                            st.session_state.official_notices.append({"time": datetime.now().strftime("%I:%M %p"), "station": rep["station"], "reason": f"Confirmed: {rep['type']}", "details": f"{rep['details']} Detours active."})
                            log_authority_action("Verified Report", f"{rep['id']} at {rep['station']}", "Push alert & rerouting active")
                            st.session_state.pending_reports.pop(idx); st.rerun()
                        if b2.button("❌ Dismiss", key=f"dism_{rep['id']}", use_container_width=True):
                            st.session_state.pending_reports.pop(idx); st.rerun()
            else:
                st.success("✅ Zero unverified citizen reports in queue.")

            if closed_stations:
                st.markdown("#### 🔒 Active Suspended Hubs")
                for cs in list(closed_stations):
                    rc1, rc2 = st.columns([2.2, 1])
                    rc1.warning(f"**{st_name(cs)} ({cs})** — Suspended")
                    if rc2.button("✅ Reopen", key=f"reopen_{cs}", use_container_width=True):
                        st.session_state.closed_stations.remove(cs)
                        log_authority_action("Reopened Hub", f"Restored service at {cs}", "Normal routing resumed")
                        st.rerun()

            with st.expander("📢 Publish Direct Proactive Alert (Anonymous Push)", expanded=not bool(st.session_state.pending_reports)):
                with st.form("proactive_broadcast_form", clear_on_submit=True):
                    b_station = st.selectbox("Target Hub:", options=station_ids, format_func=lambda x: f"{st_name(x)} ({x})")
                    b_reason = st.selectbox("Reason:", ["Scheduled Track / Signal Maintenance", "Emergency Rolling Stock Fault", "Police / VIP Diversion", "Severe Weather Closure"])
                    b_msg = st.text_input("Advisory Message:", placeholder="e.g., Services halted 45 mins; take feeder shuttles.")
                    apply_c = st.checkbox("Suspend hub & auto-reroute commuters", value=True)
                    if st.form_submit_button("🚨 Publish & Send Push Alert", use_container_width=True):
                        if apply_c and b_station not in st.session_state.closed_stations: st.session_state.closed_stations.append(b_station)
                        st.session_state.official_notices.append({"time": datetime.now().strftime("%I:%M %p"), "station": b_station, "reason": b_reason, "details": b_msg.strip() or "All commuter routes updated."})
                        log_authority_action("Published Alert", f"{b_station}: {b_reason}", "Anonymous push sent")
                        st.rerun()

    with a_tab2:
        man = AUTHORITY_MANUAL[selected_lang]
        with st.expander(man["title"], expanded=True):
            for step_t, step_b in man["steps"]:
                st.markdown(f"**{step_t}:** {step_b}")

        st.divider()
        p_col1, p_col2, p_col3 = st.columns(3, gap="medium")
        with p_col1:
            new_hw = st.slider("🚇 BMRCL Metro Headway (min)", 3.0, 10.0, float(st.session_state.metro_headway_min), 0.5)
            if new_hw != st.session_state.metro_headway_min: st.session_state.metro_headway_min = new_hw; st.rerun()
        with p_col2:
            new_bud = st.slider("🏭 Reserve Depot Fleet Pool", 5, 60, st.session_state.reserve_bus_budget, 5)
            if new_bud != st.session_state.reserve_bus_budget: st.session_state.reserve_bus_budget = new_bud; st.rerun()
        with p_col3:
            st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
            new_prio = st.toggle("🚌 Dedicated ORR Bus Priority Lanes", value=st.session_state.bus_priority_lane)
            if new_prio != st.session_state.bus_priority_lane: st.session_state.bus_priority_lane = new_prio; st.rerun()

        f_left, f_right = st.columns([1.2, 1], gap="large")
        with f_left:
            st.subheader("📋 Optimal Depot Dispatch Plan")
            dispatch_plan = []
            budget_left = st.session_state.reserve_bus_budget
            for a in allocations:
                assigned = min(budget_left, int(a["Buses Dispatched"]))
                if assigned > 0:
                    budget_left -= assigned
                    dispatch_plan.append({"Depot": a["Depot"], "Target": f"{st_name(a['Target Hub']).split('[')[0].strip()} (Bridge)", "Buses": assigned, "Impact": "Restores rail link"})
            depot_names = list(depots["depot_name"]) if "depot_name" in depots.columns else ["Yeshwanthpur Depot", "KR Puram Depot", "Shantinagar TTMC", "Hebbal Depot"]
            for idx, (u, v, d) in enumerate(sorted(overloaded_edges, key=lambda x: x[2]["load"] - x[2]["capacity"], reverse=True)):
                if budget_left <= 0: break
                assigned = min(budget_left, max(1, min(6, int(round((d["load"] - d["capacity"]) / 120)))))
                budget_left -= assigned
                dispatch_plan.append({"Depot": depot_names[idx % len(depot_names)], "Target": f"{st_name(u).split('[')[0].strip()} → {st_name(v).split('[')[0].strip()}", "Buses": assigned, "Impact": f"Load {int((d['load']/d['capacity'])*100)}% ➔ {int((d['load']/(d['capacity']+assigned*95))*100)}%"})
            if dispatch_plan:
                st.dataframe(pd.DataFrame(dispatch_plan), use_container_width=True, height=240, hide_index=True)
                if st.button("✅ Execute Fleet Dispatch Orders", use_container_width=True):
                    log_authority_action("Executed Dispatch", f"Deployed {sum(r['Buses'] for r in dispatch_plan)} buses", "Corridor load reduced")
                    st.success("Dispatch orders sent to Depots!")
            else:
                st.success("✅ Zero reserve buses needed — all corridors within capacity.")

        with f_right:
            st.subheader("📜 Operator Audit Trail & Shift Export")
            if st.session_state.audit_log:
                df_audit = pd.DataFrame(st.session_state.audit_log)
                st.dataframe(df_audit, use_container_width=True, height=240, hide_index=True)
                st.download_button("📄 Download Shift Report (CSV)", data=df_audit.to_csv(index=False).encode("utf-8"), file_name="authority_shift_report.csv", mime="text/csv", use_container_width=True)
            else:
                st.info("No operator actions recorded yet in this session.")
