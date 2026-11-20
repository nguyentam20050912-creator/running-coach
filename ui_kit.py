# -*- coding: utf-8 -*-
"""ui_kit.py - Giao diện sáng, gọn cho AI Running Coach Pro (tông hồng-đỏ, thẻ bo tròn, mật độ cao)."""
from datetime import timedelta
from html import escape
import streamlit as st

DAY_ORDER = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
DAY_SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
TYPE_COLORS = {
    "Easy Run": "#16A34A", "Tempo": "#D97706", "Interval": "#DB2777", "Long Run": "#7C3AED",
    "Rest": "#94A3B8", "Walk": "#2563EB", "Threshold": "#DC2626",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap');

:root {
    --ink: #2A1F1F; --ink-2: #6F6060; --ink-3: #9A8A8A;
    --line: #F0DEDC; --line-2: #E6CFCC;
    --accent: #D92D20; --accent-d: #B42318; --accent-soft: #FDECEA; --accent-wash: #FFF6F5;
    --surface: #FFFFFF;
    --ok: #16A34A; --warn: #D97706; --info: #2563EB;
}
@property --p { syntax: '<integer>'; inherits: true; initial-value: 0; }
@keyframes rc-grow { from { width: 0; } }
@keyframes rc-ring { from { --p: 0; } to { --p: var(--target); } }
@keyframes rc-in   { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* ---------- Nền & khung trang ---------- */
.stApp {
    color: var(--ink);
    background:
        radial-gradient(900px 420px at 0% 0%, #FFE3E0 0%, transparent 62%),
        radial-gradient(760px 380px at 100% 0%, #FFEFE9 0%, transparent 58%),
        #FFFAF9 !important;
    background-attachment: fixed !important;
}
.stApp :where(p, span, div, label, li, a, h1, h2, h3, h4, h5, h6, input, textarea, button, th, td, summary):not([data-testid="stIconMaterial"]):not([class*="material" i]) {
    font-family: 'Nunito', -apple-system, 'Segoe UI', sans-serif;
}
header[data-testid="stHeader"] { background: transparent !important; height: 2.4rem !important; }
.block-container, [data-testid="stMainBlockContainer"] {
    padding: 2.6rem 1.5rem 1rem !important; max-width: 1320px !important;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"] { gap: .6rem; }
hr { margin: .55rem 0 !important; border-color: var(--line) !important; }

/* ---------- Chữ ---------- */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { letter-spacing: -.01em; color: var(--ink); }
[data-testid="stHeading"] h2, [data-testid="stHeading"] h3 { font-size: 14.5px !important; font-weight: 800 !important; padding: .1rem 0 !important; margin: 0 !important; }
[data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
[data-testid="stMarkdownContainer"] p { font-size: 13.5px; line-height: 1.5; margin-bottom: .3rem; }
[data-testid="stMarkdownContainer"] p:last-child { margin-bottom: 0; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: 12px !important; color: var(--ink-2) !important; }
[data-testid="stWidgetLabel"] p, label[data-testid="stWidgetLabel"] { font-size: 12px !important; font-weight: 700 !important; color: var(--ink-2) !important; }
[data-testid="stWidgetLabel"] { margin-bottom: 2px !important; min-height: 0 !important; }

/* ---------- Ô nhập liệu ---------- */
.stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea { font-size: 13px !important; color: var(--ink) !important; }
.stTextInput div[data-baseweb="input"], .stNumberInput div[data-baseweb="input"], .stDateInput div[data-baseweb="input"],
.stTextArea div[data-baseweb="textarea"], .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {
    background: #fff !important; border-color: var(--line-2) !important; border-radius: 10px !important; min-height: 34px !important;
}
.stTextInput input, .stNumberInput input, .stDateInput input { padding-top: .3rem !important; padding-bottom: .3rem !important; }
.stSelectbox div[data-baseweb="select"] > div { font-size: 13px !important; }
.stTextInput div[data-baseweb="input"]:focus-within, .stNumberInput div[data-baseweb="input"]:focus-within,
.stTextArea div[data-baseweb="textarea"]:focus-within, .stSelectbox div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(217,45,32,.12) !important;
}
.stCheckbox label, .stCheckbox p { font-size: 13px !important; }

/* ---------- Nút ---------- */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
    min-height: 34px; padding: .2rem .85rem; font-size: 13px; font-weight: 700; border-radius: 10px;
    background: #fff; color: var(--ink); border: 1px solid var(--line-2); transition: border-color .15s, background .15s, transform .1s;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
    border-color: var(--accent); color: var(--accent-d); background: var(--accent-wash);
}
.stButton > button:active { transform: scale(.98); }
button[kind="primary"], button[data-testid="stBaseButton-primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {
    background: var(--accent) !important; color: #fff !important; border: 1px solid var(--accent-d) !important;
    box-shadow: 0 4px 12px -4px rgba(217,45,32,.55) !important;
}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover { background: var(--accent-d) !important; color: #fff !important; }
button[kind="primary"] p, button[data-testid="stBaseButton-primary"] p { color: #fff !important; }

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap: 2px !important; background: transparent !important; border-bottom: 1px solid var(--line); padding: 0 !important; }
.stTabs [data-baseweb="tab"] { height: 36px !important; padding: 0 14px !important; background: transparent !important; }
.stTabs [data-baseweb="tab"] p { font-size: 13px !important; font-weight: 700 !important; color: var(--ink-2) !important; }
.stTabs [aria-selected="true"] p { color: var(--accent-d) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--accent) !important; height: 2.5px !important; }
.stTabs [data-baseweb="tab-border"] { background: transparent !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: .7rem !important; }

/* ---------- Expander / form / alert / metric / bảng ---------- */
[data-testid="stExpander"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 12px !important; margin-bottom: .1rem; overflow: hidden; }
[data-testid="stExpander"] details summary { padding: .4rem .75rem !important; font-size: 13px !important; font-weight: 700 !important; }
[data-testid="stExpander"] details summary p { font-size: 13px !important; font-weight: 700 !important; }
[data-testid="stExpander"] details summary:hover { color: var(--accent-d) !important; background: var(--accent-wash); }
[data-testid="stExpanderDetails"] { padding: .35rem .75rem .65rem !important; }
[data-testid="stForm"] { border: 1px solid var(--line) !important; border-radius: 12px !important; padding: .7rem .8rem !important; background: #fff; }
[data-testid="stAlert"] { border-radius: 10px !important; padding: .4rem .7rem !important; font-size: 13px !important; }
[data-testid="stAlert"] p { font-size: 13px !important; margin: 0 !important; }
[data-testid="stMetric"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 12px !important; padding: 8px 12px !important; }
[data-testid="stMetricLabel"] p { font-size: 11.5px !important; font-weight: 700 !important; color: var(--ink-2) !important; }
[data-testid="stMetricValue"] { font-size: 1.15rem !important; font-weight: 800 !important; line-height: 1.2 !important; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
[class*="st-key-card-"] [data-testid="stForm"] { border: none !important; padding: 0 !important; }
[class*="st-key-card-"] { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: .65rem .8rem; }
[data-testid="stFileUploader"] section { padding: .5rem .75rem !important; border-radius: 10px !important; background: var(--accent-wash) !important; border: 1px dashed var(--line-2) !important; }
[data-testid="stFileUploaderDropzoneInstructions"] span { font-size: 12px !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFEDEA 0%, #FFF8F7 38%, #FFFFFF 100%) !important;
    border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebarUserContent"], [data-testid="stSidebarContent"] > div:first-child { padding-top: .9rem !important; }
[data-testid="stSidebarUserContent"] { padding-left: 1rem !important; padding-right: 1rem !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .45rem !important; }
.rc-side-h { display: flex; align-items: baseline; justify-content: space-between; margin: .3rem 0 -.1rem; font-size: 13.5px; font-weight: 800; }
.rc-side-h small { font-size: 11.5px; font-weight: 600; color: var(--ink-2); max-width: 55%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ---------- Thanh tiêu đề ---------- */
.rc-top { display: flex; align-items: center; justify-content: space-between; gap: 10px 16px; flex-wrap: wrap;
    padding: 8px 14px; border-radius: 14px; background: rgba(255,255,255,.86); border: 1px solid var(--line); backdrop-filter: blur(6px); }
.rc-top .l { display: flex; align-items: center; gap: 10px; min-width: 0; }
.rc-logo { width: 30px; height: 30px; flex: none; border-radius: 9px; background: var(--accent); color: #fff; display: grid; place-items: center; font-size: 16px; }
.rc-top .t { font-size: 15px; font-weight: 800; letter-spacing: -.01em; line-height: 1.2; }
.rc-top .s { font-size: 11.5px; color: var(--ink-2); display: flex; gap: 4px 14px; flex-wrap: wrap; }
.rc-top .s b { color: var(--ink); font-weight: 700; }
.rc-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.rc-chip { padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; background: #F4EFEF; color: var(--ink-2); white-space: nowrap; }
.rc-chip.acc { background: var(--accent-soft); color: var(--accent-d); }
.rc-chip.blue { background: #EEF4FF; color: #1D4ED8; }
.rc-chip.ok { background: #ECFDF3; color: #067647; }
.rc-chip.warn { background: #FFF4E5; color: #B45309; }

/* ---------- Tiêu đề mục & thẻ ---------- */
.rc-sec { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 2px 0 6px; }
.rc-sec span { font-size: 14.5px; font-weight: 800; letter-spacing: -.01em; }
.rc-sec em { font-style: normal; font-size: 11.5px; font-weight: 800; color: var(--ink-2); background: #F6EDEC; padding: 1px 8px; border-radius: 999px; }
.rc-sec .lk { font-size: 12px; font-weight: 700; color: var(--accent-d); background: none; padding: 0; }
.rc-card { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 10px 14px; animation: rc-in .35s ease both; }
.rc-card .sub { font-size: 12px; color: var(--ink-2); margin: -2px 0 4px; }
.rc-empty { border: 1px dashed var(--line-2); border-radius: 14px; padding: 16px; text-align: center; background: rgba(255,255,255,.6); }
.rc-empty b { font-size: 14px; } .rc-empty div { font-size: 12.5px; color: var(--ink-2); margin-top: 2px; }

/* ---------- Thẻ "Hôm nay" ---------- */
.rc-today { position: relative; overflow: hidden; padding: 12px 16px 12px; border-radius: 16px;
    background: linear-gradient(135deg, #FDE4E1 0%, #FFF1EF 60%, #FFF8F7 100%); border: 1px solid #F6D0CC; animation: rc-in .35s ease both; }
.rc-today::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px; background: var(--c); }
.rc-today .kick { font-size: 12px; font-weight: 800; color: var(--accent-d); display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.rc-today .ttl { font-size: 20px; font-weight: 800; letter-spacing: -.02em; margin: 3px 0 1px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rc-today .ttl i { font-style: normal; font-size: 11px; font-weight: 800; padding: 2px 9px; border-radius: 999px; color: #fff; background: var(--c); }
.rc-today .meta { font-size: 13px; color: var(--ink-2); }
.rc-today .note { font-size: 12.5px; color: var(--ink); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.rc-today .prog { display: flex; justify-content: space-between; font-size: 12px; color: var(--ink-2); margin-top: 8px; }
.rc-today .prog b { color: var(--ink); font-weight: 800; }

.rc-bar { height: 6px; border-radius: 999px; background: rgba(42,31,31,.09); overflow: hidden; margin: 4px 0 2px; }
.rc-bar > i { display: block; height: 100%; width: var(--w); border-radius: 999px; background: var(--c); animation: rc-grow .9s cubic-bezier(.2,.8,.2,1) both; }

/* ---------- KPI ---------- */
.rc-kpis { display: grid; grid-template-columns: repeat(var(--cols, 2), minmax(0, 1fr)); gap: 8px; }
.rc-kpi { display: flex; align-items: center; gap: 9px; padding: 8px 10px; border-radius: 12px; background: #fff; border: 1px solid var(--line); animation: rc-in .35s ease both; }
.rc-kpi .ic { width: 30px; height: 30px; flex: none; border-radius: 9px; display: grid; place-items: center; font-size: 15px; background: color-mix(in srgb, var(--c) 14%, #fff); }
.rc-kpi .lb { font-size: 11px; font-weight: 700; color: var(--ink-2); line-height: 1.2; }
.rc-kpi .val { font-size: 18px; font-weight: 800; letter-spacing: -.02em; line-height: 1.2; }
.rc-kpi .val small { font-size: 11px; font-weight: 700; color: var(--ink-2); margin-left: 3px; }

/* ---------- Danh sách "Cần chú ý" / "Đang theo dõi" ---------- */
.rc-list { background: #fff; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; animation: rc-in .35s ease both; }
.rc-row { display: flex; gap: 10px; align-items: flex-start; padding: 8px 12px; }
.rc-row + .rc-row { border-top: 1px solid var(--line); }
.rc-row .ic { width: 28px; height: 28px; flex: none; border-radius: 9px; display: grid; place-items: center; font-size: 14px; background: var(--accent-soft); }
.rc-row .bd { min-width: 0; flex: 1; }
.rc-row .tt { font-size: 13px; font-weight: 800; line-height: 1.3; }
.rc-row .sb { font-size: 11.5px; color: var(--ink-2); margin-top: 1px; }
.rc-row .tg { display: inline-block; margin-top: 3px; font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 999px; background: #F6EDEC; color: var(--ink-2); }
.rc-row .tg.acc { background: #FFF1E6; color: #B45309; }
.rc-none { padding: 10px 12px; font-size: 12.5px; color: var(--ink-2); }

/* ---------- Dải tuần ---------- */
.rc-week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; }
.rc-day { position: relative; min-height: 62px; padding: 6px 4px; border-radius: 12px; text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 1px;
    background: rgba(255,255,255,.7); border: 1px dashed var(--line-2); color: var(--ink-3); }
.rc-day .d { font-size: 11px; font-weight: 800; letter-spacing: .02em; }
.rc-day .w { font-size: 11.5px; font-weight: 700; line-height: 1.2; }
.rc-day .k { font-size: 15px; font-weight: 800; line-height: 1.15; }
.rc-day .k small { font-size: 10.5px; font-weight: 700; opacity: .75; }
.rc-day.on { border: 1px solid color-mix(in srgb, var(--c) 40%, #fff); background: color-mix(in srgb, var(--c) 11%, #fff); color: color-mix(in srgb, var(--c) 82%, #000); }
.rc-day.on.done { background: var(--c); border-color: var(--c); color: #fff; }
.rc-day.on.today { box-shadow: 0 0 0 2px #fff, 0 0 0 4px var(--c); }
.rc-day.done::after { content: "✓"; position: absolute; top: 3px; right: 6px; font-size: 11px; font-weight: 900; }
@media (max-width: 700px) { .rc-week { grid-template-columns: repeat(4, 1fr); } }

/* ---------- Bản đồ nhiệt ---------- */
.rc-heatwrap { display: flex; gap: 22px; align-items: flex-end; flex-wrap: wrap; margin-top: 6px; }
.rc-heatleft { max-width: 100%; overflow-x: auto; padding-bottom: 2px; }
.rc-heat { display: grid; grid-template-rows: repeat(7, 12px); grid-auto-flow: column; grid-auto-columns: 12px; gap: 4px; }
.rc-heat i, .rc-legend i { display: block; width: 12px; height: 12px; border-radius: 50%; background: #F8ECEB; }
.rc-heat i.l1, .rc-legend i.l1 { background: #F7CFCB; }
.rc-heat i.l2, .rc-legend i.l2 { background: #EE9F98; }
.rc-heat i.l3, .rc-legend i.l3 { background: #E0584E; }
.rc-heat i.l4, .rc-legend i.l4 { background: #C21F1A; }
.rc-heat i.fut { background: transparent; box-shadow: inset 0 0 0 1px #F3E3E1; }
.rc-hfoot { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--ink-2); margin-top: 5px; }
.rc-hstats { display: flex; gap: 16px; }
.rc-hstats div { display: flex; flex-direction: column; }
.rc-hstats b { font-size: 19px; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; }
.rc-hstats span { font-size: 11px; color: var(--ink-2); font-weight: 700; }
.rc-legend { display: flex; align-items: center; gap: 4px; font-size: 11.5px; color: var(--ink-2); margin-top: 6px; }
.rc-legend i { width: 10px; height: 10px; }

/* ---------- Đường đua ---------- */
.rc-track { padding: 8px 14px 9px; border-radius: 14px; background: #fff; border: 1px solid var(--line); }
.rc-track .row { display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; color: var(--ink-2); }
.rc-track .lane { position: relative; height: 8px; margin: 18px 0 5px; border-radius: 999px; background: repeating-linear-gradient(90deg, #F2E2E0 0 10px, transparent 10px 16px); }
.rc-track .lane > i { position: absolute; left: 0; top: 0; height: 100%; width: var(--w); border-radius: 999px; background: linear-gradient(90deg, #F59E0B, var(--accent)); animation: rc-grow 1.1s cubic-bezier(.2,.8,.2,1) both; }
.rc-track .runner { position: absolute; top: -17px; left: var(--w); transform: translateX(-50%); font-size: 16px; }
.rc-track .flag { position: absolute; top: -17px; right: -2px; font-size: 16px; }

/* ---------- Vòng tiến độ ---------- */
.rc-ring-wrap { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-radius: 14px; background: #fff; border: 1px solid var(--line); }
.rc-ring { --target: 0; width: 60px; height: 60px; flex: none; border-radius: 50%; display: grid; place-items: center;
    background: conic-gradient(var(--c) calc(var(--p) * 1%), #F2E2E0 0); animation: rc-ring 1s cubic-bezier(.2,.8,.2,1) both; }
.rc-ring::before { content: ""; grid-area: 1/1; width: 46px; height: 46px; border-radius: 50%; background: #fff; }
.rc-ring span { grid-area: 1/1; z-index: 1; font-weight: 800; font-size: 13px; counter-reset: n var(--p); }
.rc-ring span::after { content: counter(n) "%"; }
.rc-ring-wrap .t { font-weight: 800; font-size: 13.5px; } .rc-ring-wrap .s { font-size: 12px; color: var(--ink-2); }

/* ---------- Hộp lời khuyên HLV & thẻ giày ---------- */
.hlv-box { font-size: 13.5px; line-height: 1.55; color: var(--ink); background: linear-gradient(135deg, #FFF1EF, #FFFFFF); padding: 10px 14px; border-radius: 12px;
    border: 1px solid #F6D0CC; border-left: 4px solid var(--accent); }
.shoe-card { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 9px 12px; margin-bottom: 6px; }
.shoe-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; }

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


# ----------------------------------------------------------------- khối giao diện
def topbar(title, meta=None, chips=None):
    """Thanh tiêu đề 1 hàng thay cho hero-banner cũ. meta: [(nhãn, giá trị)], chips: [(text, tone)]."""
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
        cards.append(
            f'<div class="rc-kpi" style="--c:{it.get("color", "#D92D20")};animation-delay:{i * 0.05:.2f}s">'
            f'<span class="ic">{escape(str(it.get("icon", "🏃")))}</span>'
            f'<div><div class="lb">{escape(str(it["label"]))}</div>'
            f'<div class="val">{escape(str(it["value"]))}{unit}</div></div></div>'
        )
    _html(f'<div class="rc-kpis" style="--cols:{int(cols)}">{"".join(cards)}</div>')


def ring_card(pct, title, sub="", color="#16A34A"):
    p = _clamp_pct(pct)
    _html(
        f'<div class="rc-ring-wrap"><div class="rc-ring" style="--target:{p};--c:{color}"><span></span></div>'
        f'<div><div class="t">{escape(title)}</div><div class="s">{escape(sub)}</div></div></div>'
    )


def attention_list(items, empty_text="Không cần bạn xử lý ngay."):
    """items: [{icon, title, tag, sub}] -> danh sách việc cần chú ý."""
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
    """items: [{icon, title, sub, pct, color, tag}] -> danh sách theo dõi kèm thanh tiến độ nhỏ."""
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


def heat_card(by_date, today, weeks=5):
    """Hiển thị heatmap hoạt động chạy trong 1 tháng qua (5 tuần gần nhất, lưới T2–CN)."""
    from datetime import timedelta
    from html import escape
    import streamlit as st

    mon_this = today - timedelta(days=today.weekday())
    start_date = mon_this - timedelta(weeks=weeks - 1)
    end_grid = mon_this + timedelta(days=6)

    period_vals = [
        float(v) for d, v in (by_date or {}).items()
        if start_date <= d <= today and float(v or 0) > 0
    ]
    total_km = sum(period_vals)
    run_days = len(period_vals)
    longest_km = max(period_vals) if period_vals else 0.0
    scale_max = max(longest_km, 4.0)

    palette = ["#F8ECEB", "#F2B8B5", "#E67C73", "#D93829", "#B91C1C"]

    def dot_style(d, km):
        if d > today:
            return "background:transparent;border:1.5px solid #EAD7D5;"
        if km <= 0:
            lvl = 0
        else:
            ratio = km / scale_max
            lvl = 1 if ratio <= 0.25 else (2 if ratio <= 0.5 else (3 if ratio <= 0.75 else 4))
        ring = "box-shadow:0 0 0 2px rgba(217,45,32,0.35);" if d == today else ""
        return f"background:{palette[lvl]};border:1.5px solid transparent;{ring}"

    day_headers = "".join(
        f'<span class="hc-dow">{lbl}</span>' for lbl in ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    )

    cells = []
    cur = start_date
    while cur <= end_grid:
        km = float((by_date or {}).get(cur, 0.0) or 0.0)
        tip = f"{cur:%d/%m/%Y}" + (" (Hôm nay)" if cur == today else "")
        tip += " · Chưa tới" if cur > today else (f" · {km:.1f} km" if km > 0 else " · Nghỉ")
        cells.append(f'<span class="hc-dot" style="{dot_style(cur, km)}" title="{escape(tip)}"></span>')
        cur += timedelta(days=1)

    legend_dots = "".join(f'<i style="background:{c};"></i>' for c in palette)
    total_km_str = f"{int(round(total_km))}" if abs(total_km - round(total_km)) < 0.05 else f"{total_km:.1f}"

    st.markdown(f"""
    <style>
    .hc-wrap{{background:rgba(255,255,255,0.88);border:1px solid #F0DEDC;border-radius:16px;padding:18px 22px;margin-top:10px}}
    .hc-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}}
    .hc-title{{font-size:16px;font-weight:800;color:#2A1F1F;line-height:1.25}}
    .hc-sub{{font-size:12.5px;color:#6F6060;margin-top:3px}}
    .hc-pill{{background:#F8ECEB;color:#5C4B4B;font-size:12px;font-weight:700;padding:5px 12px;border-radius:999px;white-space:nowrap}}
    .hc-body{{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:24px;margin-top:14px}}
    .hc-cal{{min-width:215px}}
    .hc-grid{{display:grid;grid-template-columns:repeat(7,22px);gap:7px;align-items:center;justify-items:center}}
    .hc-dow{{font-size:11px;font-weight:700;color:#9A8A8A;margin-bottom:2px}}
    .hc-dot{{width:20px;height:20px;border-radius:50%;display:inline-block;transition:transform .15s ease}}
    .hc-dot:hover{{transform:scale(1.18)}}
    .hc-dates{{display:flex;justify-content:space-between;font-size:12px;color:#6F6060;margin-top:8px}}
    .hc-legend{{display:flex;align-items:center;gap:5px;font-size:12px;color:#6F6060;margin-top:10px}}
    .hc-legend i{{width:11px;height:11px;border-radius:50%;display:inline-block}}
    .hc-stats{{display:flex;align-items:flex-end;gap:26px;padding-bottom:2px}}
    .hc-stat b{{display:block;font-size:24px;font-weight:800;color:#1F1616;line-height:1.1}}
    .hc-stat span{{font-size:12.5px;color:#6F6060}}
    </style>
    <div class="hc-wrap">
      <div class="hc-top">
        <div>
          <div class="hc-title">Hoạt động chạy của bạn</div>
          <div class="hc-sub">Km đã hoàn thành mỗi ngày</div>
        </div>
        <span class="hc-pill">1 tháng qua</span>
      </div>
      <div class="hc-body">
        <div class="hc-cal">
          <div class="hc-grid">{day_headers}{"".join(cells)}</div>
          <div class="hc-dates"><span>{start_date:%d/%m/%Y}</span><span>{today:%d/%m/%Y}</span></div>
          <div class="hc-legend"><span>Ít</span>{legend_dots}<span>Nhiều</span></div>
        </div>
        <div class="hc-stats">
          <div class="hc-stat"><b>{total_km_str}</b><span>km</span></div>
          <div class="hc-stat"><b>{run_days}</b><span>buổi chạy</span></div>
          <div class="hc-stat"><b>{longest_km:.1f}</b><span>km dài nhất</span></div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


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
