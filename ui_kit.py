# -*- coding: utf-8 -*-
"""ui_kit.py - Giao diện hiện đại cho AI Running Coach Pro (Be Vietnam Pro, đổ bóng mềm, hiệu ứng nút bấm cao cấp)."""
import json
from datetime import datetime, timedelta
from html import escape

import streamlit as st
import streamlit.components.v1 as components

DAY_ORDER = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
DAY_SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
TYPE_COLORS = {
    "Easy Run": "#16A34A", "Tempo": "#D97706", "Interval": "#DB2777", "Long Run": "#7C3AED",
    "Rest": "#94A3B8", "Walk": "#2563EB", "Threshold": "#DC2626",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap');

:root {
    --ink: #241A1A; --ink-2: #6B5C5C; --ink-3: #9A8A8A;
    --line: #F1DFDD; --line-2: #E5CDCA;
    --accent: #D92D20; --accent-l: #F04438; --accent-d: #B42318;
    --accent-soft: #FDECEA; --accent-wash: #FFF6F5;
    --surface: #FFFFFF;
    --ok: #16A34A; --warn: #D97706; --info: #2563EB;
    --shadow-sm: 0 2px 10px -4px rgba(180, 35, 24, .07), 0 1px 2px rgba(42, 31, 31, .04);
    --shadow-md: 0 10px 24px -10px rgba(180, 35, 24, .16), 0 2px 6px -2px rgba(42, 31, 31, .06);
    --ease-spring: cubic-bezier(.22, 1, .36, 1);
}
@keyframes rc-grow { from { width: 0; } }
@keyframes rc-in   { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* ---------- Thanh cuộn mảnh ---------- */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(180, 35, 24, .18); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: rgba(180, 35, 24, .34); }

/* ---------- Nền & khung trang ---------- */
.stApp {
    color: var(--ink);
    background:
        radial-gradient(960px 440px at 0% 0%, #FFE2DF 0%, transparent 62%),
        radial-gradient(780px 400px at 100% 0%, #FFEFE8 0%, transparent 58%),
        #FFFAF9 !important;
    background-attachment: fixed !important;
}
.stApp :where(p, span, div, label, li, a, h1, h2, h3, h4, h5, h6, input, textarea, button, th, td, summary):not([data-testid="stIconMaterial"]):not([class*="material" i]) {
    font-family: 'Be Vietnam Pro', -apple-system, 'Segoe UI', sans-serif;
}
header[data-testid="stHeader"] { background: transparent !important; height: 2.4rem !important; }
.block-container, [data-testid="stMainBlockContainer"] {
    padding: 2.5rem 1.5rem 1.2rem !important; max-width: 1320px !important;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"] { gap: .65rem; }
hr { margin: .55rem 0 !important; border-color: var(--line) !important; }

/* ---------- Chữ & số thẳng hàng ---------- */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { letter-spacing: -.015em; color: var(--ink); }
[data-testid="stHeading"] h2, [data-testid="stHeading"] h3 { font-size: 14.5px !important; font-weight: 800 !important; padding: .1rem 0 !important; margin: 0 !important; }
[data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
[data-testid="stMarkdownContainer"] p { font-size: 13.5px; line-height: 1.52; margin-bottom: .3rem; }
[data-testid="stMarkdownContainer"] p:last-child { margin-bottom: 0; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: 12px !important; color: var(--ink-2) !important; }
[data-testid="stWidgetLabel"] p, label[data-testid="stWidgetLabel"] { font-size: 12px !important; font-weight: 700 !important; color: var(--ink-2) !important; }
[data-testid="stWidgetLabel"] { margin-bottom: 2px !important; min-height: 0 !important; }
.rc-kpi .val, .rc-day .k, .rc-today .prog b, .shoe-header, [data-testid="stMetricValue"] {
    font-variant-numeric: tabular-nums;
}

/* ---------- Ô nhập liệu ---------- */
.stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea { font-size: 13px !important; color: var(--ink) !important; }
.stTextInput div[data-baseweb="input"], .stNumberInput div[data-baseweb="input"], .stDateInput div[data-baseweb="input"],
.stTextArea div[data-baseweb="textarea"], .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {
    background: #fff !important; border-color: var(--line-2) !important; border-radius: 10px !important; min-height: 36px !important;
    transition: border-color .18s ease, box-shadow .18s ease !important;
}
.stTextInput input, .stNumberInput input, .stDateInput input { padding-top: .3rem !important; padding-bottom: .3rem !important; }
.stSelectbox div[data-baseweb="select"] > div { font-size: 13px !important; }
.stTextInput div[data-baseweb="input"]:focus-within, .stNumberInput div[data-baseweb="input"]:focus-within,
.stTextArea div[data-baseweb="textarea"]:focus-within, .stSelectbox div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(217,45,32,.14) !important;
}
.stCheckbox label, .stCheckbox p { font-size: 13px !important; }

/* ---------- HIỆU ỨNG NÚT BẤM CAO CẤP ---------- */
.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {
    position: relative;
    overflow: hidden;
    isolation: isolate;
    min-height: 37px;
    padding: .35rem .95rem;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -.01em;
    border-radius: 11px;
    background: linear-gradient(180deg, #FFFFFF 0%, #FFF9F8 100%);
    color: var(--ink);
    border: 1px solid var(--line-2);
    box-shadow: 0 1px 2px rgba(42, 31, 31, .05), inset 0 1px 0 rgba(255, 255, 255, .9);
    transition:
        transform .22s var(--ease-spring),
        box-shadow .22s var(--ease-spring),
        border-color .18s ease,
        background .22s ease,
        color .18s ease !important;
}

/* Luồng sáng lướt qua khi hover (Glass Sheen) */
.stButton > button::after,
.stDownloadButton > button::after,
[data-testid="stFormSubmitButton"] > button::after {
    content: "";
    position: absolute;
    top: -20%;
    left: -130%;
    width: 65%;
    height: 140%;
    background: linear-gradient(110deg, transparent 15%, rgba(255, 255, 255, .52) 50%, transparent 85%);
    transform: skewX(-18deg);
    transition: left .6s var(--ease-spring);
    pointer-events: none;
    z-index: 0;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px);
    border-color: rgba(217, 45, 32, .55);
    color: var(--accent-d);
    background: linear-gradient(180deg, #FFFFFF 0%, #FFF1EF 100%);
    box-shadow: 0 7px 18px -6px rgba(217, 45, 32, .22), 0 2px 5px -1px rgba(42, 31, 31, .06);
}
.stButton > button:hover::after,
.stDownloadButton > button:hover::after,
[data-testid="stFormSubmitButton"] > button:hover::after {
    left: 145%;
}

.stButton > button:active,
.stDownloadButton > button:active,
[data-testid="stFormSubmitButton"] > button:active {
    transform: translateY(1px) scale(.982) !important;
    box-shadow: 0 1px 3px rgba(42, 31, 31, .10), inset 0 2px 4px rgba(42, 31, 31, .06) !important;
    transition-duration: .08s !important;
}

.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible,
[data-testid="stFormSubmitButton"] > button:focus-visible {
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(217, 45, 32, .22), 0 4px 12px -4px rgba(217, 45, 32, .3) !important;
}

/* Nút Primary (Gradient san hô-đỏ + tỏa sáng + sheen đậm hơn) */
button[kind="primary"],
button[data-testid="stBaseButton-primary"],
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {
    background: linear-gradient(135deg, #F04438 0%, #D92D20 55%, #B42318 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(153, 27, 27, .75) !important;
    box-shadow:
        0 6px 16px -4px rgba(217, 45, 32, .50),
        0 2px 4px -1px rgba(180, 35, 24, .25),
        inset 0 1px 0 rgba(255, 255, 255, .28) !important;
}
button[kind="primary"]::after,
button[data-testid="stBaseButton-primary"]::after,
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]::after {
    background: linear-gradient(110deg, transparent 10%, rgba(255, 255, 255, .36) 50%, transparent 90%) !important;
}
button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover,
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover {
    transform: translateY(-2.5px) !important;
    background: linear-gradient(135deg, #F95346 0%, #E03124 55%, #B92519 100%) !important;
    color: #FFFFFF !important;
    border-color: #991B1B !important;
    box-shadow:
        0 12px 24px -6px rgba(217, 45, 32, .60),
        0 4px 8px -2px rgba(180, 35, 24, .30),
        inset 0 1px 0 rgba(255, 255, 255, .36) !important;
}
button[kind="primary"]:active,
button[data-testid="stBaseButton-primary"]:active,
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:active {
    transform: translateY(1px) scale(.98) !important;
    box-shadow: 0 3px 8px -2px rgba(217, 45, 32, .45), inset 0 2px 5px rgba(0, 0, 0, .18) !important;
}
button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p,
[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] p {
    color: #FFFFFF !important;
    position: relative;
    z-index: 1;
}


/* ---------- Thanh điều hướng chính (Segmented Control) ---------- */
[data-testid="stSegmentedControl"] {
    margin: .15rem 0 .25rem !important;
}
[data-testid="stSegmentedControl"] [role="radiogroup"],
[data-testid="stSegmentedControl"] > div {
    background: rgba(255, 255, 255, .82) !important;
    border: 1px solid var(--line) !important;
    border-radius: 14px !important;
    padding: 4px !important;
    gap: 4px !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stSegmentedControl"] button {
    border: 1px solid transparent !important;
    border-radius: 10px !important;
    min-height: 36px !important;
    padding: .3rem .95rem !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    color: var(--ink-2) !important;
    background: transparent !important;
    transition: transform .18s var(--ease-spring), background .18s ease, color .18s ease, box-shadow .2s ease !important;
}
[data-testid="stSegmentedControl"] button:hover {
    background: var(--accent-wash) !important;
    color: var(--accent-d) !important;
    transform: translateY(-1px);
}
[data-testid="stSegmentedControl"] button[aria-checked="true"],
[data-testid="stSegmentedControl"] button[kind="segmented_controlActive"] {
    background: linear-gradient(135deg, #F04438 0%, #D92D20 60%, #B42318 100%) !important;
    color: #FFFFFF !important;
    border-color: rgba(153, 27, 27, .65) !important;
    box-shadow: 0 5px 14px -4px rgba(217, 45, 32, .50), inset 0 1px 0 rgba(255, 255, 255, .28) !important;
}
[data-testid="stSegmentedControl"] button[aria-checked="true"] p,
[data-testid="stSegmentedControl"] button[kind="segmented_controlActive"] p {
    color: #FFFFFF !important;
}

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap: 4px !important; background: transparent !important; border-bottom: 1px solid var(--line); padding: 0 0 2px !important; }
.stTabs [data-baseweb="tab"] {
    height: 36px !important; padding: 0 14px !important; background: transparent !important;
    border-radius: 10px 10px 0 0 !important; transition: background .18s ease, color .18s ease !important;
}
.stTabs [data-baseweb="tab"]:hover { background: rgba(217, 45, 32, .05) !important; }
.stTabs [data-baseweb="tab"] p { font-size: 13px !important; font-weight: 700 !important; color: var(--ink-2) !important; }
.stTabs [aria-selected="true"] p { color: var(--accent-d) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: linear-gradient(90deg, var(--accent-l), var(--accent-d)) !important; height: 3px !important; border-radius: 3px 3px 0 0 !important; }
.stTabs [data-baseweb="tab-border"] { background: transparent !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: .75rem !important; }

/* ---------- Expander / form / alert / metric / bảng / dialog ---------- */
[data-testid="stExpander"] {
    background: #fff !important; border: 1px solid var(--line) !important; border-radius: 14px !important;
    margin-bottom: .15rem; overflow: hidden; box-shadow: var(--shadow-sm);
    transition: box-shadow .2s ease, border-color .2s ease;
}
[data-testid="stExpander"]:hover { border-color: var(--line-2) !important; }
[data-testid="stExpander"] details summary { padding: .45rem .8rem !important; font-size: 13px !important; font-weight: 700 !important; transition: background .16s ease, color .16s ease; }
[data-testid="stExpander"] details summary p { font-size: 13px !important; font-weight: 700 !important; }
[data-testid="stExpander"] details summary:hover { color: var(--accent-d) !important; background: var(--accent-wash); }
[data-testid="stExpanderDetails"] { padding: .4rem .8rem .7rem !important; }
[data-testid="stForm"] { border: 1px solid var(--line) !important; border-radius: 14px !important; padding: .75rem .85rem !important; background: #fff; box-shadow: var(--shadow-sm); }
[data-testid="stAlert"] { border-radius: 11px !important; padding: .45rem .75rem !important; font-size: 13px !important; }
[data-testid="stAlert"] p { font-size: 13px !important; margin: 0 !important; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-sm); }
[class*="st-key-card-"] [data-testid="stForm"] { border: none !important; padding: 0 !important; box-shadow: none !important; }
[class*="st-key-card-"] { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: .75rem .9rem; box-shadow: var(--shadow-sm); }
[data-testid="stFileUploader"] section { padding: .55rem .8rem !important; border-radius: 11px !important; background: var(--accent-wash) !important; border: 1.5px dashed var(--line-2) !important; transition: border-color .18s ease, background .18s ease; }
[data-testid="stFileUploader"] section:hover { border-color: var(--accent) !important; background: #FFF0EE !important; }
[data-testid="stFileUploaderDropzoneInstructions"] span { font-size: 12px !important; }
[data-testid="stDialog"] div[role="dialog"] { border-radius: 18px !important; border: 1px solid var(--line) !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFECE9 0%, #FFF7F6 40%, #FFFFFF 100%) !important;
    border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebarUserContent"], [data-testid="stSidebarContent"] > div:first-child { padding-top: .9rem !important; }
[data-testid="stSidebarUserContent"] { padding-left: 1rem !important; padding-right: 1rem !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .48rem !important; }
.rc-side-h { display: flex; align-items: baseline; justify-content: space-between; margin: .35rem 0 -.1rem; font-size: 13.5px; font-weight: 800; }
.rc-side-h small { font-size: 11.5px; font-weight: 600; color: var(--ink-2); max-width: 55%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ---------- Thanh tiêu đề ---------- */
.rc-top {
    display: flex; align-items: center; justify-content: space-between; gap: 10px 16px; flex-wrap: wrap;
    padding: 9px 15px; border-radius: 15px; background: rgba(255,255,255,.88);
    border: 1px solid var(--line); backdrop-filter: blur(8px); box-shadow: var(--shadow-sm);
}
.rc-top .l { display: flex; align-items: center; gap: 10px; min-width: 0; }
.rc-logo {
    width: 32px; height: 32px; flex: none; border-radius: 10px;
    background: linear-gradient(135deg, var(--accent-l), var(--accent-d));
    color: #fff; display: grid; place-items: center; font-size: 16px;
    box-shadow: 0 4px 10px -3px rgba(217,45,32,.45);
}
.rc-top .t { font-size: 15px; font-weight: 800; letter-spacing: -.015em; line-height: 1.2; }
.rc-top .s { font-size: 11.5px; color: var(--ink-2); display: flex; gap: 4px 14px; flex-wrap: wrap; }
.rc-top .s b { color: var(--ink); font-weight: 700; }
.rc-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.rc-chip { padding: 3.5px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; background: #F4EFEF; color: var(--ink-2); white-space: nowrap; }
.rc-chip.acc { background: var(--accent-soft); color: var(--accent-d); }
.rc-chip.blue { background: #EEF4FF; color: #1D4ED8; }
.rc-chip.ok { background: #ECFDF3; color: #067647; }
.rc-chip.warn { background: #FFF4E5; color: #B45309; }

/* ---------- Tiêu đề mục & thẻ ---------- */
.rc-sec { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 3px 0 6px; }
.rc-sec span { font-size: 14px; font-weight: 800; letter-spacing: -.01em; }
.rc-sec em { font-style: normal; font-size: 11.5px; font-weight: 800; color: var(--ink-2); background: #F6EDEC; padding: 1.5px 9px; border-radius: 999px; }
.rc-sec .lk { font-size: 12px; font-weight: 700; color: var(--accent-d); background: none; padding: 0; }
.rc-empty {
    border: 1.5px dashed var(--line-2); border-radius: 15px; padding: 20px 18px; text-align: center;
    background: linear-gradient(180deg, rgba(255,255,255,.85), rgba(255,246,245,.65));
}
.rc-empty b { font-size: 14px; color: var(--ink); }
.rc-empty div { font-size: 12.5px; color: var(--ink-2); margin-top: 4px; }

/* ---------- Thẻ "Hôm nay" ---------- */
.rc-today {
    position: relative; overflow: hidden; padding: 14px 16px 13px; border-radius: 16px;
    background: linear-gradient(135deg, #FDE3DF 0%, #FFF1EF 58%, #FFF9F8 100%);
    border: 1px solid #F5CECA; box-shadow: var(--shadow-sm); animation: rc-in .35s ease both;
}
.rc-today::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px; background: var(--c); }
.rc-today .kick { font-size: 12px; font-weight: 800; color: var(--accent-d); display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.rc-today .ttl { font-size: 20px; font-weight: 800; letter-spacing: -.02em; margin: 3px 0 1px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rc-today .ttl i { font-style: normal; font-size: 11px; font-weight: 800; padding: 2px 9px; border-radius: 999px; color: #fff; background: var(--c); }
.rc-today .meta { font-size: 13px; color: var(--ink-2); }
.rc-today .note { font-size: 12.5px; color: var(--ink); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.rc-today .prog { display: flex; justify-content: space-between; font-size: 12px; color: var(--ink-2); margin-top: 9px; }
.rc-today .prog b { color: var(--ink); font-weight: 800; }

.rc-bar { height: 6.5px; border-radius: 999px; background: rgba(42,31,31,.09); overflow: hidden; margin: 5px 0 2px; }
.rc-bar > i { display: block; height: 100%; width: var(--w); border-radius: 999px; background: var(--c); animation: rc-grow .9s var(--ease-spring) both; }

/* ---------- KPI ---------- */
.rc-kpis { display: grid; grid-template-columns: repeat(var(--cols, 2), minmax(0, 1fr)); gap: 9px; }
.rc-kpi {
    display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 13px;
    background: #fff; border: 1px solid var(--line); box-shadow: var(--shadow-sm);
    animation: rc-in .35s ease both;
    transition: transform .22s var(--ease-spring), box-shadow .22s var(--ease-spring), border-color .18s ease;
}
.rc-kpi:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); border-color: color-mix(in srgb, var(--c) 35%, var(--line)); }
.rc-kpi .ic { width: 32px; height: 32px; flex: none; border-radius: 10px; display: grid; place-items: center; font-size: 15px; background: color-mix(in srgb, var(--c) 14%, #fff); }
.rc-kpi .lb { font-size: 11px; font-weight: 700; color: var(--ink-2); line-height: 1.2; }
.rc-kpi .val { font-size: 18px; font-weight: 800; letter-spacing: -.02em; line-height: 1.25; }
.rc-kpi .val small { font-size: 11px; font-weight: 700; color: var(--ink-2); margin-left: 3px; }

/* ---------- Danh sách "Cần chú ý" / "Đang theo dõi" ---------- */
.rc-list { background: #fff; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; box-shadow: var(--shadow-sm); animation: rc-in .35s ease both; }
.rc-row { display: flex; gap: 10px; align-items: flex-start; padding: 9px 12px; transition: background .15s ease; }
.rc-row:hover { background: var(--accent-wash); }
.rc-row + .rc-row { border-top: 1px solid var(--line); }
.rc-row .ic { width: 29px; height: 29px; flex: none; border-radius: 9px; display: grid; place-items: center; font-size: 14px; background: var(--accent-soft); }
.rc-row .bd { min-width: 0; flex: 1; }
.rc-row .tt { font-size: 13px; font-weight: 800; line-height: 1.3; }
.rc-row .sb { font-size: 11.5px; color: var(--ink-2); margin-top: 1px; }
.rc-row .tg { display: inline-block; margin-top: 3px; font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 999px; background: #F6EDEC; color: var(--ink-2); }
.rc-row .tg.acc { background: #FFF1E6; color: #B45309; }
.rc-none { padding: 11px 12px; font-size: 12.5px; color: var(--ink-2); }

/* ---------- Dải tuần ---------- */
.rc-week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; }
.rc-day {
    position: relative; min-height: 64px; padding: 6px 4px; border-radius: 12px; text-align: center;
    display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 1px;
    background: rgba(255,255,255,.78); border: 1px dashed var(--line-2); color: var(--ink-3);
    transition: transform .2s var(--ease-spring), box-shadow .2s ease;
}
.rc-day:hover { transform: translateY(-2px); box-shadow: var(--shadow-sm); }
.rc-day .d { font-size: 11px; font-weight: 800; letter-spacing: .02em; }
.rc-day .w { font-size: 11px; font-weight: 700; line-height: 1.2; }
.rc-day .k { font-size: 15px; font-weight: 800; line-height: 1.15; }
.rc-day .k small { font-size: 10px; font-weight: 700; opacity: .75; }
.rc-day.on { border: 1px solid color-mix(in srgb, var(--c) 40%, #fff); background: color-mix(in srgb, var(--c) 11%, #fff); color: color-mix(in srgb, var(--c) 82%, #000); }
.rc-day.on.done { background: var(--c); border-color: var(--c); color: #fff; box-shadow: 0 4px 12px -4px color-mix(in srgb, var(--c) 65%, transparent); }
.rc-day.on.today { box-shadow: 0 0 0 2px #fff, 0 0 0 4px var(--c); }
.rc-day.done::after { content: "✓"; position: absolute; top: 3px; right: 6px; font-size: 11px; font-weight: 900; }
@media (max-width: 700px) { .rc-week { grid-template-columns: repeat(4, 1fr); } }

/* ---------- Đường đua ---------- */
.rc-track { padding: 10px 14px 10px; border-radius: 14px; background: #fff; border: 1px solid var(--line); box-shadow: var(--shadow-sm); }
.rc-track .row { display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; color: var(--ink-2); }
.rc-track .lane { position: relative; height: 8px; margin: 18px 0 5px; border-radius: 999px; background: repeating-linear-gradient(90deg, #F2E2E0 0 10px, transparent 10px 16px); }
.rc-track .lane > i { position: absolute; left: 0; top: 0; height: 100%; width: var(--w); border-radius: 999px; background: linear-gradient(90deg, #F59E0B, var(--accent)); animation: rc-grow 1.1s var(--ease-spring) both; }
.rc-track .runner { position: absolute; top: -17px; left: var(--w); transform: translateX(-50%); font-size: 16px; }
.rc-track .flag { position: absolute; top: -17px; right: -2px; font-size: 16px; }

/* ---------- Hộp lời khuyên HLV & thẻ giày ---------- */
.hlv-box {
    font-size: 13.5px; line-height: 1.55; color: var(--ink);
    background: linear-gradient(135deg, #FFF1EF, #FFFFFF); padding: 11px 15px; border-radius: 13px;
    border: 1px solid #F6D0CC; border-left: 4px solid var(--accent); box-shadow: var(--shadow-sm);
}
.shoe-card {
    background: #fff; border: 1px solid var(--line); border-radius: 13px; padding: 10px 13px;
    margin-bottom: 7px; box-shadow: var(--shadow-sm);
    transition: transform .2s var(--ease-spring), box-shadow .2s ease;
}
.shoe-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.shoe-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; }
.shoe-meta { font-size: 12px; opacity: .75; display: flex; justify-content: space-between; }

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
</style>
"""


def inject_ui():
    st.markdown(_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------- tiện ích
def _clamp_pct(v):
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return 0


def _html(s):
    st.markdown("".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


def _chip(text, tone=""):
    return f'<span class="rc-chip {escape(tone)}">{escape(str(text))}</span>'


def _safe_json(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def render_iframe(html_code, height):
    if hasattr(st, "iframe"):
        st.iframe(html_code, height=height)
    else:
        components.html(html_code, height=height)


# ----------------------------------------------------------------- khối giao diện
def topbar(title, meta=None, chips=None):
    meta_html = "".join(f"<span>{escape(str(k))} <b>{escape(str(v))}</b></span>" for k, v in (meta or []))
    chips_html = "".join(_chip(t, tone) for t, tone in (chips or []))
    _html(
        f'<div class="rc-top"><div class="l"><div class="rc-logo">🏃</div>'
        f'<div><div class="t">{escape(title)}</div><div class="s">{meta_html}</div></div></div>'
        f'<div class="rc-chips">{chips_html}</div></div>'
    )


def side_title(text, sub=""):
    sub_html = f"<small>{escape(sub)}</small>" if sub else ""
    st.markdown(f'<div class="rc-side-h"><span>{escape(text)}</span>{sub_html}</div>', unsafe_allow_html=True)


def section_title(text, count=None, link=None):
    cnt = f"<em>{escape(str(count))}</em>" if count not in (None, "") else ""
    lk = f'<em class="lk">{escape(link)}</em>' if link else ""
    _html(f'<div class="rc-sec"><span>{escape(text)}</span>{cnt or lk}</div>')


def empty_state(title, sub=""):
    _html(f'<div class="rc-empty"><b>{escape(title)}</b><div>{escape(sub)}</div></div>')


def progress_bar_html(pct, color="#16A34A"):
    return f'<div class="rc-bar"><i style="--w:{_clamp_pct(pct)}%;--c:{color}"></i></div>'


def today_card(kicker, title, meta="", note="", pct=0, progress_label="", color="#D92D20", badge=""):
    badge_html = f"<i>{escape(badge)}</i>" if badge else ""
    note_html = f'<div class="note">{escape(note)}</div>' if note else ""
    _html(
        f'<div class="rc-today" style="--c:{color}"><div class="kick"><span>{escape(kicker)}</span></div>'
        f'<div class="ttl">{escape(title)}{badge_html}</div><div class="meta">{escape(meta)}</div>{note_html}'
        f'<div class="prog"><span>{escape(progress_label)}</span><b>{_clamp_pct(pct)}%</b></div>'
        f'{progress_bar_html(pct, color)}</div>'
    )


def kpi_row(items, cols=2):
    cards = []
    for i, it in enumerate(items):
        unit = f"<small>{escape(str(it['unit']))}</small>" if it.get("unit") else ""
        title_attr = f' title="{escape(str(it["help"]))}"' if it.get("help") else ""
        cards.append(
            f'<div class="rc-kpi" style="--c:{it.get("color", "#D92D20")};animation-delay:{i * 0.04:.2f}s"{title_attr}>'
            f'<span class="ic">{escape(str(it.get("icon", "🏃")))}</span>'
            f'<div><div class="lb">{escape(str(it["label"]))}</div>'
            f'<div class="val">{escape(str(it["value"]))}{unit}</div></div></div>'
        )
    _html(f'<div class="rc-kpis" style="--cols:{int(cols)}">{"".join(cards)}</div>')


def attention_list(items, empty_text="Không cần bạn xử lý ngay."):
    if not items:
        _html(f'<div class="rc-list"><div class="rc-none">{escape(empty_text)}</div></div>')
        return
    rows = []
    for it in items:
        tag = f'<span class="tg acc">{escape(str(it["tag"]))}</span>' if it.get("tag") else ""
        sub = f'<div class="sb">{escape(str(it["sub"]))}</div>' if it.get("sub") else ""
        rows.append(
            f'<div class="rc-row"><span class="ic">{escape(str(it.get("icon", "•")))}</span>'
            f'<div class="bd"><div class="tt">{escape(str(it["title"]))}</div>{sub}{tag}</div></div>'
        )
    _html(f'<div class="rc-list">{"".join(rows)}</div>')


def watch_list(items):
    if not items:
        _html('<div class="rc-list"><div class="rc-none">Chưa có dữ liệu để theo dõi.</div></div>')
        return
    rows = []
    for it in items:
        tag = f'<span class="tg">{escape(str(it["tag"]))}</span>' if it.get("tag") else ""
        rows.append(
            f'<div class="rc-row"><span class="ic" style="background:color-mix(in srgb, {it.get("color", "#16A34A")} 14%, #fff)">{escape(str(it.get("icon", "•")))}</span>'
            f'<div class="bd"><div class="tt">{escape(str(it["title"]))}</div>'
            f'<div class="sb">{escape(str(it.get("sub", "")))}</div>'
            f'{progress_bar_html(it.get("pct", 0), it.get("color", "#16A34A"))}{tag}</div></div>'
        )
    _html(f'<div class="rc-list">{"".join(rows)}</div>')


def shoe_card(s):
    bar_color = "#EF4444" if s["total_km"] >= s["max_km"] else ("#F59E0B" if s["pct"] >= 80 else "#10B981")
    rem_km = max(0.0, round(s["max_km"] - s["total_km"], 1))
    star_prefix = "⭐ " if s.get("is_default") else ""
    _html(
        f'<div class="shoe-card"><div class="shoe-header"><div>'
        f'<strong style="font-size:15px;">{star_prefix}{escape(s["name"])}</strong>'
        f'<span style="font-size:12px;opacity:0.65;margin-left:8px;">{escape(s.get("brand", ""))}</span>'
        f'</div><div style="font-weight:800;color:{bar_color};">{s["total_km"]} / {s["max_km"]:g} km ({s["pct"]}%)</div></div>'
        f'{progress_bar_html(s["pct"], bar_color)}'
        f'<div class="shoe-meta"><span>{escape(s["status"])}</span><span>Còn lại ~{rem_km} km trước khi cần thay mới</span></div></div>'
    )


def week_strip(schedule, normalize_day=None, today_name=None):
    norm = normalize_day or (lambda x: x)
    by_day = {}
    for it in schedule or []:
        by_day.setdefault(norm(it.get("day")), it)
    cells = []
    for day, short in zip(DAY_ORDER, DAY_SHORT):
        it = by_day.get(day)
        if not it:
            cells.append(f'<div class="rc-day"><div class="d">{short}</div><div class="w">—</div></div>')
            continue
        wt = str(it.get("workout_type") or "")
        color = TYPE_COLORS.get(wt, "#16A34A")
        try:
            km = float(it.get("distance_km") or 0)
        except (TypeError, ValueError):
            km = 0.0
        km_html = f'<div class="k">{km:.1f}<small> km</small></div>' if wt != "Rest" else ""
        cls = "rc-day on" + (" done" if it.get("completed") else "") + (" today" if today_name and day == today_name else "")
        cells.append(
            f'<div class="{cls}" style="--c:{color}"><div class="d">{short}</div>'
            f'<div class="w">{escape(wt)}</div>{km_html}</div>'
        )
    _html(f'<div class="rc-week">{"".join(cells)}</div>')


def race_track(days_left, total_days=None, race_name=""):
    if days_left is None or days_left < 0:
        return
    total = max(int(total_days or 0), int(days_left), 1)
    pct = _clamp_pct((1 - days_left / total) * 100)
    label = escape(race_name) if race_name else "Race day"
    left_txt = "HÔM NAY!" if days_left == 0 else f"còn {days_left} ngày"
    _html(
        f'<div class="rc-track"><div class="row"><span>🏁 {label}</span><span>{left_txt}</span></div>'
        f'<div class="lane" style="--w:{pct}%"><i></i><span class="runner">🏃</span><span class="flag">🏁</span></div>'
        f'<div class="row"><span>Xuất phát</span><span>{pct}% chặng đường</span></div></div>'
    )


# ----------------------------------------------------------------- Dashboard động (Tab Lịch sử)
_DASHBOARD_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@500;600;700;800&display=swap');
:root{
  color-scheme:light;
  --ux-ink:#241A1A; --ux-ink-2:#6B5C5C; --ux-ink-3:#9A8A8A; --ux-line:#F1DFDD;
  --ux-accent:#D92D20; --ux-wash:#FFF6F5; --ux-surface-2:#FDECEA;
}
html,body{margin:0;background:transparent}
.ux,.ux *,.ux *::before,.ux *::after{box-sizing:border-box}
.ux{font-family:'Be Vietnam Pro',-apple-system,'Segoe UI',sans-serif;color:var(--ux-ink);display:flex;justify-content:center}
.ux button{cursor:pointer;font:inherit;color:inherit;border:none;background:none}
.u213{position:relative;width:100%;height:270px;border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 0 0 1px var(--ux-line),0 4px 16px -8px rgba(180,35,24,.12)}
.u213-tl{position:absolute;left:12px;right:12px;top:10px;display:grid;grid-template-columns:repeat(3,1fr);gap:7px}
.u213-tb{position:relative;display:flex;flex-direction:row;align-items:center;justify-content:center;gap:6px;padding:7px 6px 11px;border-radius:11px;color:var(--ux-ink-3);font-size:12.5px;font-weight:700;transition:color .22s,background .22s,transform .18s cubic-bezier(.22,1,.36,1),box-shadow .2s}
.u213-tb:hover{background:#FFF4F2;color:var(--ux-ink);transform:translateY(-1px)}
.u213-tb:active{transform:translateY(1px) scale(.98)}
.u213-tb svg{width:15px;height:15px}
.u213-tb.is-on{color:var(--ux-accent);background:var(--ux-surface-2);box-shadow:0 3px 10px -4px rgba(217,45,32,.25)}
.u213-tb>i{position:absolute;left:12px;right:12px;bottom:4px;height:2.5px;border-radius:2px;background:var(--ux-line);overflow:hidden}
.u213-tb>i b{display:block;height:100%;border-radius:2px;background:linear-gradient(90deg,#F04438,#B42318);transform:scaleX(0);transform-origin:0 50%}
.u213-pv{position:absolute;left:12px;right:12px;top:54px;bottom:12px;border-radius:13px;background:var(--ux-wash);box-shadow:0 0 0 1px var(--ux-line);overflow:hidden}
.u213-pn{position:absolute;inset:0;padding:10px 14px;opacity:0;transform:translateY(8px);transition:opacity .35s,transform .4s cubic-bezier(.2,.8,.2,1);pointer-events:none}
.u213-pn.is-on{opacity:1;transform:none}
.u213-pn small{font-size:11.5px;font-weight:700;color:var(--ux-ink-2)}
.u213-wk{position:relative;display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-top:6px;height:calc(100% - 20px)}
.u213-wk>span{display:block;border-radius:9px;background:#fff;box-shadow:0 0 0 1px var(--ux-line);font-size:11px;font-weight:800;color:var(--ux-ink-3);text-align:center;padding-top:5px}
.u213-ev{position:absolute;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;text-align:center;border-radius:9px;padding:4px 3px;font-size:11.5px;font-weight:700;line-height:1.25;color:#fff;opacity:0;transform:translateY(-6px) scale(.94);transition:opacity .3s,transform .4s cubic-bezier(.3,1.4,.5,1);overflow:hidden;font-variant-numeric:tabular-nums}
.u213-ev small{font-size:10px;font-weight:600;color:#fff;opacity:.92}
.u213-ev.is-done{box-shadow:0 0 0 2px #fff inset}
.u213-pn.is-play .u213-ev{opacity:1;transform:none}
.u213-dh{display:flex;align-items:center;gap:6px}
.u213-dh b{font-size:14px;font-weight:800;margin-right:auto}
.u213-dh em{font-style:normal;font-size:11px;font-weight:800;color:#2563EB}
.u213-sum{margin-top:8px;font-size:13px;line-height:1.55;color:var(--ux-ink);display:-webkit-box;-webkit-line-clamp:7;-webkit-box-orient:vertical;overflow:hidden}
.u213-kp{display:flex;align-items:baseline;gap:10px;margin-top:2px;font-variant-numeric:tabular-nums}
.u213-kp b{font-size:28px;font-weight:800;letter-spacing:-.02em}
.u213-kp span{font-size:12px;font-weight:700;color:#16A34A}
.u213-br{display:flex;align-items:flex-end;gap:10px;height:84px;margin-top:20px;border-bottom:1px solid var(--ux-line)}
.u213-br i{position:relative;flex:1;border-radius:6px 6px 2px 2px;background:rgba(217,45,32,.26);height:var(--h);transform:scaleY(0);transform-origin:50% 100%;transition:transform .6s cubic-bezier(.3,1.3,.5,1)}
.u213-br i:last-child{background:linear-gradient(180deg,#F04438,#B42318)}
.u213-pn.is-play .u213-br i{transform:none}
.u213-br i::after{content:attr(data-v);position:absolute;top:-16px;left:50%;transform:translateX(-50%);font-size:10.5px;font-style:normal;font-weight:700;color:var(--ux-ink-2);font-variant-numeric:tabular-nums}
</style>
<div class="ux">
  <div class="u213">
    <div class="u213-tl" role="tablist">
      <button type="button" class="u213-tb" role="tab"><svg viewBox="0 0 16 16"><rect x="2" y="3" width="12" height="11" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3" stroke="currentColor" stroke-width="1.6"/></svg>Lịch tuần<i><b></b></i></button>
      <button type="button" class="u213-tb" role="tab"><svg viewBox="0 0 16 16"><path d="M4 1.8h5.5L13 5.3v8.4a.6.6 0 0 1-.6.6H4a.6.6 0 0 1-.6-.6V2.4a.6.6 0 0 1 .6-.6z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 8.5h4.5M6 11h3" stroke="currentColor" stroke-width="1.6"/></svg>Nhận xét AI<i><b></b></i></button>
      <button type="button" class="u213-tb" role="tab"><svg viewBox="0 0 16 16"><path d="M2.5 13.5h11M4.5 11V8M8 11V4.5M11.5 11V6.5" stroke="currentColor" stroke-width="1.8"/></svg>Khối lượng<i><b></b></i></button>
    </div>
    <div class="u213-pv">
      <div class="u213-pn" role="tabpanel"><small>Lịch tập tuần gần nhất</small><div class="u213-wk" id="dynamic_wk"><span>T2</span><span>T3</span><span>T4</span><span>T5</span><span>T6</span><span>T7</span><span>CN</span></div></div>
      <div class="u213-pn" role="tabpanel"><div class="u213-dh"><b>Phân tích giáo án</b><em>AI Coach</em></div><div class="u213-sum" id="week_sum"></div></div>
      <div class="u213-pn" role="tabpanel"><small>Tổng quãng đường đã hoàn thành</small><div class="u213-kp"><b id="real_km">0 KM</b><span id="real_rate"></span></div><div class="u213-br" id="weekly_bars"></div></div>
    </div>
  </div>
</div>
<script>
(function () {
  var root = document.querySelector('.ux');
  var T = Array.prototype.slice.call(root.querySelectorAll('.u213-tb')),
      P = Array.prototype.slice.call(root.querySelectorAll('.u213-pn')),
      pv = root.querySelector('.u213-pv');

  var scheduleList = __SCHEDULE_JSON__;
  var weeklyKm = __WEEKLY_JSON__;
  var weekSummary = __SUMMARY_JSON__;
  var doneRate = __RATE__;

  var wk = root.querySelector('#dynamic_wk');
  var dayMap = {"Thứ 2": 0, "Thứ 3": 1, "Thứ 4": 2, "Thứ 5": 3, "Thứ 6": 4, "Thứ 7": 5, "Chủ Nhật": 6};
  var colorMap = {"Easy Run": "#16A34A", "Tempo": "#D97706", "Interval": "#DB2777", "Long Run": "#7C3AED", "Rest": "#94A3B8", "Walk": "#2563EB", "Threshold": "#DC2626"};
  scheduleList.forEach(function (item, idx) {
    var colIndex = dayMap[item.day] !== undefined ? dayMap[item.day] : idx;
    var d = document.createElement('div');
    d.className = 'u213-ev';
    var bgCol = colorMap[item.workout_type] || '#10B981';
    var t1 = document.createElement('span'); t1.textContent = item.workout_type;
    d.appendChild(t1);
    if (item.workout_type !== 'Rest') {
      var kmVal = (item.completed && item.actual_km != null) ? item.actual_km : item.distance_km;
      var t2 = document.createElement('span'); t2.textContent = Number(kmVal || 0).toFixed(1) + ' km';
      d.appendChild(t2);
      var pVal = (item.completed && item.actual_pace) ? item.actual_pace : item.pace_target;
      if (pVal) { var t3 = document.createElement('small'); t3.textContent = pVal + '/km'; d.appendChild(t3); }
    }
    if (item.completed) { d.classList.add('is-done'); var t4 = document.createElement('small'); t4.textContent = '\u2713 Xong'; d.appendChild(t4); }
    d.style.cssText = 'left:calc((100% - 36px) / 7 * ' + colIndex + ' + ' + (6 * colIndex) + 'px);width:calc((100% - 36px) / 7);top:26px;bottom:5px;background:' + bgCol + ';transition-delay:' + (0.1 + idx * 0.05) + 's';
    wk.appendChild(d);
  });

  root.querySelector('#week_sum').textContent = weekSummary || 'Chưa có lời khuyên cho tuần này.';

  var bars = root.querySelector('#weekly_bars');
  var data = weeklyKm.slice(-7);
  while (data.length < 7) data.unshift(0);
  var maxKm = Math.max.apply(null, data.concat([1]));
  data.forEach(function (v, i) {
    var b = document.createElement('i');
    b.style.setProperty('--h', Math.max(4, Math.round(v / maxKm * 90)) + '%');
    b.title = v.toFixed(1) + ' km'; if (v > 0) b.setAttribute('data-v', v.toFixed(1));
    b.style.transitionDelay = (0.08 + i * 0.06) + 's';
    bars.appendChild(b);
  });
  root.querySelector('#real_rate').textContent = doneRate + '% buổi tập hoàn thành';

  var kp = root.querySelector('#real_km');
  var DUR = 4200, cur = -1, acc = 0, last = 0, hold = false, raf = 0;
  function scene(i) {
    var p = P[i]; p.classList.remove('is-play'); void p.offsetWidth; p.classList.add('is-play');
    if (i === 2) {
      var to = __COMPLETED_KM__, t0 = performance.now();
      (function f(now) {
        var k = Math.min(1, (now - t0) / 1100), e = 1 - Math.pow(1 - k, 3);
        kp.textContent = (to * e).toFixed(1) + ' KM';
        if (k < 1 && cur === 2) requestAnimationFrame(f);
      })(t0);
    }
  }
  function go(i) {
    if (i === cur) return;
    cur = i; acc = 0;
    T.forEach(function (t, k) { var on = k === i; t.classList.toggle('is-on', on); t.querySelector('b').style.transform = 'scaleX(' + (on ? 1 : 0) + ')'; });
    P.forEach(function (p, k) { p.classList.toggle('is-on', k === i); if (k !== i) p.classList.remove('is-play'); });
    scene(i);
  }
  function tick(now) {
    raf = 0; if (!hold) acc += Math.min(64, now - last); last = now;
    var p = Math.min(1, acc / DUR);
    T[cur].querySelector('b').style.transform = 'scaleX(' + p.toFixed(3) + ')';
    if (p >= 1) go((cur + 1) % T.length);
    raf = requestAnimationFrame(tick);
  }
  function run() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); } }
  T.forEach(function (t, i) { t.addEventListener('click', function () { go(i); run(); }); });
  pv.addEventListener('pointerenter', function () { hold = true; });
  pv.addEventListener('pointerleave', function () { hold = false; });
  go(0); run();
})();
</script>
"""


def render_dynamic_dashboard(completed_km, schedule_data, weekly_km, week_summary, completion_rate):
    html_code = (
        _DASHBOARD_TEMPLATE
        .replace("__SCHEDULE_JSON__", _safe_json(schedule_data))
        .replace("__WEEKLY_JSON__", _safe_json(weekly_km))
        .replace("__SUMMARY_JSON__", _safe_json(week_summary))
        .replace("__RATE__", str(int(completion_rate)))
        .replace("__COMPLETED_KM__", str(float(completed_km)))
    )
    render_iframe(html_code, height=280)


# ----------------------------------------------------------------- Lịch hoạt động theo tháng
_MONTH_CAL_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@500;600;700;800&display=swap');
:root{
  --ink:#241A1A; --ink-2:#6B5C5C; --ink-3:#9A8A8A;
  --line:#F1DFDD; --accent:#D92D20; --accent-d:#B42318;
  --accent-soft:#FDECEA; --accent-wash:#FFF6F5;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:transparent;font-family:'Be Vietnam Pro',-apple-system,'Segoe UI',sans-serif;color:var(--ink)}
.mc-card{
  background:#fff;border:1px solid var(--line);border-radius:16px;padding:12px 14px;
  box-shadow:0 2px 10px -4px rgba(180,35,24,.08);
}
.mc-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.mc-title{font-size:15px;font-weight:800;line-height:1.2}
.mc-sub{font-size:11.5px;color:var(--ink-2);margin-top:2px}
.mc-metrics{display:flex;gap:14px;align-items:center;font-variant-numeric:tabular-nums}
.mc-stat{text-align:right}
.mc-stat b{display:block;font-size:17px;font-weight:800;color:var(--accent-d);line-height:1.1}
.mc-stat span{font-size:11px;font-weight:700;color:var(--ink-2)}

.mc-pills{
  display:flex;gap:6px;overflow-x:auto;padding:10px 0 8px;margin-top:6px;
  border-top:1px solid var(--line);scrollbar-width:none;
}
.mc-pills::-webkit-scrollbar{display:none}
.mc-pill{
  flex:none;border:1px solid var(--line);background:var(--accent-wash);color:var(--ink-2);
  font:700 12px/1 'Be Vietnam Pro',sans-serif;padding:7.5px 14px;border-radius:999px;cursor:pointer;
  transition:transform .2s cubic-bezier(.22,1,.36,1),box-shadow .2s ease,border-color .16s,background .16s,color .16s;
}
.mc-pill:hover{transform:translateY(-1.5px);border-color:var(--accent);color:var(--accent-d);box-shadow:0 4px 12px -4px rgba(217,45,32,.25)}
.mc-pill:active{transform:translateY(1px) scale(.97)}
.mc-pill.is-active{
  background:linear-gradient(135deg,#F04438,#B42318);border-color:#B42318;color:#fff;
  box-shadow:0 5px 14px -4px rgba(217,45,32,.55);
}

.mc-grid{
  display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px;
  background:var(--accent-wash);border:1px solid var(--line);border-radius:13px;padding:8px 7px;
  font-variant-numeric:tabular-nums;
}
.mc-dow{
  text-align:center;font-size:11px;font-weight:800;color:var(--ink-2);padding-bottom:3px;
}
.mc-cell{
  position:relative;height:39px;border-radius:10px;border:1.5px solid transparent;
  background:transparent;color:var(--ink);font:700 12.5px/1 'Be Vietnam Pro',sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
  cursor:pointer;padding:2px;transition:transform .18s cubic-bezier(.22,1,.36,1),border-color .15s,background .15s,box-shadow .18s;
}
.mc-cell:hover{transform:translateY(-2px);border-color:#E5CDCA;background:#fff;box-shadow:0 4px 10px -4px rgba(42,31,31,.15)}
.mc-cell:active{transform:scale(.95)}
.mc-cell.is-out{opacity:.32}
.mc-cell.is-done-1{background:#FDECEA;color:#991B1B}
.mc-cell.is-done-2{background:#FAD1CD;color:#991B1B}
.mc-cell.is-done-3{background:#EE7B72;color:#fff}
.mc-cell.is-done-4{background:linear-gradient(135deg,#F04438,#B42318);color:#fff}
.mc-cell.is-plan{background:#fff;border:1.5px dashed #E5A9A3;color:var(--ink)}
.mc-cell.is-today{border-color:var(--accent);box-shadow:0 0 0 1px rgba(217,45,32,.2)}
.mc-cell.is-sel{border-color:#2563EB;box-shadow:0 0 0 2.5px rgba(37,99,235,.22)}
.mc-km{font-size:9.5px;font-weight:700;line-height:1;opacity:.92}

.mc-foot{
  margin-top:8px;padding:8px 11px;border-radius:11px;background:#fff;border:1px solid var(--line);
  display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;
}
.mc-foot-date{font-weight:800;color:var(--ink);white-space:nowrap}
.mc-foot-desc{color:var(--ink-2);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
<div class="mc-card">
  <div class="mc-head">
    <div>
      <div class="mc-title">Hoạt động chạy của bạn</div>
      <div class="mc-sub">Chọn tháng để xem số ngày tập &amp; chi tiết từng ngày</div>
    </div>
    <div class="mc-metrics">
      <div class="mc-stat"><b id="m_days">0 ngày</b><span>Số ngày tập</span></div>
      <div class="mc-stat"><b id="m_km">0.0 km</b><span>Tổng quãng đường</span></div>
      <div class="mc-stat"><b id="m_max">0.0 km</b><span>Dài nhất</span></div>
    </div>
  </div>
  <div class="mc-pills" id="mc_pills"></div>
  <div class="mc-grid" id="mc_grid"></div>
  <div class="mc-foot">
    <span class="mc-foot-date" id="mc_sel_date"></span>
    <span class="mc-foot-desc" id="mc_sel_desc"></span>
  </div>
</div>
<script>
(function(){
  var DATA = __DATA_JSON__;
  var pillsEl = document.getElementById('mc_pills');
  var gridEl = document.getElementById('mc_grid');
  var activeMonth = DATA.default_month;
  var selectedDate = DATA.today;

  function pad(n){ return n < 10 ? '0' + n : '' + n; }
  function toIso(d){ return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function fmtVn(iso){
    var p = iso.split('-');
    return p.length === 3 ? (p[2] + '/' + p[1] + '/' + p[0]) : iso;
  }

  function updateFoot(iso){
    selectedDate = iso;
    var label = fmtVn(iso) + (iso === DATA.today ? ' (Hôm nay)' : '');
    document.getElementById('mc_sel_date').textContent = label;
    var ev = DATA.events[iso];
    var descEl = document.getElementById('mc_sel_desc');
    if (ev && ev.items && ev.items.length){
      descEl.textContent = ev.items.join(' · ');
      descEl.title = ev.items.join(' | ');
    } else {
      descEl.textContent = 'Không có buổi chạy';
      descEl.title = '';
    }
  }

  function renderPills(){
    pillsEl.innerHTML = '';
    DATA.months.forEach(function(m){
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'mc-pill' + (m.key === activeMonth ? ' is-active' : '');
      btn.textContent = m.label;
      btn.onclick = function(){
        activeMonth = m.key;
        if (!selectedDate.startsWith(activeMonth)){
          selectedDate = DATA.today.startsWith(activeMonth) ? DATA.today : (activeMonth + '-01');
        }
        renderPills();
        renderCalendar();
      };
      pillsEl.appendChild(btn);
      if (m.key === activeMonth){
        setTimeout(function(){ btn.scrollIntoView({inline:'center', block:'nearest'}); }, 0);
      }
    });
  }

  function renderCalendar(){
    var parts = activeMonth.split('-');
    var y = parseInt(parts[0], 10);
    var m = parseInt(parts[1], 10) - 1;

    var prefix = activeMonth + '-';
    var runDays = 0, totalKm = 0, maxKm = 0;
    Object.keys(DATA.events).forEach(function(iso){
      if (iso.startsWith(prefix)){
        var ev = DATA.events[iso];
        if (ev.done_km > 0){
          runDays += 1;
          totalKm += ev.done_km;
          if (ev.done_km > maxKm) maxKm = ev.done_km;
        }
      }
    });
    document.getElementById('m_days').textContent = runDays + ' ngày';
    document.getElementById('m_km').textContent = totalKm.toFixed(1) + ' km';
    document.getElementById('m_max').textContent = maxKm.toFixed(1) + ' km';

    var first = new Date(y, m, 1);
    var startOffset = (first.getDay() + 6) % 7;
    var startGrid = new Date(y, m, 1 - startOffset);

    var last = new Date(y, m + 1, 0);
    var endOffset = 6 - ((last.getDay() + 6) % 7);
    var endGrid = new Date(y, m + 1, endOffset);

    gridEl.innerHTML = '';
    ['T2','T3','T4','T5','T6','T7','CN'].forEach(function(d){
      var h = document.createElement('div');
      h.className = 'mc-dow';
      h.textContent = d;
      gridEl.appendChild(h);
    });

    var scaleMax = Math.max(maxKm, 5.0);
    var cur = new Date(startGrid.getTime());
    while (cur <= endGrid){
      var iso = toIso(cur);
      var inMonth = (cur.getMonth() === m);
      var ev = DATA.events[iso];
      var cell = document.createElement('button');
      cell.type = 'button';
      var cls = ['mc-cell'];
      if (!inMonth) cls.push('is-out');
      if (iso === DATA.today) cls.push('is-today');
      if (iso === selectedDate) cls.push('is-sel');

      var subTxt = '';
      if (ev && ev.done_km > 0){
        var r = ev.done_km / scaleMax;
        var lvl = r <= 0.25 ? 1 : (r <= 0.5 ? 2 : (r <= 0.75 ? 3 : 4));
        cls.push('is-done-' + lvl);
        subTxt = ev.done_km.toFixed(1) + 'k';
      } else if (ev && ev.planned_km > 0){
        cls.push('is-plan');
        subTxt = ev.planned_km.toFixed(1) + 'k';
      }

      cell.className = cls.join(' ');
      var numSpan = document.createElement('span');
      numSpan.textContent = cur.getDate();
      cell.appendChild(numSpan);
      if (subTxt){
        var kmSpan = document.createElement('span');
        kmSpan.className = 'mc-km';
        kmSpan.textContent = subTxt;
        cell.appendChild(kmSpan);
      }

      (function(targetIso, targetInMonth){
        cell.onclick = function(){
          if (!targetInMonth){
            activeMonth = targetIso.slice(0, 7);
            selectedDate = targetIso;
            renderPills();
            renderCalendar();
          } else {
            selectedDate = targetIso;
            renderCalendar();
          }
        };
      })(iso, inMonth);

      gridEl.appendChild(cell);
      cur.setDate(cur.getDate() + 1);
    }
    updateFoot(selectedDate);
  }

  renderPills();
  renderCalendar();
})();
</script>
"""


def _parse_any_date(val):
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:16] if fmt == "%d/%m/%Y %H:%M" else s[:10], fmt).date()
        except ValueError:
            continue
    return None


def monthly_calendar_card(project, today):
    """Lịch chọn tháng (từ tháng khởi tạo dự án đổ đi) & thống kê số ngày tập trong tháng."""
    plans = (project or {}).get("plans") or []
    all_dates = []

    proj_created = _parse_any_date((project or {}).get("created_at"))
    if proj_created:
        all_dates.append(proj_created)

    day_events = {}
    for p in plans:
        ws = _parse_any_date(p.get("week_start"))
        if ws:
            all_dates.append(ws)
        pc = _parse_any_date(p.get("created_at"))
        if pc:
            all_dates.append(pc)
        for it in p.get("schedule") or []:
            d = _parse_any_date(it.get("date"))
            nd = str(it.get("day") or "").strip()
            if d is None and ws and nd in DAY_ORDER:
                d = ws + timedelta(days=DAY_ORDER.index(nd))
            if d is None:
                continue
            all_dates.append(d)
            iso = d.isoformat()
            rec = day_events.setdefault(iso, {"done_km": 0.0, "planned_km": 0.0, "items": []})
            wt = str(it.get("workout_type") or "")
            if wt == "Rest":
                rec["items"].append("Nghỉ phục hồi")
                continue
            try:
                p_km = float(it.get("distance_km") or 0.0)
            except (TypeError, ValueError):
                p_km = 0.0
            if it.get("completed"):
                a_km = it.get("actual_km")
                try:
                    km = float(a_km) if (a_km is not None and float(a_km) >= 0) else p_km
                except (TypeError, ValueError):
                    km = p_km
                rec["done_km"] = round(rec["done_km"] + km, 2)
                pace = it.get("actual_pace") or it.get("pace_target") or ""
                rec["items"].append(f"✓ {wt} · {km:.1f} km" + (f" @ {pace}/km" if pace else ""))
            else:
                rec["planned_km"] = round(rec["planned_km"] + p_km, 2)
                pace = it.get("pace_target") or ""
                rec["items"].append(f"📅 {wt} · {p_km:.1f} km" + (f" @ {pace}/km" if pace else ""))

    start_d = min(all_dates) if all_dates else today
    start_ym = (start_d.year, start_d.month)
    end_d = max([today] + all_dates)
    end_ym = (end_d.year, end_d.month)

    months = []
    y, m = start_ym
    while (y, m) <= end_ym:
        label = f"Tháng {m}" if y == today.year else f"T{m}/{y}"
        months.append({"key": f"{y:04d}-{m:02d}", "year": y, "month": m, "label": label})
        m += 1
        if m > 12:
            m = 1
            y += 1

    default_key = f"{today.year:04d}-{today.month:02d}"
    if not any(x["key"] == default_key for x in months):
        default_key = months[-1]["key"]

    payload = {
        "today": today.isoformat(),
        "default_month": default_key,
        "months": months,
        "events": day_events,
    }
    html_code = _MONTH_CAL_TEMPLATE.replace("__DATA_JSON__", _safe_json(payload))
    render_iframe(html_code, height=462)
