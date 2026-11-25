# -*- coding: utf-8 -*-
"""AI Running Coach Pro - giao diện Streamlit (Glassmorphism, Telemetry FIT/GPX & Gear Tracker)."""
import importlib
import inspect
import json
import os
import struct
import xml.etree.ElementTree as ET
from datetime import timedelta
from html import escape

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import coach_core as cc
import ui_kit

importlib.reload(cc)
importlib.reload(ui_kit)

DATA_DIR = os.environ.get("RUNNING_DATA_DIR", "data")

# ==========================================
# 1. CẤU HÌNH TRANG & CSS
# ==========================================
st.set_page_config(
    page_title="AI Running Coach Pro",
    page_icon="🏃‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui_kit.inject_ui()


# ==========================================
# 2. TIỆN ÍCH GIAO DIỆN & BIỂU ĐỒ
# ==========================================
def stretch_kwargs(func):
    params = inspect.signature(func).parameters
    if "width" in params and (
        isinstance(params["width"].default, str) or "Width" in str(params["width"].annotation)
    ):
        return {"width": "stretch"}
    if "use_container_width" in params:
        return {"use_container_width": True}
    return {}


BTN_STRETCH = stretch_kwargs(st.button)
EDITOR_STRETCH = stretch_kwargs(st.data_editor)


def stretch_button(label, **kwargs):
    return st.button(label, **BTN_STRETCH, **kwargs)


RED, GRAY, TEXT = "#D92D20", "#F3CFCB", "#3B2F2F"


def _style(chart):
    return (chart.configure(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=TEXT, titleColor=TEXT, gridColor="#F3E4E2",
                            domainColor="#E6CFCC", tickColor="#E6CFCC", labelFontSize=11, titleFontSize=11)
            .configure_legend(labelColor=TEXT, titleColor=TEXT))


def weekly_chart(rows):
    df = pd.DataFrame(rows)
    df["text"] = df.apply(lambda r: f"{r['done_km']:g}/{r['planned_km']:g}", axis=1)
    base = alt.Chart(df).encode(x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)))
    planned = base.mark_bar(color=GRAY, size=26, cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        y=alt.Y("planned_km:Q", title="km", scale=alt.Scale(domainMin=0, domainMax=max(df["planned_km"].max(), df["done_km"].max(), 1) * 1.22)),
        tooltip=[alt.Tooltip("label:N", title="Tuần"), alt.Tooltip("planned_km:Q", title="Kế hoạch (km)"),
                 alt.Tooltip("done_km:Q", title="Đã chạy (km)")])
    done = base.mark_bar(color=RED, size=26, cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(y="done_km:Q")
    label = base.mark_text(dy=-8, color=TEXT, fontWeight="bold", fontSize=11).encode(y="planned_km:Q", text="text:N")
    return _style((planned + done + label).properties(height=170))


def pace_chart(rows):
    df = pd.DataFrame([{"label": r["label"], "sec": r["avg_pace_min"] * 60} for r in rows if r["avg_pace_min"]])
    if df.empty:
        return None
    fmt = "floor(datum.value/60) + ':' + (datum.value%60<10 ? '0' : '') + floor(datum.value%60)"
    df["pace"] = df["sec"].apply(cc.sec_to_pace)
    base = alt.Chart(df).encode(
        x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("sec:Q", title="phút/km", scale=alt.Scale(zero=False, reverse=True, nice=True),
                axis=alt.Axis(labelExpr=fmt)),
        tooltip=[alt.Tooltip("label:N", title="Tuần"), alt.Tooltip("pace:N", title="Pace TB")])
    line = base.mark_line(color="#3B82F6", strokeWidth=2.5, point=alt.OverlayMarkDef(color="#3B82F6", size=60, filled=True))
    text = base.mark_text(dy=-14, color=TEXT, fontWeight="bold", fontSize=11).encode(text="pace:N")
    return _style((line + text).properties(height=170))


def dist_chart(dist):
    df = pd.DataFrame({"type": list(dist.keys()), "km": list(dist.values())})
    base = alt.Chart(df).encode(y=alt.Y("type:N", sort="-x", title=None))
    bars = base.mark_bar(color=RED, size=16, cornerRadiusTopRight=6, cornerRadiusBottomRight=6).encode(
        x=alt.X("km:Q", title="km", scale=alt.Scale(domainMin=0, domainMax=max(df["km"].max(), 1) * 1.22)),
        tooltip=["type:N", "km:Q"])
    text = base.mark_text(align="left", dx=6, color=TEXT, fontWeight="bold", fontSize=11).encode(x="km:Q", text="km:Q")
    return _style((bars + text).properties(height=170))


def telemetry_split_charts(splits):
    """Vẽ biểu đồ Pace, Nhịp tim, Cadence và Độ cao từng km từ dữ liệu .fit / .gpx."""
    df = pd.DataFrame(splits)
    charts = []

    if "pace_sec" in df.columns and (df["pace_sec"] > 0).any():
        pace_df = df[df["pace_sec"] > 0].copy()
        fmt = "floor(datum.value/60) + ':' + (datum.value%60<10 ? '0' : '') + floor(datum.value%60)"
        base_p = alt.Chart(pace_df).encode(
            x=alt.X("km_label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("pace_sec:Q", title="phút/km", scale=alt.Scale(zero=False, reverse=True, nice=True),
                    axis=alt.Axis(labelExpr=fmt)),
            tooltip=[alt.Tooltip("km_label:N", title="Split"), alt.Tooltip("pace_str:N", title="Pace")],
        )
        c_p = _style((base_p.mark_line(color="#F59E0B", strokeWidth=2.5, point=alt.OverlayMarkDef(color="#F59E0B", size=55, filled=True))
                      + base_p.mark_text(dy=-13, color=TEXT, fontWeight="bold", fontSize=11).encode(text="pace_str:N")).properties(height=160))
        charts.append(("⚡ Pace từng km (phút/km)", c_p))

    if "avg_hr" in df.columns and df["avg_hr"].notna().any():
        hr_df = df.dropna(subset=["avg_hr"])
        base_hr = alt.Chart(hr_df).encode(
            x=alt.X("km_label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("avg_hr:Q", title="bpm", scale=alt.Scale(zero=False, nice=True)),
            tooltip=[alt.Tooltip("km_label:N", title="Split"), alt.Tooltip("avg_hr:Q", title="Nhịp tim (bpm)"),
                     alt.Tooltip("pace_str:N", title="Pace")],
        )
        c_hr = _style((base_hr.mark_line(color="#D92D20", strokeWidth=2.5, point=alt.OverlayMarkDef(color="#D92D20", size=55, filled=True))
                       + base_hr.mark_text(dy=-12, color=TEXT, fontWeight="bold", fontSize=11).encode(text="avg_hr:Q")).properties(height=160))
        charts.append(("❤️ Nhịp tim trung bình từng km (bpm)", c_hr))

    if "avg_cadence" in df.columns and df["avg_cadence"].notna().any():
        cad_df = df.dropna(subset=["avg_cadence"])
        base_cad = alt.Chart(cad_df).encode(
            x=alt.X("km_label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("avg_cadence:Q", title="spm", scale=alt.Scale(zero=False, nice=True)),
            tooltip=[alt.Tooltip("km_label:N", title="Split"), alt.Tooltip("avg_cadence:Q", title="Guồng chân (spm)"),
                     alt.Tooltip("pace_str:N", title="Pace")],
        )
        c_cad = _style((base_cad.mark_line(color="#3B82F6", strokeWidth=2.5, point=alt.OverlayMarkDef(color="#3B82F6", size=55, filled=True))
                        + base_cad.mark_text(dy=-12, color=TEXT, fontWeight="bold", fontSize=11).encode(text="avg_cadence:Q")).properties(height=160))
        charts.append(("👟 Guồng chân / Cadence từng km (spm)", c_cad))

    if "ele_gain" in df.columns and (df["ele_gain"] > 0).any():
        base_ele = alt.Chart(df).encode(
            x=alt.X("km_label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("ele_gain:Q", title="mét (m)", scale=alt.Scale(domainMin=0, domainMax=max(df["ele_gain"].max(), 1) * 1.25)),
            tooltip=[alt.Tooltip("km_label:N", title="Split"), alt.Tooltip("ele_gain:Q", title="Leo dốc (m)"),
                     alt.Tooltip("pace_str:N", title="Pace")],
        )
        c_ele = _style((base_ele.mark_bar(color="#10B981", size=20, cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
                        + base_ele.mark_text(dy=-8, color=TEXT, fontWeight="bold", fontSize=11).encode(text="ele_gain:Q")).properties(height=160))
        charts.append(("⛰️ Độ cao tích lũy / Elevation Gain từng km (m)", c_ele))

    return charts


def format_splits_df(splits):
    """Định dạng bảng Splits sang tiếng Việt gọn gàng, ẩn cột cảm biến không có dữ liệu."""
    df = pd.DataFrame(splits)
    if df.empty:
        return df
    cols = []
    rename_map = {
        "km_label": "Chặng",
        "distance_km": "Quãng đường (km)",
        "pace_str": "Pace (/km)",
        "avg_hr": "Nhịp tim TB (bpm)",
        "avg_cadence": "Guồng chân (spm)",
        "ele_gain": "Leo dốc (m)",
    }
    for key in rename_map:
        if key in df.columns and df[key].notna().any():
            cols.append(key)
    return df[cols].rename(columns=rename_map)


def show_chart(chart):
    try:
        st.altair_chart(chart, theme=None, **stretch_kwargs(st.altair_chart))
    except TypeError:
        st.altair_chart(chart, **stretch_kwargs(st.altair_chart))


DASHBOARD_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
:root{
  color-scheme:light;
  --ux-ink:#2A1F1F; --ux-ink-2:#6F6060; --ux-ink-3:#9A8A8A; --ux-line:#F0DEDC;
  --ux-accent:#D92D20; --ux-wash:#FFF6F5; --ux-surface-2:#FDECEA;
}
html,body{margin:0;background:transparent}
.ux,.ux *,.ux *::before,.ux *::after{box-sizing:border-box}
.ux{font-family:'Nunito',-apple-system,'Segoe UI',sans-serif;color:var(--ux-ink);display:flex;justify-content:center}
.ux button{cursor:pointer;font:inherit;color:inherit;border:none;background:none}
.u213{position:relative;width:100%;height:268px;border-radius:14px;overflow:hidden;background:#fff;box-shadow:0 0 0 1px var(--ux-line)}
.u213-tl{position:absolute;left:12px;right:12px;top:10px;display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.u213-tb{position:relative;display:flex;flex-direction:row;align-items:center;justify-content:center;gap:6px;padding:7px 4px 11px;border-radius:10px;color:var(--ux-ink-3);font-size:12.5px;font-weight:800;transition:color .25s,background .25s}
.u213-tb svg{width:15px;height:15px}
.u213-tb.is-on{color:var(--ux-accent);background:var(--ux-surface-2)}
.u213-tb>i{position:absolute;left:12px;right:12px;bottom:4px;height:2px;border-radius:2px;background:var(--ux-line);overflow:hidden}
.u213-tb>i b{display:block;height:100%;border-radius:2px;background:var(--ux-accent);transform:scaleX(0);transform-origin:0 50%}
.u213-pv{position:absolute;left:12px;right:12px;top:52px;bottom:12px;border-radius:12px;background:var(--ux-wash);box-shadow:0 0 0 1px var(--ux-line);overflow:hidden}
.u213-pn{position:absolute;inset:0;padding:10px 14px;opacity:0;transform:translateY(8px);transition:opacity .35s,transform .4s cubic-bezier(.2,.8,.2,1);pointer-events:none}
.u213-pn.is-on{opacity:1;transform:none}
.u213-pn small{font-size:11.5px;font-weight:800;color:var(--ux-ink-2)}
.u213-wk{position:relative;display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-top:6px;height:calc(100% - 20px)}
.u213-wk>span{display:block;border-radius:8px;background:#fff;box-shadow:0 0 0 1px var(--ux-line);font-size:11px;font-weight:800;color:var(--ux-ink-3);text-align:center;padding-top:5px}
.u213-ev{position:absolute;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;text-align:center;border-radius:8px;padding:4px 3px;font-size:11.5px;font-weight:800;line-height:1.25;color:#fff;opacity:0;transform:translateY(-6px) scale(.94);transition:opacity .3s,transform .4s cubic-bezier(.3,1.4,.5,1);overflow:hidden}
.u213-ev small{font-size:10.5px;font-weight:700;color:#fff;opacity:.92}
.u213-ev.is-done{box-shadow:0 0 0 2px #fff inset}
.u213-pn.is-play .u213-ev{opacity:1;transform:none}
.u213-dh{display:flex;align-items:center;gap:6px}
.u213-dh b{font-size:14px;font-weight:800;margin-right:auto}
.u213-dh em{font-style:normal;font-size:11px;font-weight:800;color:#2563EB}
.u213-sum{margin-top:8px;font-size:13px;line-height:1.55;color:var(--ux-ink);display:-webkit-box;-webkit-line-clamp:7;-webkit-box-orient:vertical;overflow:hidden}
.u213-kp{display:flex;align-items:baseline;gap:10px;margin-top:2px}
.u213-kp b{font-size:28px;font-weight:800;letter-spacing:-.02em}
.u213-kp span{font-size:12px;font-weight:800;color:#16A34A}
.u213-br{display:flex;align-items:flex-end;gap:10px;height:84px;margin-top:20px;border-bottom:1px solid var(--ux-line)}
.u213-br i{position:relative;flex:1;border-radius:5px 5px 1px 1px;background:rgba(217,45,32,.28);height:var(--h);transform:scaleY(0);transform-origin:50% 100%;transition:transform .6s cubic-bezier(.3,1.3,.5,1)}
.u213-br i:last-child{background:var(--ux-accent)}
.u213-pn.is-play .u213-br i{transform:none}
.u213-br i::after{content:attr(data-v);position:absolute;top:-16px;left:50%;transform:translateX(-50%);font-size:10.5px;font-style:normal;font-weight:800;color:var(--ux-ink-2)}
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
  var DUR = 4200, cur = -1, acc = 0, last = 0, hold = false, vis = true, raf = 0;
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
    raf = 0; if (!hold && vis) acc += Math.min(64, now - last); last = now;
    var p = Math.min(1, acc / DUR);
    T[cur].querySelector('b').style.transform = 'scaleX(' + p.toFixed(3) + ')';
    if (p >= 1) go((cur + 1) % T.length);
    if (vis) raf = requestAnimationFrame(tick);
  }
  function run() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); } }
  T.forEach(function (t, i) { t.addEventListener('click', function () { go(i); run(); }); });
  pv.addEventListener('pointerenter', function () { hold = true; });
  pv.addEventListener('pointerleave', function () { hold = false; });
  go(0); run();
})();
</script>
"""


def safe_json_for_script(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def render_dynamic_dashboard(completed_km, schedule_data, weekly_km, week_summary, completion_rate):
    html_code = (
        DASHBOARD_TEMPLATE
        .replace("__SCHEDULE_JSON__", safe_json_for_script(schedule_data))
        .replace("__WEEKLY_JSON__", safe_json_for_script(weekly_km))
        .replace("__SUMMARY_JSON__", safe_json_for_script(week_summary))
        .replace("__RATE__", str(int(completion_rate)))
        .replace("__COMPLETED_KM__", str(float(completed_km)))
    )
    if hasattr(st, "iframe"):
        st.iframe(html_code, height=276)
    else:
        components.html(html_code, height=276)


@st.cache_resource
def get_storage():
    return cc.Storage(DATA_DIR)


def persist(pid):
    get_storage().save_project(pid, st.session_state.projects[pid])


def get_valid_keys():
    keys = cc.get_configured_api_keys()
    if len(keys) > 1:
        rr = st.session_state.get("key_rr", 0) % len(keys)
        keys = keys[rr:] + keys[:rr]
        st.session_state["key_rr"] = rr + 1
    return keys


# ==========================================
# 3. TRẠNG THÁI & CALLBACK
# ==========================================
if "projects" not in st.session_state:
    _projects, _warn = get_storage().load_all()
    st.session_state.projects = _projects
    st.session_state.current_project_id = list(_projects.keys())[0]
    if _warn:
        st.session_state["load_warning"] = _warn


def _find_plan(pid, plan_id):
    proj = st.session_state.projects.get(pid)
    if not proj:
        return None
    return next((p for p in proj["plans"] if p["id"] == plan_id), None)


def cb_log_edit(pid, plan_id, widget_key):
    plan = _find_plan(pid, plan_id)
    proj = st.session_state.projects.get(pid)
    if plan is None or proj is None:
        return
    name_to_id = {s["name"]: s["id"] for s in proj.get("shoes", [])}
    cc.apply_log_edits(plan, st.session_state[widget_key].get("edited_rows", {}), shoe_name_to_id=name_to_id)
    persist(pid)


def cb_feedback(pid, plan_id, widget_key):
    plan = _find_plan(pid, plan_id)
    if plan is None:
        return
    plan["user_feedback"] = st.session_state[widget_key]
    persist(pid)


def cb_ask_delete(pid, plan_id):
    st.session_state["pending_del_plan"] = (pid, plan_id)


def cb_cancel_delete():
    st.session_state["pending_del_plan"] = None


def cb_delete_plan(pid, plan_id):
    proj = st.session_state.projects.get(pid)
    if proj:
        proj["plans"] = [p for p in proj["plans"] if p["id"] != plan_id]
        persist(pid)
    st.session_state["pending_del_plan"] = None


# ==========================================
# 4. SIDEBAR (ĐÃ TỐI GIẢN)
# ==========================================
_load_warn_msg = str(st.session_state.get("load_warning") or "").strip()
if _load_warn_msg:
    w_col1, w_col2 = st.columns([11, 1])
    w_col1.warning(_load_warn_msg)
    if w_col2.button("✕", key="dismiss_load_warn", help="Ẩn cảnh báo"):
        st.session_state["load_warning"] = ""
        st.rerun()

configured_keys_count = len(cc.get_configured_api_keys())

with st.sidebar:
    ui_kit.side_title("📁 Dự án")

    if st.session_state.current_project_id not in st.session_state.projects:
        st.session_state.current_project_id = list(st.session_state.projects.keys())[0]

    project_options = {pid: pdata["name"] for pid, pdata in st.session_state.projects.items()}
    selected_proj_id = st.selectbox(
        "Chọn Dự Án Hiện Tại:",
        options=list(project_options.keys()),
        format_func=lambda x: project_options[x],
        index=list(project_options.keys()).index(st.session_state.current_project_id),
    )
    st.session_state.current_project_id = selected_proj_id
    curr_project = st.session_state.projects[selected_proj_id]

    with st.expander("➕ Tạo Dự Án Mới"):
        with st.form("new_project_form"):
            new_p_name = st.text_input("Tên dự án")
            new_p_goal = st.selectbox("Mục tiêu", cc.GOALS)
            c_np1, c_np2 = st.columns(2)
            new_p_curr_pace = c_np1.text_input("Pace hiện tại", value="07:00")
            new_p_targ_pace = c_np2.text_input("Pace mục tiêu", value="05:30")
            new_p_dist = st.number_input("Max KM", min_value=1.0, value=10.0)
            new_p_has_race = st.checkbox("Có ngày thi đấu")
            new_p_race_date = st.date_input("Ngày giải", min_value=cc.today_vn())
            new_p_injuries = st.text_area("Chấn thương", value="Không có")
            new_p_notes = st.text_area("Ghi chú HLV", value="80% Easy")
            new_p_days = st.multiselect("Ngày rảnh", cc.ALL_DAYS, default=["Thứ 3", "Thứ 5", "Chủ Nhật"])

            if st.form_submit_button("Khởi Tạo"):
                if not new_p_name.strip():
                    st.error("Nhập tên dự án.")
                elif not (cc.validate_pace(new_p_curr_pace) and cc.validate_pace(new_p_targ_pace)):
                    st.error("Pace phải đúng định dạng mm:ss (vd 06:30).")
                elif not new_p_days:
                    st.error("Chọn ít nhất 1 ngày tập.")
                else:
                    new_id = cc.new_id()
                    race_dt_str = new_p_race_date.strftime("%Y-%m-%d") if new_p_has_race else ""
                    st.session_state.projects[new_id] = {
                        "name": new_p_name.strip(),
                        "created_at": cc.today_vn().isoformat(),
                        "profile": {
                            "goal": new_p_goal, "current_pace": new_p_curr_pace.strip(),
                            "target_pace": new_p_targ_pace.strip(), "target_time": "",
                            "max_distance": new_p_dist, "injuries": new_p_injuries, "notes": new_p_notes,
                            "days": new_p_days, "race_date": race_dt_str,
                        },
                        "shoes": [], "plans": [], "draft": None,
                    }
                    st.session_state.current_project_id = new_id
                    persist(new_id)
                    st.rerun()

    with st.expander("✏️ Đổi Tên / 🗑️ Xóa Dự Án"):
        rename_val = st.text_input("Đổi tên dự án:", value=curr_project["name"], key=f"rename_{selected_proj_id}")
        if stretch_button("Lưu tên mới", key=f"save_name_{selected_proj_id}"):
            if rename_val.strip() and rename_val.strip() != curr_project["name"]:
                curr_project["name"] = rename_val.strip()
                persist(selected_proj_id)
                st.rerun()
        st.divider()
        confirm_delete = st.checkbox(
            f"Xác nhận xóa '{curr_project['name']}'", key=f"confirm_del_{selected_proj_id}"
        )
        if stretch_button("❌ XÓA DỰ ÁN", type="primary", key=f"del_btn_{selected_proj_id}"):
            if len(st.session_state.projects) <= 1:
                st.error("Phải giữ lại ít nhất 1 dự án!")
            elif not confirm_delete:
                st.warning("Tick ô xác nhận trước khi xóa.")
            else:
                del st.session_state.projects[selected_proj_id]
                get_storage().delete_project(selected_proj_id)
                st.session_state.current_project_id = list(st.session_state.projects.keys())[0]
                st.rerun()

    with st.expander("💾 Sao lưu / Khôi phục"):
        st.download_button(
            "⬇️ Sao lưu tất cả (JSON)",
            data=json.dumps(st.session_state.projects, ensure_ascii=False, indent=2),
            file_name=f"running_backup_{cc.today_vn():%Y%m%d}.json", mime="application/json",
            key="dl_backup",
        )
        st.download_button(
            "⬇️ Xuất dự án này (CSV)",
            data=cc.project_to_csv(curr_project).encode("utf-8-sig"),
            file_name=f"{curr_project['name']}.csv", mime="text/csv", key="dl_csv",
        )
        up = st.file_uploader("Khôi phục từ file JSON", type="json", key="restore_file")
        if up is not None and stretch_button("Nhập vào (gộp, không ghi đè)", key="restore_btn"):
            try:
                added = cc.import_projects(st.session_state.projects, json.loads(up.getvalue().decode("utf-8")))
                for _pid, _pd in added.items():
                    st.session_state.projects[_pid] = _pd
                    persist(_pid)
                st.toast(f"Đã nhập {len(added)} dự án.", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Không nhập được: {str(e)[:200]}")

    ui_kit.side_title("🛠️ Hồ sơ", curr_project["name"])
    prof = curr_project["profile"]
    pid = selected_proj_id

    goal_idx = cc.GOALS.index(prof["goal"]) if prof.get("goal") in cc.GOALS else 0
    updated_goal = st.selectbox("Mục tiêu", cc.GOALS, index=goal_idx, key=f"p_goal_{pid}")
    goal_dist = cc.GOAL_DISTANCE_KM.get(updated_goal)

    c_p1, c_p2 = st.columns(2)
    updated_curr_pace = c_p1.text_input(
        "Pace hiện tại", value=prof.get("current_pace", "07:00"), key=f"p_cpace_{pid}",
        help="Pace race hiện tại của bạn ở cự ly mục tiêu (mm:ss/km).",
    )
    updated_time = c_p2.text_input(
        "Thời gian đích", value=prof.get("target_time", ""), key=f"p_ttime_{pid}",
        placeholder="mm:ss (vd: 59:30) hoặc h:mm:ss (vd: 1:55:00)",
        help="Nhập mm:ss (ví dụ 59:30 cho 10K) hoặc h:mm:ss (ví dụ 1:55:00 cho Half Marathon).",
    )
    time_given = bool(updated_time.strip())
    time_secs = cc.parse_duration(updated_time)
    time_ok = (not time_given) or (time_secs is not None and goal_dist is not None)
    if time_given and time_secs is None:
        st.warning("Thời gian đích phải dạng mm:ss hoặc h:mm:ss.")
    elif time_given and goal_dist is None:
        st.warning("Mục tiêu này không có cự ly cố định, hãy bỏ trống thời gian đích.")

    if time_given and time_ok:
        updated_targ_pace = cc.sec_to_pace(time_secs / goal_dist)
        st.caption(f"🎯 Pace mục tiêu (tự tính): **{updated_targ_pace}** /km")
    else:
        updated_targ_pace = st.text_input(
            "Pace mục tiêu", value=prof.get("target_pace", "05:30"), key=f"p_tpace_{pid}"
        )

    updated_dist = st.number_input("Max KM/buổi", min_value=0.5, value=float(prof.get("max_distance", 8.0)), key=f"p_dist_{pid}")

    pace_ok = cc.validate_pace(updated_curr_pace) and cc.validate_pace(updated_targ_pace)
    if not pace_ok:
        st.warning("Pace phải đúng định dạng mm:ss (vd 06:30).")

    c_r1, c_r2 = st.columns([2, 3])
    updated_is_racing = c_r1.checkbox("Có giải", value=bool(prof.get("race_date", "")), key=f"p_israce_{pid}")
    old_dt = cc.parse_iso_date(prof.get("race_date")) or cc.today_vn()
    updated_race_date = c_r2.date_input(
        "Ngày giải", value=old_dt, min_value=min(old_dt, cc.today_vn()),
        disabled=not updated_is_racing, key=f"p_race_{pid}", label_visibility="collapsed",
    )
    updated_race_date_str = updated_race_date.strftime("%Y-%m-%d") if updated_is_racing else ""

    with st.expander("📝 Chấn thương & ghi chú"):
        updated_injuries = st.text_area("Chấn thương", value=prof.get("injuries", ""), height=68, key=f"p_inj_{pid}")
        updated_notes = st.text_area("Ghi chú riêng", value=prof.get("notes", ""), height=68, key=f"p_notes_{pid}")
    updated_days = st.multiselect("Lịch rảnh", cc.ALL_DAYS, default=prof.get("days", []), key=f"p_days_{pid}")

    new_profile = {
        "goal": updated_goal, "current_pace": updated_curr_pace.strip(), "target_pace": updated_targ_pace.strip(),
        "target_time": updated_time.strip() if time_ok else prof.get("target_time", ""),
        "max_distance": updated_dist, "injuries": updated_injuries, "notes": updated_notes,
        "days": updated_days, "race_date": updated_race_date_str,
    }
    profile_valid = pace_ok and time_ok
    existing_prof = curr_project.get("profile") or {}
    profile_changed = any(existing_prof.get(k) != v for k, v in new_profile.items())
    if profile_valid and profile_changed:
        curr_project["profile"].update(new_profile)
        persist(selected_proj_id)

    week_pick = st.date_input("📅 Tuần bắt đầu từ", value=cc.default_week_start(), key="week_start_pick")
    week_start = cc.monday_of(week_pick)
    st.caption(f"Tuần: {week_start:%d/%m} – {week_start + timedelta(days=6):%d/%m/%Y}")
    if any(p.get("week_start") == week_start.isoformat() for p in curr_project["plans"]):
        st.warning("Đã có tuần được lưu trùng ngày bắt đầu này.")

    if stretch_button("🚀 TẠO KẾ HOẠCH TUẦN MỚI", type="primary", key="gen_btn"):
        valid_keys = get_valid_keys()
        if not valid_keys:
            st.error("Chưa có API Key! Hãy dán key vào HARDCODED_API_KEYS trong coach_core.py.")
        elif not profile_valid:
            st.error("Sửa lại pace / thời gian đích trước khi tạo kế hoạch.")
        elif not updated_days:
            st.error("Chọn ít nhất 1 ngày tập.")
        else:
            with st.spinner("🧠 AI đang lập giáo án (ưu tiên Hydrogen → 3.8 Flash)..."):
                plan_result = cc.generate_running_plan(
                    valid_keys, curr_project["profile"], curr_project["plans"],
                    week_start=week_start, memory=curr_project.get("memory"),
                )
            if "error" in plan_result:
                st.error(plan_result["error"])
            else:
                plan_result["_draft_id"] = cc.new_id()
                curr_project["draft"] = plan_result
                persist(selected_proj_id)
                st.toast(f"Đã tạo kế hoạch mới ({plan_result.get('model_used', 'AI')})!", icon="🎉")


# ==========================================
# 5. HERO BANNER & TABS
# ==========================================
days_left = cc.days_to_race(curr_project["profile"])
phase_now = cc.training_phase(days_left)
phase_text = cc.PHASE_LABEL.get(phase_now, "Duy trì")
shoe_stats_now = cc.compute_shoe_stats(curr_project)
worn_shoes = [x for x in shoe_stats_now if x["pct"] >= 85]
today = cc.today_vn()
plans = curr_project.get("plans", [])

chips = [
    (f"⚡ {phase_text}", "blue"),
    ("🤖 Auto: Hydrogen → 3.8 Flash" if configured_keys_count else "⚠️ Chưa gắn API Key", "ok" if configured_keys_count else "warn"),
]
if days_left is not None:
    if days_left > 0:
        chips.append((f"🏁 Còn {days_left} ngày tới race", "acc"))
    elif days_left == 0:
        chips.append(("🔥 Hôm nay là race day!", "acc"))
if worn_shoes:
    chips.append((f"👟 {worn_shoes[0]['name']}: {worn_shoes[0]['total_km']}/{worn_shoes[0]['max_km']:g} km", "warn"))
ui_kit.topbar(
    "AI Running Coach Pro",
    [("Dự án", curr_project["name"]), ("Mục tiêu", curr_project["profile"].get("goal", "")),
     ("Pace đích", f"{cc.resolve_target_pace(curr_project['profile'])}/km")],
    chips,
)


def find_focus_session(plans_, today_):
    """(plan, item, mode, date): buổi hôm nay; nếu hôm nay không có lịch thì buổi tiếp theo trong tuần."""
    for plan_ in reversed(plans_):
        ws = cc.parse_iso_date(plan_.get("week_start"))
        if not ws or not (ws <= today_ <= ws + timedelta(days=6)):
            continue
        idx_today = (today_ - ws).days
        by_idx = {}
        for it_ in plan_.get("schedule", []):
            nd = cc.normalize_day(it_.get("day"))
            if nd in cc.ALL_DAYS:
                by_idx.setdefault(cc.ALL_DAYS.index(nd), it_)
        if idx_today in by_idx:
            return plan_, by_idx[idx_today], "today", today_
        for i in range(idx_today + 1, 7):
            if i in by_idx:
                return plan_, by_idx[i], "next", ws + timedelta(days=i)
        return plan_, None, "none", today_
    return None, None, "none", today_


def activity_by_date(plans_):
    out = {}
    for plan_ in plans_ or []:
        ws = cc.parse_iso_date(plan_.get("week_start"))
        for it_ in plan_.get("schedule") or []:
            tele = it_.get("telemetry") if isinstance(it_.get("telemetry"), dict) else None
            if not (cc.is_run(it_) and (it_.get("completed") or tele)):
                continue
            d = cc.parse_iso_date(it_.get("date"))
            nd = cc.normalize_day(it_.get("day"))
            if d is None and ws and nd in cc.ALL_DAYS:
                d = ws + timedelta(days=cc.ALL_DAYS.index(nd))
            if d is not None:
                km_val = cc.km_done(it_) if it_.get("completed") else float(tele.get("distance_km") or 0.0)
                if km_val > 0:
                    out[d] = out.get(d, 0.0) + km_val
    return out


tab_today, tab_current, tab_history, tab_gear_tools = st.tabs([
    "🏠 Hôm nay",
    "📋 Lịch tuần mới",
    "📊 Lịch sử & Dashboard",
    "👟 Giày & Công cụ",
])

with tab_today:
    col_l, col_r = st.columns([1.75, 1], gap="medium")
    focus_plan, focus_item, focus_mode, focus_date = find_focus_session(plans, today)
    last_plan = plans[-1] if plans else None
    last_stats = cc.plan_stats(last_plan) if last_plan else None

    with col_l:
        if focus_item:
            wt = str(focus_item.get("workout_type") or "")
            km_f = cc.km_planned(focus_item)
            day_nm = cc.normalize_day(focus_item.get("day"))
            kicker = (f"Hôm nay · {day_nm}, {focus_date:%d/%m}" if focus_mode == "today"
                      else f"Buổi tiếp theo · {day_nm}, {focus_date:%d/%m}")
            fs = cc.plan_stats(focus_plan)
            meta_bits = [] if wt == "Rest" else [f"Pace mục tiêu {focus_item.get('pace_target') or '—'}/km"]
            ui_kit.today_card(
                kicker, wt if wt == "Rest" else f"{wt} · {km_f:.1f} km", " ".join(meta_bits),
                str(focus_item.get("notes") or ""), fs["rate"], f"Hoàn thành {fs['done']}/{fs['total']} buổi tuần này",
                ui_kit.TYPE_COLORS.get(wt, "#16A34A"), "Đã xong" if focus_item.get("completed") else "",
            )
            if focus_mode == "today" and cc.is_run(focus_item) and not focus_item.get("completed"):
                if st.button("✓ Đánh dấu đã xong buổi hôm nay", type="primary", key="mark_today_done"):
                    focus_item["completed"] = True
                    persist(selected_proj_id)
                    st.rerun()
        elif plans:
            ui_kit.empty_state("Tuần này chưa có buổi nào", "Tạo kế hoạch cho tuần hiện tại ở thanh bên để thấy buổi tập hôm nay.")
        else:
            ui_kit.empty_state("Chưa có kế hoạch", "Bấm “Tạo kế hoạch tuần mới” ở thanh bên để AI lập giáo án đầu tiên.")

        if last_plan and last_stats:
            ui_kit.section_title("Lịch tuần gần nhất", f"{last_stats['done']}/{last_stats['total']} buổi")
            ui_kit.week_strip(last_plan.get("schedule") or [], normalize_day=cc.normalize_day,
                              today_name=cc.ALL_DAYS[today.weekday()])
        ui_kit.monthly_calendar_card(curr_project, today)

    with col_r:
        if last_plan and last_stats:
            _avg_p = last_stats.get("avg_pace")
            _avg_p_str = (cc.sec_to_pace(_avg_p) if (_avg_p is not None and _avg_p > 0) else "") or "—"
            ui_kit.kpi_row([
                {"icon": "📏", "label": "Km tuần gần nhất", "value": f"{last_stats['done_km']:.1f}", "unit": f"/{last_stats['planned_km']:.0f}", "color": "#D92D20"},
                {"icon": "✅", "label": "Hoàn thành", "value": last_stats["rate"], "unit": "%", "color": "#16A34A"},
                {"icon": "⚡", "label": "Pace TB", "value": _avg_p_str, "unit": "/km", "color": "#2563EB"},
                {"icon": "🔥", "label": "Streak ≥80%", "value": cc.completion_streak(plans), "unit": "tuần", "color": "#D97706"},
            ])
        alerts = []
        if last_plan:
            ws_l = cc.parse_iso_date(last_plan.get("week_start"))
            overdue = []
            for it_ in last_plan.get("schedule", []):
                nd = cc.normalize_day(it_.get("day"))
                if ws_l and cc.is_run(it_) and not it_.get("completed") and nd in cc.ALL_DAYS:
                    d_ = ws_l + timedelta(days=cc.ALL_DAYS.index(nd))
                    if d_ < today:
                        overdue.append(d_)
            if overdue:
                alerts.append({"icon": "📝", "title": f"{len(overdue)} buổi chưa cập nhật", "tag": "Lịch tuần", "sub": f"Sớm nhất: {min(overdue):%d/%m}"})
            if last_stats["done"] > 0 and not last_plan.get("user_feedback"):
                alerts.append({"icon": "💬", "title": "Chưa ghi cảm nhận tuần gần nhất", "tag": "Phản hồi", "sub": "AI đọc cảm nhận để chỉnh tuần sau"})
            if last_stats["max_pain"] is not None and last_stats["max_pain"] >= 6:
                alerts.append({"icon": "⚠️", "title": f"Đau tối đa {last_stats['max_pain']:.0f}/10", "tag": "Sức khỏe", "sub": "Cân nhắc giảm tải hoặc nghỉ"})
        if curr_project.get("draft"):
            alerts.append({"icon": "🗂️", "title": "Có bản nháp chưa lưu", "tag": "Lịch mới", "sub": "Mở tab “Lịch tuần mới” để duyệt"})
        ui_kit.section_title("Cần chú ý", len(alerts))
        ui_kit.attention_list(alerts)

        if days_left is not None and plans:
            first_start = cc.parse_iso_date(plans[0].get("week_start"))
            if first_start:
                ui_kit.race_track(days_left, (today - first_start).days + days_left, curr_project["profile"].get("goal", ""))

        ui_kit.section_title("Giày đang theo dõi", len(shoe_stats_now))
        ui_kit.watch_list([
            {"icon": "👟", "title": x["name"], "sub": f"{x['total_km']}/{x['max_km']:g} km · {x['status']}", "pct": x["pct"],
             "color": "#DC2626" if x["total_km"] >= x["max_km"] else ("#D97706" if x["pct"] >= 80 else "#16A34A")}
            for x in shoe_stats_now[:3]
        ])

DRAFT_COLS = ["day", "workout_type", "distance_km", "pace_target", "notes"]

with tab_current:
    draft = curr_project.get("draft")
    if draft:
        draft_id = draft.get("_draft_id", "x")
        plan_title = st.text_input("🏷️ Tiêu đề Tuần Tập:", value=draft.get("default_title", "Tuần"), key=f"draft_title_{draft_id}")
        draft["default_title"] = plan_title

        st.markdown(
            f'<div class="hlv-box"><strong>💡 Lời khuyên HLV AI:</strong><br>{escape(str(draft.get("week_summary", "")))}</div>',
            unsafe_allow_html=True,
        )

        meta = [f"📅 {cc.week_range_text(draft.get('week_start'))}",
                f"Giai đoạn: **{cc.PHASE_LABEL.get(draft.get('phase'), '-')}**"]
        if draft.get("model_used"):
            meta.append(f"Model: **{draft['model_used']}**")
        if draft.get("cap_km"):
            meta.append(f"Trần km tuần: **{draft['cap_km']:g}** ({draft.get('cap_reason', '')})")
        st.caption(" · ".join(meta))
        if draft.get("zones"):
            with st.expander("🎯 Vùng pace gợi ý (đã tính theo giai đoạn)"):
                st.text(cc.zones_text({t: tuple(v) for t, v in draft["zones"].items()}))
        if draft.get("warnings"):
            with st.expander(f"⚠️ App đã tự hiệu chỉnh {len(draft['warnings'])} điểm trong đề xuất của AI"):
                for w in draft["warnings"]:
                    st.markdown(f"- {w}")

        mem_rules = (curr_project.get("memory") or {}).get("rules", [])
        if draft.get("insights") or mem_rules:
            with st.expander(f"🧠 Tín hiệu đã đưa vào prompt ({len(draft.get('insights') or [])}) · quy tắc đã học ({len(mem_rules)})"):
                for b in draft.get("insights") or []:
                    st.markdown(f"- {b}")
                if mem_rules:
                    st.caption("Quy tắc thói quen chỉ được lưu khi cùng kiểu chỉnh lặp lại từ 2 tuần; giữ tối đa 5 quy tắc gần nhất.")
                    if st.button("🗑️ Xóa các quy tắc đã học", key=f"clear_mem_{draft_id}"):
                        curr_project["memory"] = cc.default_memory()
                        persist(selected_proj_id)
                        st.rerun()

        df = pd.DataFrame([{k: it.get(k) for k in DRAFT_COLS} for it in draft.get("schedule", [])], columns=DRAFT_COLS)
        edited_df = st.data_editor(
            df, key=f"draft_editor_{draft_id}", num_rows="dynamic", hide_index=True, **EDITOR_STRETCH,
            column_config={
                "day": st.column_config.SelectboxColumn("Ngày", options=cc.ALL_DAYS, required=True),
                "workout_type": st.column_config.SelectboxColumn("Loại", options=cc.WORKOUT_TYPES, required=True),
                "distance_km": st.column_config.NumberColumn("Km", min_value=0.0, step=0.1, format="%.1f"),
                "pace_target": st.column_config.TextColumn("Pace (mm:ss)"),
                "notes": st.column_config.TextColumn("Ghi chú"),
            },
        )
        records = [
            {k: (None if pd.isna(v) else v) for k, v in row.items()}
            for row in edited_df.to_dict("records") if not pd.isna(row.get("day"))
        ]
        total_km = sum(cc.km_planned(r) for r in records if r.get("workout_type") != "Rest")
        if draft.get("cap_km") and total_km > draft["cap_km"]:
            st.warning(f"Tổng {total_km:.1f} km đang vượt trần tuần {draft['cap_km']:g} km. Giảm bớt để tránh tăng tải quá nhanh.")
        else:
            st.caption(f"Tổng km tuần: **{total_km:.1f} km**")

        with st.expander("🔄 Tạo lại 1 buổi"):
            if records:
                re_day = st.selectbox("Buổi cần tạo lại", [r["day"] for r in records], key=f"re_day_{draft_id}")
                re_hint = st.text_input("Yêu cầu thêm (tùy chọn)", key=f"re_hint_{draft_id}", placeholder="vd: nhẹ hơn, chạy sáng sớm")
                if st.button("Tạo lại buổi này", key=f"re_btn_{draft_id}"):
                    keys = get_valid_keys()
                    if not keys:
                        st.error("Chưa có API Key!")
                    else:
                        draft["schedule"] = records
                        with st.spinner("Đang tạo lại buổi..."):
                            res = cc.regenerate_session(keys, curr_project["profile"], draft, re_day, hint=re_hint)
                        if "error" in res:
                            st.error(res["error"])
                        else:
                            draft["schedule"] = [res["item"] if cc.normalize_day(r["day"]) == re_day else r for r in records]
                            if draft.get("ai_schedule"):
                                draft["ai_schedule"] = [r for r in draft["ai_schedule"] if cc.normalize_day(r.get("day")) != re_day] + [dict(res["item"])]
                            draft["_draft_id"] = cc.new_id()
                            persist(selected_proj_id)
                            st.rerun()
            else:
                st.caption("Chưa có buổi nào.")

        b1, b2 = st.columns([1, 1])
        if b1.button("💾 LƯU VÀO DỰ ÁN", type="primary", key=f"save_draft_{draft_id}"):
            profile_now = curr_project["profile"]
            ws_iso = draft.get("week_start") or ""
            cleaned, _ = cc.validate_plan(records, profile_now, week_start=cc.parse_iso_date(ws_iso), lenient=True)
            if not cleaned:
                st.error("Cần ít nhất 1 buổi tập hợp lệ trước khi lưu.")
            else:
                new_week_index = cc.next_week_index(curr_project["plans"])
                curr_project["memory"] = cc.learn_from_edits(
                    curr_project.get("memory"), new_week_index, draft.get("ai_schedule"), cleaned)
                curr_project["plans"].append({
                    "id": cc.new_id(), "title": plan_title,
                    "week_index": new_week_index,
                    "week_start": ws_iso,
                    "created_at": cc.now_vn().strftime("%d/%m/%Y %H:%M"),
                    "week_summary": draft.get("week_summary", ""),
                    "phase": draft.get("phase"), "cap_km": draft.get("cap_km"),
                    "schedule": cleaned, "user_feedback": "",
                })
                curr_project["draft"] = None
                persist(selected_proj_id)
                st.rerun()
        if b2.button("🗑️ Bỏ bản nháp", key=f"discard_draft_{draft_id}"):
            curr_project["draft"] = None
            persist(selected_proj_id)
            st.rerun()
    else:
        st.info("👈 Bấm **'🚀 TẠO KẾ HOẠCH TUẦN MỚI'** ở thanh bên trái để AI thiết kế giáo án phù hợp nhất với thể trạng của bạn.")

LOG_COLS = ["day", "date", "workout_type", "distance_km", "pace_target",
            "completed", "actual_km", "actual_pace", "shoe_name", "rpe", "pain", "notes"]
LOG_DISABLED = ["day", "date", "workout_type", "distance_km", "pace_target", "notes"]
NAN = float("nan")


def log_df(plan, shoes):
    id_to_name = {s["id"]: s["name"] for s in shoes}
    default_name = next((s["name"] for s in shoes if s.get("is_default")), "")
    rows = []
    for it in plan.get("schedule", []):
        def num(key):
            v = cc.to_float(it.get(key))
            return NAN if v is None else v
        sname = id_to_name.get(it.get("shoe_id"), default_name if cc.is_run(it) else "")
        rows.append({
            "day": it.get("day"), "date": cc.fmt_dm(it.get("date")), "workout_type": it.get("workout_type"),
            "distance_km": cc.km_planned(it), "pace_target": it.get("pace_target", ""),
            "completed": bool(it.get("completed")), "actual_km": num("actual_km"),
            "actual_pace": it.get("actual_pace", "") or "", "shoe_name": sname,
            "rpe": num("rpe"), "pain": num("pain"), "notes": it.get("notes", ""),
        })
    return pd.DataFrame(rows, columns=LOG_COLS)


with tab_history:
    saved_plans = curr_project["plans"]
    shoes_list = curr_project.get("shoes", [])
    shoe_names = [""] + [s["name"] for s in shoes_list]

    if not saved_plans:
        st.warning("Chưa có lịch tập nào được lưu trong dự án này.")
    else:
        stats = [cc.plan_stats(p) for p in saved_plans]
        total_runs = sum(s["total"] for s in stats)
        done_runs = sum(s["done"] for s in stats)
        rate = int(done_runs / total_runs * 100) if total_runs else 0
        total_km_done = sum(s["done_km"] for s in stats)
        dist = cc.type_distribution(saved_plans)
        low_share = cc.low_intensity_share(dist)

        latest = saved_plans[-1]
        render_dynamic_dashboard(
            total_km_done, latest.get("schedule", []), [x["done_km"] for x in cc.weekly_table(saved_plans)],
            latest.get("week_summary", ""), rate,
        )

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Số tuần đã lưu", f"{len(saved_plans)}")
        m2.metric("Buổi hoàn thành", f"{done_runs}/{total_runs}", help="Chỉ tính các buổi chạy/đi bộ có kế hoạch (không tính ngày Rest).")
        m3.metric("Tỷ lệ hoàn thành", f"{rate}%", help="Tỷ lệ buổi chạy hoàn thành trên tổng số buổi chạy được giao (không tính Rest).")
        m4.metric("Tổng km đã chạy", f"{total_km_done:.1f}")
        m5.metric("Streak", f"{cc.completion_streak(saved_plans)} tuần", help="Số tuần liên tiếp hoàn thành ≥ 80%")
        m6.metric("Km cường độ thấp", "-" if low_share is None else f"{low_share}%", help="Mốc chuẩn 80/20 là ~80%")

        with st.expander("📈 Biểu đồ tổng quan (km tuần, pace, phân bổ loại buổi)", expanded=True):
            rows_w = cc.weekly_table(saved_plans)
            charts = [("Km mỗi tuần: đã chạy / kế hoạch", weekly_chart(rows_w))]
            pace_chart_obj = pace_chart(rows_w)
            if pace_chart_obj is not None:
                charts.append(("Pace thực tế TB (lên = nhanh hơn)", pace_chart_obj))
            if dist:
                charts.append(("Km đã chạy theo loại buổi", dist_chart(dist)))
            for col, (caption, chart) in zip(st.columns([3] + [2] * (len(charts) - 1)), charts):
                with col:
                    st.caption(caption)
                    show_chart(chart)
            if pace_chart_obj is None:
                st.caption("💡 Tick 'Xong' hoặc đồng bộ file .fit / .gpx để xem đường xu hướng pace.")

        pending = st.session_state.get("pending_del_plan")

        for p_idx, plan in enumerate(reversed(saved_plans)):
            plan_id = plan["id"]
            s = cc.plan_stats(plan)
            wr = cc.week_range_text(plan.get("week_start"))
            with st.expander(f"🗓️ {plan['title']}{' · ' + wr if wr else ''} (Tạo: {plan['created_at']})", expanded=(p_idx == 0)):
                st.info(f"**Lời khuyên:** {plan['week_summary']}")
                st.caption(f"Hoàn thành {s['done']}/{s['total']} buổi · {s['done_km']:.1f}/{s['planned_km']:.1f} km"
                           + (f" · pace TB {cc.sec_to_pace(s['avg_pace'])}" if s["avg_pace"] else "")
                           + (f" · RPE TB {s['rpe_avg']:.1f}" if s["rpe_avg"] is not None else "")
                           + (f" · đau tối đa {s['max_pain']:.0f}/10" if s["max_pain"] is not None else ""))

                ui_kit.week_strip(plan.get("schedule") or [], normalize_day=cc.normalize_day)

                log_key = f"log_{selected_proj_id}_{plan_id}"
                st.data_editor(
                    log_df(plan, shoes_list), key=log_key, hide_index=True, disabled=LOG_DISABLED, column_order=LOG_COLS,
                    on_change=cb_log_edit, args=(selected_proj_id, plan_id, log_key), **EDITOR_STRETCH,
                    column_config={
                        "day": st.column_config.TextColumn("Ngày"),
                        "date": st.column_config.TextColumn("Ngày tháng"),
                        "workout_type": st.column_config.TextColumn("Loại"),
                        "distance_km": st.column_config.NumberColumn("Km KH", format="%.1f"),
                        "pace_target": st.column_config.TextColumn("Pace KH"),
                        "completed": st.column_config.CheckboxColumn("Xong"),
                        "actual_km": st.column_config.NumberColumn("Km thực", min_value=0.0, max_value=100.0, step=0.1, format="%.1f"),
                        "actual_pace": st.column_config.TextColumn("Pace thực", help="mm:ss"),
                        "shoe_name": st.column_config.SelectboxColumn("Giày chạy", options=shoe_names),
                        "rpe": st.column_config.NumberColumn("RPE 1-10", min_value=1, max_value=10, step=1, format="%d"),
                        "pain": st.column_config.NumberColumn("Đau 0-10", min_value=0, max_value=10, step=1, format="%d"),
                        "notes": st.column_config.TextColumn("Ghi chú"),
                    },
                )

                run_sessions = [it for it in plan.get("schedule", []) if cc.is_run(it)]
                if run_sessions:
                    with st.container(key=f"card-fit-{plan_id}"):
                        st.markdown("**⌚ Đồng bộ dữ liệu đồng hồ / Strava (`.fit` hoặc `.gpx`)**")
                        c_fit1, c_fit2 = st.columns([1, 2])
                        session_labels = [f"{it['day']} ({it['workout_type']} - {cc.km_planned(it):.1f} km)" for it in run_sessions]
                        sel_idx = c_fit1.selectbox(
                            "Chọn buổi tập để nạp dữ liệu:",
                            range(len(run_sessions)),
                            format_func=lambda idx: session_labels[idx],
                            key=f"fit_sel_{plan_id}",
                        )
                        target_session = run_sessions[sel_idx]
                        uploaded_act = c_fit2.file_uploader(
                            "Kéo thả file .fit hoặc .gpx vào đây:",
                            type=["fit", "gpx"],
                            key=f"fit_up_{plan_id}_{sel_idx}",
                        )
                        if uploaded_act is not None:
                            c_ov1, c_ov2 = st.columns(2)
                            ov_km = c_ov1.number_input(
                                "Quãng đường Strava (km - để 0 nếu tự tính):",
                                min_value=0.0, max_value=200.0, value=0.0, step=0.01, format="%.2f",
                                key=f"ov_km_{plan_id}_{sel_idx}",
                            )
                            ov_time_str = c_ov2.text_input(
                                "Moving Time Strava (mm:ss hoặc h:mm:ss - để trống nếu tự tính):",
                                value="", placeholder="vd: 28:45 hoặc 1:42:10",
                                key=f"ov_time_{plan_id}_{sel_idx}",
                            )
                            if stretch_button("📥 Phân tích & Đồng bộ vào buổi này", type="primary", key=f"fit_btn_{plan_id}_{sel_idx}"):
                                try:
                                    ov_time_sec = cc.parse_duration(ov_time_str) if ov_time_str.strip() else None
                                    if ov_time_str.strip() and ov_time_sec is None:
                                        st.error("Thời gian Strava phải đúng định dạng mm:ss hoặc h:mm:ss.")
                                    else:
                                        tele = cc.parse_activity_file(
                                            uploaded_act.name,
                                            uploaded_act.getvalue(),
                                            strava_km=ov_km if ov_km > 0 else None,
                                            strava_time_sec=ov_time_sec,
                                        )
                                        target_session["telemetry"] = tele
                                        target_session["completed"] = True
                                        target_session["actual_km"] = tele["distance_km"]
                                        if tele.get("avg_pace"):
                                            target_session["actual_pace"] = tele["avg_pace"]
                                        persist(selected_proj_id)
                                        st.toast(f"Đã đồng bộ {tele['distance_km']} km từ {uploaded_act.name}!", icon="⌚")
                                        st.rerun()
                                except (ValueError, RuntimeError, OSError, UnicodeDecodeError, struct.error, ET.ParseError) as e:
                                    st.error(f"Lỗi định dạng hoặc dữ liệu file hoạt động: {e}")
                                except Exception as e:
                                    st.error(f"Lỗi không mong muốn khi xử lý file ({type(e).__name__}): {e}")

                        tele_sessions = [it for it in run_sessions if it.get("telemetry")]
                        if tele_sessions:
                            view_it = target_session if target_session.get("telemetry") else tele_sessions[-1]
                            tele_data = view_it["telemetry"]
                            dur_str = cc.format_duration(tele_data.get("duration_sec", 0))
                            st.caption(
                                f"📊 Telemetry buổi **{view_it['day']}** (Nguồn: `{tele_data.get('source_file', 'activity')}`) · "
                                f"Quãng đường: **{tele_data.get('distance_km')} km** · "
                                f"Thời gian di chuyển: **{dur_str}** · "
                                f"Pace TB: **{tele_data.get('avg_pace')}/km**"
                                + (f" · HR TB: **{tele_data['avg_hr']} bpm**" if tele_data.get("avg_hr") else "")
                                + (f" · Cadence TB: **{tele_data['avg_cadence']} spm**" if tele_data.get("avg_cadence") else "")
                                + (f" · Leo dốc: **+{tele_data['total_ele_gain']} m**" if tele_data.get("total_ele_gain") else "")
                            )
                            physio = cc.analyze_session_physio(view_it)
                            if physio["status"] == "ok":
                                st.caption(f"❤️ Cardiac Drift **{physio['drift_pct']:.1f}%** · Efficiency Factor **{physio['ef']:.2f}** (HR hợp lệ)")
                            elif physio["status"] == "invalid":
                                st.caption("❤️ HR buổi này nghi nhiễu (cổ tay/cadence lock) nên không dùng để đánh giá drift.")
                            split_charts = telemetry_split_charts(tele_data.get("splits", []))
                            if split_charts:
                                n_cols = 2 if len(split_charts) >= 2 else 1
                                for start_i in range(0, len(split_charts), n_cols):
                                    row_items = split_charts[start_i:start_i + n_cols]
                                    cols_t = st.columns(len(row_items))
                                    for col_t, (cap_t, ch_t) in zip(cols_t, row_items):
                                        with col_t:
                                            st.caption(cap_t)
                                            show_chart(ch_t)
                            splits_df = format_splits_df(tele_data.get("splits", []))
                            if not splits_df.empty:
                                st.markdown("**📋 Bảng thông số chi tiết từng km (Splits)**")
                                st.dataframe(splits_df, hide_index=True, **EDITOR_STRETCH)

                fb_key = f"fb_{selected_proj_id}_{plan_id}"
                fb_val = st.text_area(
                    "📝 Cảm nhận / phản hồi sau tuần này (AI sẽ đọc để điều chỉnh tuần sau):",
                    value=plan.get("user_feedback", ""), key=fb_key, height=80,
                    on_change=cb_feedback, args=(selected_proj_id, plan_id, fb_key),
                )
                if st.button("💾 Lưu cảm nhận", key=f"save_fb_{selected_proj_id}_{plan_id}"):
                    plan["user_feedback"] = fb_val
                    persist(selected_proj_id)
                    st.toast("Đã lưu cảm nhận để AI tham chiếu cho tuần sau!", icon="📝")

                a1, a2 = st.columns([1, 1])
                ics = cc.plan_to_ics(curr_project["name"], plan)
                if ics:
                    a1.download_button("📅 Xuất lịch (.ics)", data=ics, file_name=f"{plan['title']}.ics",
                                       mime="text/calendar", key=f"ics_{selected_proj_id}_{plan_id}")
                if pending == (selected_proj_id, plan_id):
                    a2.warning("Xóa tuần này? Không thể hoàn tác.")
                    d1, d2 = a2.columns(2)
                    d1.button("✅ Xóa", key=f"yes_del_{plan_id}", on_click=cb_delete_plan, args=(selected_proj_id, plan_id))
                    d2.button("Hủy", key=f"no_del_{plan_id}", on_click=cb_cancel_delete)
                else:
                    a2.button("🗑️ Xóa tuần này", key=f"del_plan_{selected_proj_id}_{plan_id}",
                              on_click=cb_ask_delete, args=(selected_proj_id, plan_id))

with tab_gear_tools:
    st.subheader("👟 Theo dõi giày chạy")
    st.caption("Tự động cộng dồn số km từ các buổi chạy đã hoàn thành để cảnh báo thời điểm đệm giày hết độ đàn hồi.")

    c_shoe_list, c_shoe_add = st.columns([3, 2])
    with c_shoe_list:
        shoe_stats = cc.compute_shoe_stats(curr_project)
        if not shoe_stats:
            st.info("Chưa có đôi giày nào. Hãy thêm giày của bạn ở khung bên phải.")
        else:
            for s in shoe_stats:
                bar_color = "#EF4444" if s["total_km"] >= s["max_km"] else ("#F59E0B" if s["pct"] >= 80 else "#10B981")
                rem_km = max(0.0, round(s["max_km"] - s["total_km"], 1))
                star_prefix = "⭐ " if s["is_default"] else ""
                st.markdown(f"""
                <div class="shoe-card">
                    <div class="shoe-header">
                        <div>
                            <strong style="font-size:15px;">{star_prefix}{escape(s['name'])}</strong>
                            <span style="font-size:12px;opacity:0.65;margin-left:8px;">{escape(s['brand'])}</span>
                        </div>
                        <div style="font-weight:800;color:{bar_color};">{s['total_km']} / {s['max_km']:g} km ({s['pct']}%)</div>
                    </div>
                    {ui_kit.progress_bar_html(s['pct'], bar_color)}
                    <div style="font-size:12px;opacity:0.75;display:flex;justify-content:space-between;">
                        <span>{escape(s['status'])}</span>
                        <span>Còn lại ~{rem_km} km trước khi cần thay mới</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            c_act1, c_act2 = st.columns(2)
            sel_shoe_id = c_act1.selectbox(
                "Chọn giày thao tác:",
                [s["id"] for s in shoe_stats],
                format_func=lambda sid: next(x["name"] for x in shoe_stats if x["id"] == sid),
                key=f"shoe_act_sel_{selected_proj_id}",
            )
            if c_act2.button("⭐ Đặt làm giày mặc định", key=f"shoe_def_{selected_proj_id}"):
                for sh in curr_project["shoes"]:
                    sh["is_default"] = (sh["id"] == sel_shoe_id)
                persist(selected_proj_id)
                st.rerun()
            if c_act2.button("🗑️ Xóa đôi giày này", key=f"shoe_del_{selected_proj_id}"):
                curr_project["shoes"] = [sh for sh in curr_project["shoes"] if sh["id"] != sel_shoe_id]
                if curr_project["shoes"] and not any(sh.get("is_default") for sh in curr_project["shoes"]):
                    curr_project["shoes"][0]["is_default"] = True
                for pl in curr_project.get("plans", []):
                    for it in pl.get("schedule", []):
                        if it.get("shoe_id") == sel_shoe_id:
                            it["shoe_id"] = None
                persist(selected_proj_id)
                st.rerun()

    with c_shoe_add:
        with st.container(key="card-add-shoe"):
            st.markdown("**➕ Thêm Giày Mới**")
            with st.form(f"add_shoe_form_{selected_proj_id}"):
                sh_name = st.text_input("Tên giày (vd: Xtep 2000km 5.0 Pro, Saucony Guide 17):")
                sh_brand = st.text_input("Phân loại / Dòng giày:", value="Daily / Stability")
                c_sh1, c_sh2 = st.columns(2)
                sh_init = c_sh1.number_input("Số km đã chạy trước đó:", min_value=0.0, max_value=2000.0, value=0.0, step=10.0)
                sh_max = c_sh2.number_input("Tuổi thọ tối đa (km):", min_value=200.0, max_value=2000.0, value=750.0, step=50.0)
                sh_def = st.checkbox("Đặt làm giày mặc định cho các buổi mới", value=True)
                if st.form_submit_button("Thêm vào tủ giày"):
                    if not sh_name.strip():
                        st.error("Nhập tên đôi giày.")
                    else:
                        if sh_def or not curr_project.get("shoes"):
                            sh_def = True
                            for existing_sh in curr_project.setdefault("shoes", []):
                                existing_sh["is_default"] = False
                        curr_project.setdefault("shoes", []).append({
                            "id": cc.new_id(),
                            "name": sh_name.strip(),
                            "brand": sh_brand.strip(),
                            "initial_km": float(sh_init),
                            "max_km": float(sh_max),
                            "is_default": sh_def,
                        })
                        persist(selected_proj_id)
                        st.toast(f"Đã thêm {sh_name.strip()}!", icon="👟")
                        st.rerun()

    c_tool1, c_tool2 = st.columns(2)
    with c_tool1:
        st.subheader("⏱️ Dự đoán thành tích race")
        st.caption("Nhập thành tích tốt nhất gần đây (PR) của bạn để ước tính thời gian các cự ly khác.")
        t_dist = st.number_input("Cự ly đã chạy (km):", min_value=1.0, max_value=100.0, value=5.0, step=0.5)
        t_time = st.text_input("Thời gian hoàn thành (mm:ss hoặc h:mm:ss):", value="35:00")
        t_sec = cc.parse_duration(t_time)
        if t_sec:
            preds = cc.predict_race_times(t_dist, t_sec)
            st.dataframe(pd.DataFrame(preds), hide_index=True, **EDITOR_STRETCH)
        else:
            st.warning("Nhập đúng định dạng thời gian (vd: 32:00 hoặc 1:45:00).")

    with c_tool2:
        st.subheader("❤️ Vùng nhịp tim")
        st.caption("Hữu ích khi chạy thời tiết nóng ẩm (nên ưu tiên giữ nhịp tim Zone 2 cho bài Easy/Long Run).")
        age = st.number_input("Tuổi của bạn:", min_value=12, max_value=90, value=21)
        est_max_hr = 220 - age
        custom_max_hr = st.number_input("Nhịp tim tối đa HRmax (mặc định 220 - tuổi):", min_value=120, max_value=230, value=est_max_hr)
        hr_rows = cc.compute_hr_zones(custom_max_hr)
        st.dataframe(pd.DataFrame(hr_rows), hide_index=True, **EDITOR_STRETCH)
