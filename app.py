# -*- coding: utf-8 -*-
"""AI Running Coach Pro - giao diện Streamlit (Be Vietnam Pro, Glass Sheen Buttons, Telemetry FIT/GPX & Gear Tracker)."""
import inspect
import json
import os
from datetime import timedelta
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

import coach_core as cc
import ui_kit

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
RED, GRAY, TEXT = "#D92D20", "#F3CFCB", "#3B2F2F"
PACE_AXIS_EXPR = "floor(datum.value/60) + ':' + (datum.value%60<10 ? '0' : '') + floor(datum.value%60)"


def stretch_kwargs(func):
    params = inspect.signature(func).parameters
    if "width" in params and (
        isinstance(params["width"].default, str) or "Width" in str(params["width"].annotation)
    ):
        return {"width": "stretch"}
    return {"use_container_width": True} if "use_container_width" in params else {}


BTN_STRETCH = stretch_kwargs(st.button)
EDITOR_STRETCH = stretch_kwargs(st.data_editor)
CHART_STRETCH = stretch_kwargs(st.altair_chart)


def stretch_button(label, **kwargs):
    return st.button(label, **BTN_STRETCH, **kwargs)


def _style(chart):
    return (
        chart.configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=TEXT, titleColor=TEXT, gridColor="#F3E4E2",
            domainColor="#E6CFCC", tickColor="#E6CFCC", labelFontSize=11, titleFontSize=11,
        )
        .configure_legend(labelColor=TEXT, titleColor=TEXT)
    )


def show_chart(chart):
    try:
        st.altair_chart(chart, theme=None, **CHART_STRETCH)
    except TypeError:
        st.altair_chart(chart, **CHART_STRETCH)


def _area_gradient(color, opacity_top=0.22):
    return alt.Gradient(
        gradient="linear",
        stops=[
            alt.GradientStop(color=color, offset=0, opacity=opacity_top),
            alt.GradientStop(color="#FFFFFF", offset=1, opacity=0.0),
        ],
        x1=1, x2=1, y1=0, y2=1,
    )


def weekly_chart(rows):
    df = pd.DataFrame(rows)
    df["text"] = df.apply(lambda r: f"{r['done_km']:g}/{r['planned_km']:g}", axis=1)
    y_max = max(df["planned_km"].max(), df["done_km"].max(), 1) * 1.22
    base = alt.Chart(df).encode(x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)))
    planned = base.mark_bar(color=GRAY, size=26, cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        y=alt.Y("planned_km:Q", title="km", scale=alt.Scale(domainMin=0, domainMax=y_max)),
        tooltip=[
            alt.Tooltip("label:N", title="Tuần"),
            alt.Tooltip("planned_km:Q", title="Kế hoạch (km)"),
            alt.Tooltip("done_km:Q", title="Đã chạy (km)"),
        ],
    )
    done = base.mark_bar(color=RED, size=26, cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(y="done_km:Q")
    label = base.mark_text(dy=-8, color=TEXT, fontWeight="bold", fontSize=11).encode(y="planned_km:Q", text="text:N")
    return _style((planned + done + label).properties(height=175))


def pace_chart(rows, target_pace_str=None):
    df = pd.DataFrame([{"label": r["label"], "sec": r["avg_pace_min"] * 60} for r in rows if r["avg_pace_min"]])
    if df.empty:
        return None
    df["pace"] = df["sec"].apply(cc.sec_to_pace)
    base = alt.Chart(df).encode(
        x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(
            "sec:Q", title="phút/km",
            scale=alt.Scale(zero=False, reverse=True, nice=True),
            axis=alt.Axis(labelExpr=PACE_AXIS_EXPR),
        ),
        tooltip=[alt.Tooltip("label:N", title="Tuần"), alt.Tooltip("pace:N", title="Pace TB")],
    )
    area = base.mark_area(color=_area_gradient("#3B82F6", 0.22), interpolate="monotone")
    line = base.mark_line(color="#3B82F6", strokeWidth=2.5, interpolate="monotone",
                          point=alt.OverlayMarkDef(color="#3B82F6", size=60, filled=True))
    text = base.mark_text(dy=-14, color=TEXT, fontWeight="bold", fontSize=11).encode(text="pace:N")
    layers = area + line + text

    t_sec = cc.pace_to_sec(target_pace_str) if target_pace_str else None
    if t_sec:
        rule_df = pd.DataFrame([{"sec": t_sec, "lbl": f"Đích {cc.sec_to_pace(t_sec)}"}])
        rule = alt.Chart(rule_df).mark_rule(color="#D92D20", strokeDash=[4, 4], strokeWidth=1.5, opacity=0.75).encode(
            y="sec:Q", tooltip=[alt.Tooltip("lbl:N", title="Mục tiêu")],
        )
        layers = layers + rule
    return _style(layers.properties(height=175))


def dist_chart(dist):
    df = pd.DataFrame({"type": list(dist.keys()), "km": list(dist.values())})
    base = alt.Chart(df).encode(y=alt.Y("type:N", sort="-x", title=None))
    bars = base.mark_bar(color=RED, size=16, cornerRadiusTopRight=6, cornerRadiusBottomRight=6).encode(
        x=alt.X("km:Q", title="km", scale=alt.Scale(domainMin=0, domainMax=max(df["km"].max(), 1) * 1.22)),
        tooltip=["type:N", "km:Q"],
    )
    text = base.mark_text(align="left", dx=6, color=TEXT, fontWeight="bold", fontSize=11).encode(x="km:Q", text="km:Q")
    return _style((bars + text).properties(height=175))


def _split_line(df, y_col, y_title, label_col, color, tooltips, reverse=False, axis_expr=None):
    y_kwargs = {"title": y_title, "scale": alt.Scale(zero=False, reverse=reverse, nice=True)}
    if axis_expr:
        y_kwargs["axis"] = alt.Axis(labelExpr=axis_expr)
    base = alt.Chart(df).encode(
        x=alt.X("km_label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{y_col}:Q", **y_kwargs),
        tooltip=tooltips,
    )
    area = base.mark_area(color=_area_gradient(color, 0.20), interpolate="monotone")
    line = base.mark_line(color=color, strokeWidth=2.5, interpolate="monotone",
                          point=alt.OverlayMarkDef(color=color, size=55, filled=True))
    text = base.mark_text(dy=-12, color=TEXT, fontWeight="bold", fontSize=11).encode(text=f"{label_col}:N")
    return _style((area + line + text).properties(height=165))


def telemetry_split_charts(splits):
    """Vẽ biểu đồ Pace, Nhịp tim, Cadence và Độ cao từng km từ dữ liệu .fit / .gpx."""
    df = pd.DataFrame(splits)
    if df.empty:
        return []
    charts = []

    if "pace_sec" in df.columns and (df["pace_sec"] > 0).any():
        charts.append((
            "⚡ Pace từng km (phút/km)",
            _split_line(
                df[df["pace_sec"] > 0], "pace_sec", "phút/km", "pace_str", "#F59E0B",
                [alt.Tooltip("km_label:N", title="Split"), alt.Tooltip("pace_str:N", title="Pace")],
                reverse=True, axis_expr=PACE_AXIS_EXPR,
            ),
        ))

    if "avg_hr" in df.columns and df["avg_hr"].notna().any():
        charts.append((
            "❤️ Nhịp tim trung bình từng km (bpm)",
            _split_line(
                df.dropna(subset=["avg_hr"]), "avg_hr", "bpm", "avg_hr", "#D92D20",
                [
                    alt.Tooltip("km_label:N", title="Split"),
                    alt.Tooltip("avg_hr:Q", title="Nhịp tim (bpm)"),
                    alt.Tooltip("pace_str:N", title="Pace"),
                ],
            ),
        ))

    if "avg_cadence" in df.columns and df["avg_cadence"].notna().any():
        charts.append((
            "👟 Guồng chân / Cadence từng km (spm)",
            _split_line(
                df.dropna(subset=["avg_cadence"]), "avg_cadence", "spm", "avg_cadence", "#3B82F6",
                [
                    alt.Tooltip("km_label:N", title="Split"),
                    alt.Tooltip("avg_cadence:Q", title="Guồng chân (spm)"),
                    alt.Tooltip("pace_str:N", title="Pace"),
                ],
            ),
        ))

    if "ele_gain" in df.columns and (df["ele_gain"] > 0).any():
        base_ele = alt.Chart(df).encode(
            x=alt.X("km_label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("ele_gain:Q", title="mét (m)", scale=alt.Scale(domainMin=0, domainMax=max(df["ele_gain"].max(), 1) * 1.25)),
            tooltip=[
                alt.Tooltip("km_label:N", title="Split"),
                alt.Tooltip("ele_gain:Q", title="Leo dốc (m)"),
                alt.Tooltip("pace_str:N", title="Pace"),
            ],
        )
        c_ele = _style((
            base_ele.mark_bar(color="#10B981", size=20, cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
            + base_ele.mark_text(dy=-8, color=TEXT, fontWeight="bold", fontSize=11).encode(text="ele_gain:Q")
        ).properties(height=165))
        charts.append(("⛰️ Độ cao tích lũy / Elevation Gain từng km (m)", c_ele))

    return charts


def format_splits_df(splits):
    """Định dạng bảng Splits sang tiếng Việt gọn gàng, ẩn cột cảm biến không có dữ liệu."""
    df = pd.DataFrame(splits)
    if df.empty:
        return df
    rename_map = {
        "km_label": "Chặng",
        "distance_km": "Quãng đường (km)",
        "pace_str": "Pace (/km)",
        "avg_hr": "Nhịp tim TB (bpm)",
        "avg_cadence": "Guồng chân (spm)",
        "ele_gain": "Leo dốc (m)",
    }
    cols = [k for k in rename_map if k in df.columns and df[k].notna().any()]
    return df[cols].rename(columns=rename_map)


# ==========================================
# 3. LƯU TRỮ, TRẠNG THÁI & CALLBACK
# ==========================================
@st.cache_resource
def get_storage():
    return cc.Storage(DATA_DIR)


def persist(pid):
    warn = get_storage().save_project(pid, st.session_state.projects[pid])
    if warn:
        st.session_state["load_warning"] = warn


def get_valid_keys():
    keys = cc.get_configured_api_keys()
    if len(keys) > 1:
        rr = st.session_state.get("key_rr", 0) % len(keys)
        keys = keys[rr:] + keys[:rr]
        st.session_state["key_rr"] = rr + 1
    return keys


def default_shoe_id(project):
    return next((s["id"] for s in project.get("shoes", []) if s.get("is_default")), None)


if "projects" not in st.session_state:
    _projects, _warn = get_storage().load_all()
    st.session_state.projects = _projects
    st.session_state.current_project_id = next(iter(_projects))
    if _warn:
        st.session_state["load_warning"] = _warn


def _find_plan(pid, plan_id):
    proj = st.session_state.projects.get(pid)
    return next((p for p in proj["plans"] if p["id"] == plan_id), None) if proj else None


def cb_log_edit(pid, plan_id, widget_key):
    plan = _find_plan(pid, plan_id)
    proj = st.session_state.projects.get(pid)
    if plan is None or proj is None:
        return
    name_to_id = {s["name"]: s["id"] for s in proj.get("shoes", [])}
    cc.apply_log_edits(
        plan,
        st.session_state[widget_key].get("edited_rows", {}),
        shoe_name_to_id=name_to_id,
        default_shoe_id=default_shoe_id(proj),
    )
    persist(pid)


def cb_feedback(pid, plan_id, widget_key):
    plan = _find_plan(pid, plan_id)
    if plan is not None:
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


# ==========================================
# HỘP THOẠI QUẢN LÝ & SAO LƯU DỰ ÁN (GIỮ SIDEBAR GỌN)
# ==========================================
def _render_project_manager(selected_proj_id):
    curr_project = st.session_state.projects[selected_proj_id]
    t_new, t_edit, t_backup = st.tabs(["➕ Tạo mới", "✏️ Đổi tên / Xóa", "💾 Sao lưu"])

    with t_new:
        with st.form("new_project_form"):
            new_p_name = st.text_input("Tên dự án")
            new_p_goal = st.selectbox("Mục tiêu", cc.GOALS)
            c_np1, c_np2 = st.columns(2)
            new_p_curr_pace = c_np1.text_input("Pace hiện tại", value="07:00")
            new_p_targ_pace = c_np2.text_input("Pace mục tiêu", value="05:30")
            new_p_dist = st.number_input("Max KM", min_value=1.0, value=10.0)
            c_rd1, c_rd2 = st.columns([2, 3])
            new_p_has_race = c_rd1.checkbox("Có ngày thi đấu")
            new_p_race_date = c_rd2.date_input("Ngày giải", min_value=cc.today_vn(), label_visibility="collapsed")
            new_p_injuries = st.text_area("Chấn thương", value="Không có", height=60)
            new_p_notes = st.text_area("Ghi chú HLV", value="80% Easy", height=60)
            new_p_days = st.multiselect("Ngày rảnh", cc.ALL_DAYS, default=["Thứ 3", "Thứ 5", "Chủ Nhật"])

            if st.form_submit_button("✨ Khởi tạo dự án", type="primary"):
                if not new_p_name.strip():
                    st.error("Nhập tên dự án.")
                elif not (cc.validate_pace(new_p_curr_pace) and cc.validate_pace(new_p_targ_pace)):
                    st.error("Pace phải đúng định dạng mm:ss (vd 06:30).")
                elif not new_p_days:
                    st.error("Chọn ít nhất 1 ngày tập.")
                else:
                    new_id = cc.new_id()
                    st.session_state.projects[new_id] = {
                        "name": new_p_name.strip(),
                        "created_at": cc.today_vn().isoformat(),
                        "profile": {
                            "goal": new_p_goal, "current_pace": new_p_curr_pace.strip(),
                            "target_pace": new_p_targ_pace.strip(), "target_time": "",
                            "max_distance": new_p_dist, "injuries": new_p_injuries,
                            "notes": new_p_notes, "days": new_p_days,
                            "race_date": new_p_race_date.strftime("%Y-%m-%d") if new_p_has_race else "",
                        },
                        "shoes": [], "plans": [], "draft": None, "memory": cc.default_memory(),
                    }
                    st.session_state.current_project_id = new_id
                    persist(new_id)
                    st.rerun()

    with t_edit:
        rename_val = st.text_input("Đổi tên dự án:", value=curr_project["name"], key=f"rename_{selected_proj_id}")
        if stretch_button("💾 Lưu tên mới", key=f"save_name_{selected_proj_id}"):
            if rename_val.strip() and rename_val.strip() != curr_project["name"]:
                curr_project["name"] = rename_val.strip()
                persist(selected_proj_id)
                st.rerun()
        st.divider()
        confirm_delete = st.checkbox(
            f"Xác nhận xóa vĩnh viễn '{curr_project['name']}'", key=f"confirm_del_{selected_proj_id}"
        )
        if stretch_button("🗑️ Xóa dự án hiện tại", type="primary", key=f"del_btn_{selected_proj_id}"):
            if len(st.session_state.projects) <= 1:
                st.error("Phải giữ lại ít nhất 1 dự án!")
            elif not confirm_delete:
                st.warning("Tick ô xác nhận trước khi xóa.")
            else:
                del st.session_state.projects[selected_proj_id]
                get_storage().delete_project(selected_proj_id)
                st.session_state.current_project_id = next(iter(st.session_state.projects))
                st.rerun()

    with t_backup:
        c_dl1, c_dl2 = st.columns(2)
        c_dl1.download_button(
            "⬇️ Sao lưu tất cả (JSON)",
            data=json.dumps(st.session_state.projects, ensure_ascii=False, indent=2),
            file_name=f"running_backup_{cc.today_vn():%Y%m%d}.json", mime="application/json",
            key="dl_backup", **BTN_STRETCH,
        )
        c_dl2.download_button(
            "⬇️ Xuất dự án (CSV)",
            data=cc.project_to_csv(curr_project).encode("utf-8-sig"),
            file_name=f"{curr_project['name']}.csv", mime="text/csv", key="dl_csv", **BTN_STRETCH,
        )
        up = st.file_uploader("Khôi phục từ file JSON", type="json", key="restore_file")
        if up is not None and stretch_button("📥 Nhập vào (gộp, không ghi đè)", type="primary", key="restore_btn"):
            try:
                added = cc.import_projects(st.session_state.projects, json.loads(up.getvalue().decode("utf-8")))
                for _pid, _pd in added.items():
                    st.session_state.projects[_pid] = _pd
                    persist(_pid)
                st.toast(f"Đã nhập {len(added)} dự án.", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Không nhập được: {str(e)[:200]}")


if hasattr(st, "dialog"):
    @st.dialog("⚙️ Quản lý & Sao lưu dự án")
    def open_project_manager(selected_proj_id):
        _render_project_manager(selected_proj_id)
else:
    open_project_manager = None

# ==========================================
# 4. CẢNH BÁO & SIDEBAR GỌN NHẸ
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
        st.session_state.current_project_id = next(iter(st.session_state.projects))

    project_options = {pid: pdata["name"] for pid, pdata in st.session_state.projects.items()}
    pid_list = list(project_options.keys())
    selected_proj_id = st.selectbox(
        "Chọn Dự Án Hiện Tại:",
        options=pid_list,
        format_func=lambda x: project_options[x],
        index=pid_list.index(st.session_state.current_project_id),
        label_visibility="collapsed",
    )
    st.session_state.current_project_id = selected_proj_id
    curr_project = st.session_state.projects[selected_proj_id]

    if open_project_manager is not None:
        if stretch_button("⚙️ Quản lý & Sao lưu dự án", key="open_proj_mgr"):
            open_project_manager(selected_proj_id)
    else:
        with st.expander("⚙️ Quản lý & Sao lưu dự án"):
            _render_project_manager(selected_proj_id)

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
        placeholder="59:30 / 1:55:00",
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

    with st.expander("📝 Chấn thương & ghi chú"):
        updated_injuries = st.text_area("Chấn thương", value=prof.get("injuries", ""), height=68, key=f"p_inj_{pid}")
        updated_notes = st.text_area("Ghi chú riêng", value=prof.get("notes", ""), height=68, key=f"p_notes_{pid}")
    updated_days = st.multiselect("Lịch rảnh", cc.ALL_DAYS, default=prof.get("days", []), key=f"p_days_{pid}")

    new_profile = {
        "goal": updated_goal,
        "current_pace": updated_curr_pace.strip(),
        "target_pace": updated_targ_pace.strip(),
        "target_time": updated_time.strip() if time_ok else prof.get("target_time", ""),
        "max_distance": updated_dist,
        "injuries": updated_injuries,
        "notes": updated_notes,
        "days": updated_days,
        "race_date": updated_race_date.strftime("%Y-%m-%d") if updated_is_racing else "",
    }
    profile_valid = pace_ok and time_ok
    if profile_valid and any((curr_project.get("profile") or {}).get(k) != v for k, v in new_profile.items()):
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
# 5. HERO BANNER & DỮ LIỆU CHUNG
# ==========================================
days_left = cc.days_to_race(curr_project["profile"])
phase_text = cc.PHASE_LABEL.get(cc.training_phase(days_left), "Duy trì")
shoe_stats_now = cc.compute_shoe_stats(curr_project)
worn_shoes = [x for x in shoe_stats_now if x["pct"] >= 85]
today = cc.today_vn()
plans = curr_project.get("plans", [])
stats_by_id = {p["id"]: cc.plan_stats(p) for p in plans}
target_pace_now = cc.resolve_target_pace(curr_project["profile"])

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
    [
        ("Dự án", curr_project["name"]),
        ("Mục tiêu", curr_project["profile"].get("goal", "")),
        ("Pace đích", f"{target_pace_now}/km"),
    ],
    chips,
)

tab_today, tab_current, tab_history, tab_gear_tools = st.tabs([
    "🏠 Hôm nay",
    "📋 Lịch tuần mới",
    "📊 Lịch sử & Dashboard",
    "👟 Giày & Công cụ",
])

# ==========================================
# TAB 1: HÔM NAY
# ==========================================
with tab_today:
    col_l, col_r = st.columns([1.75, 1], gap="medium")
    focus_plan, focus_item, focus_mode, focus_date = find_focus_session(plans, today)
    last_plan = plans[-1] if plans else None
    last_stats = stats_by_id.get(last_plan["id"]) if last_plan else None

    with col_l:
        if focus_item:
            wt = str(focus_item.get("workout_type") or "")
            km_f = cc.km_planned(focus_item)
            day_nm = cc.normalize_day(focus_item.get("day"))
            kicker = (
                f"Hôm nay · {day_nm}, {focus_date:%d/%m}" if focus_mode == "today"
                else f"Buổi tiếp theo · {day_nm}, {focus_date:%d/%m}"
            )
            fs = stats_by_id[focus_plan["id"]]
            meta_txt = "" if wt == "Rest" else f"Pace mục tiêu {focus_item.get('pace_target') or '—'}/km"
            ui_kit.today_card(
                kicker, wt if wt == "Rest" else f"{wt} · {km_f:.1f} km", meta_txt,
                str(focus_item.get("notes") or ""), fs["rate"],
                f"Hoàn thành {fs['done']}/{fs['total']} buổi tuần này",
                ui_kit.TYPE_COLORS.get(wt, "#16A34A"), "Đã xong" if focus_item.get("completed") else "",
            )
            if focus_mode == "today" and cc.is_run(focus_item) and not focus_item.get("completed"):
                if stretch_button("✓ Đánh dấu đã xong buổi hôm nay", type="primary", key="mark_today_done"):
                    cc.mark_session_done(focus_item, default_shoe_id=default_shoe_id(curr_project))
                    persist(selected_proj_id)
                    st.rerun()
        elif plans:
            ui_kit.empty_state("Tuần này chưa có buổi nào", "Tạo kế hoạch cho tuần hiện tại ở thanh bên để thấy buổi tập hôm nay.")
        else:
            ui_kit.empty_state("Chưa có kế hoạch", "Bấm “🚀 Tạo kế hoạch tuần mới” ở thanh bên để AI lập giáo án đầu tiên.")

        if last_plan and last_stats:
            ui_kit.section_title("Lịch tuần gần nhất", f"{last_stats['done']}/{last_stats['total']} buổi")
            ui_kit.week_strip(
                last_plan.get("schedule") or [], normalize_day=cc.normalize_day,
                today_name=cc.ALL_DAYS[today.weekday()],
            )
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
        if last_plan and last_stats:
            ws_l = cc.parse_iso_date(last_plan.get("week_start"))
            overdue = [
                ws_l + timedelta(days=cc.ALL_DAYS.index(nd))
                for it_ in last_plan.get("schedule", [])
                if ws_l and cc.is_run(it_) and not it_.get("completed")
                and (nd := cc.normalize_day(it_.get("day"))) in cc.ALL_DAYS
                and ws_l + timedelta(days=cc.ALL_DAYS.index(nd)) < today
            ]
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
            {
                "icon": "👟", "title": x["name"], "sub": f"{x['total_km']}/{x['max_km']:g} km · {x['status']}",
                "pct": x["pct"],
                "color": "#DC2626" if x["total_km"] >= x["max_km"] else ("#D97706" if x["pct"] >= 80 else "#16A34A"),
            }
            for x in shoe_stats_now[:3]
        ])

# ==========================================
# TAB 2: LỊCH TUẦN MỚI (BẢN NHÁP)
# ==========================================
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

        meta = [
            f"📅 {cc.week_range_text(draft.get('week_start'))}",
            f"Giai đoạn: **{cc.PHASE_LABEL.get(draft.get('phase'), '-')}**",
        ]
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
                if stretch_button("🔄 Tạo lại buổi này", key=f"re_btn_{draft_id}"):
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
                                draft["ai_schedule"] = [
                                    r for r in draft["ai_schedule"] if cc.normalize_day(r.get("day")) != re_day
                                ] + [dict(res["item"])]
                            draft["_draft_id"] = cc.new_id()
                            persist(selected_proj_id)
                            st.rerun()
            else:
                st.caption("Chưa có buổi nào.")

        b1, b2 = st.columns(2)
        if b1.button("💾 LƯU VÀO DỰ ÁN", type="primary", key=f"save_draft_{draft_id}", **BTN_STRETCH):
            ws_iso = draft.get("week_start") or ""
            cleaned, _ = cc.validate_plan(records, curr_project["profile"], week_start=cc.parse_iso_date(ws_iso), lenient=True)
            if not cleaned:
                st.error("Cần ít nhất 1 buổi tập hợp lệ trước khi lưu.")
            else:
                new_week_index = cc.next_week_index(curr_project["plans"])
                curr_project["memory"] = cc.learn_from_edits(
                    curr_project.get("memory"), new_week_index, draft.get("ai_schedule"), cleaned
                )
                curr_project["plans"].append({
                    "id": cc.new_id(), "title": plan_title, "week_index": new_week_index,
                    "week_start": ws_iso, "created_at": cc.now_vn().strftime("%d/%m/%Y %H:%M"),
                    "week_summary": draft.get("week_summary", ""), "phase": draft.get("phase"),
                    "cap_km": draft.get("cap_km"), "schedule": cleaned, "user_feedback": "",
                })
                curr_project["draft"] = None
                persist(selected_proj_id)
                st.rerun()
        if b2.button("🗑️ Bỏ bản nháp", key=f"discard_draft_{draft_id}", **BTN_STRETCH):
            curr_project["draft"] = None
            persist(selected_proj_id)
            st.rerun()
    else:
        ui_kit.empty_state(
            "Chưa có bản nháp tuần mới",
            "Bấm “🚀 TẠO KẾ HOẠCH TUẦN MỚI” ở thanh bên trái để AI thiết kế giáo án phù hợp nhất với thể trạng của bạn.",
        )

# ==========================================
# TAB 3: LỊCH SỬ & DASHBOARD
# ==========================================
LOG_COLS = ["day", "date", "workout_type", "distance_km", "pace_target",
            "completed", "actual_km", "actual_pace", "shoe_name", "rpe", "pain", "notes"]
LOG_DISABLED = ["day", "date", "workout_type", "distance_km", "pace_target", "notes"]
NAN = float("nan")


def log_df(plan, shoes):
    id_to_name = {s["id"]: s["name"] for s in shoes}
    default_name = next((s["name"] for s in shoes if s.get("is_default")), "")
    rows = []
    for it in plan.get("schedule", []):
        rows.append({
            "day": it.get("day"), "date": cc.fmt_dm(it.get("date")), "workout_type": it.get("workout_type"),
            "distance_km": cc.km_planned(it), "pace_target": it.get("pace_target", ""),
            "completed": bool(it.get("completed")),
            "actual_km": NAN if (v := cc.to_float(it.get("actual_km"))) is None else v,
            "actual_pace": it.get("actual_pace", "") or "",
            "shoe_name": id_to_name.get(it.get("shoe_id"), default_name if cc.is_run(it) else ""),
            "rpe": NAN if (v := cc.to_float(it.get("rpe"))) is None else v,
            "pain": NAN if (v := cc.to_float(it.get("pain"))) is None else v,
            "notes": it.get("notes", ""),
        })
    return pd.DataFrame(rows, columns=LOG_COLS)


with tab_history:
    shoes_list = curr_project.get("shoes", [])
    shoe_names = [""] + [s["name"] for s in shoes_list]

    if not plans:
        ui_kit.empty_state(
            "Chưa có lịch tập nào được lưu",
            "Tạo và lưu tuần tập đầu tiên để xem Dashboard tiến độ, biểu đồ pace và đồng bộ file .fit / .gpx.",
        )
    else:
        all_stats = list(stats_by_id.values())
        total_runs = sum(s["total"] for s in all_stats)
        done_runs = sum(s["done"] for s in all_stats)
        rate = int(done_runs / total_runs * 100) if total_runs else 0
        total_km_done = sum(s["done_km"] for s in all_stats)
        dist = cc.type_distribution(plans)
        low_share = cc.low_intensity_share(dist)
        rows_w = cc.weekly_table(plans)

        latest = plans[-1]
        ui_kit.render_dynamic_dashboard(
            total_km_done, latest.get("schedule", []), [x["done_km"] for x in rows_w],
            latest.get("week_summary", ""), rate,
        )

        ui_kit.kpi_row([
            {"icon": "🗓️", "label": "Số tuần đã lưu", "value": len(plans), "unit": "tuần", "color": "#7C3AED"},
            {"icon": "🏃", "label": "Buổi hoàn thành", "value": f"{done_runs}/{total_runs}", "color": "#2563EB",
             "help": "Chỉ tính các buổi chạy/đi bộ có kế hoạch (không tính ngày Rest)."},
            {"icon": "✅", "label": "Tỷ lệ hoàn thành", "value": rate, "unit": "%", "color": "#16A34A"},
            {"icon": "📏", "label": "Tổng km đã chạy", "value": f"{total_km_done:.1f}", "unit": "km", "color": "#D92D20"},
            {"icon": "🔥", "label": "Streak ≥80%", "value": cc.completion_streak(plans), "unit": "tuần", "color": "#D97706"},
            {"icon": "💚", "label": "Km cường độ thấp", "value": "-" if low_share is None else low_share,
             "unit": "" if low_share is None else "%", "color": "#10B981", "help": "Mốc chuẩn 80/20 là ~80%"},
        ], cols=3)

        with st.expander("📈 Biểu đồ tổng quan (km tuần, pace, phân bổ loại buổi)", expanded=True):
            charts = [("Km mỗi tuần: đã chạy / kế hoạch", weekly_chart(rows_w))]
            pace_chart_obj = pace_chart(rows_w, target_pace_str=target_pace_now)
            if pace_chart_obj is not None:
                charts.append(("Pace thực tế TB (lên = nhanh hơn · nét đứt = mục tiêu)", pace_chart_obj))
            if dist:
                charts.append(("Km đã chạy theo loại buổi", dist_chart(dist)))
            for col, (caption, chart) in zip(st.columns([3] + [2] * (len(charts) - 1)), charts):
                with col:
                    st.caption(caption)
                    show_chart(chart)
            if pace_chart_obj is None:
                st.caption("💡 Tick 'Xong' hoặc đồng bộ file .fit / .gpx để xem đường xu hướng pace.")

        pending = st.session_state.get("pending_del_plan")

        for p_idx, plan in enumerate(reversed(plans)):
            plan_id = plan["id"]
            s = stats_by_id[plan_id]
            wr = cc.week_range_text(plan.get("week_start"))
            with st.expander(f"🗓️ {plan['title']}{' · ' + wr if wr else ''} (Tạo: {plan['created_at']})", expanded=(p_idx == 0)):
                st.markdown(
                    f'<div class="hlv-box"><strong>💡 Lời khuyên:</strong> {escape(str(plan.get("week_summary", "")))}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Hoàn thành {s['done']}/{s['total']} buổi · {s['done_km']:.1f}/{s['planned_km']:.1f} km"
                    + (f" · pace TB {cc.sec_to_pace(s['avg_pace'])}" if s["avg_pace"] else "")
                    + (f" · RPE TB {s['rpe_avg']:.1f}" if s["rpe_avg"] is not None else "")
                    + (f" · đau tối đa {s['max_pain']:.0f}/10" if s["max_pain"] is not None else "")
                )

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
                            "Chọn buổi tập để nạp dữ liệu:", range(len(run_sessions)),
                            format_func=lambda idx: session_labels[idx], key=f"fit_sel_{plan_id}",
                        )
                        target_session = run_sessions[sel_idx]
                        uploaded_act = c_fit2.file_uploader(
                            "Kéo thả file .fit hoặc .gpx vào đây:", type=["fit", "gpx"],
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
                                ov_time_sec = cc.parse_duration(ov_time_str) if ov_time_str.strip() else None
                                if ov_time_str.strip() and ov_time_sec is None:
                                    st.error("Thời gian Strava phải đúng định dạng mm:ss hoặc h:mm:ss.")
                                else:
                                    try:
                                        tele = cc.parse_activity_file(
                                            uploaded_act.name, uploaded_act.getvalue(),
                                            strava_km=ov_km if ov_km > 0 else None,
                                            strava_time_sec=ov_time_sec,
                                        )
                                        target_session["telemetry"] = tele
                                        cc.mark_session_done(
                                            target_session,
                                            actual_km=tele["distance_km"],
                                            actual_pace=tele.get("avg_pace"),
                                            default_shoe_id=default_shoe_id(curr_project),
                                        )
                                        persist(selected_proj_id)
                                        st.toast(f"Đã đồng bộ {tele['distance_km']} km từ {uploaded_act.name}!", icon="⌚")
                                        st.rerun()
                                    except ValueError as e:
                                        st.error(f"Lỗi định dạng hoặc dữ liệu file hoạt động: {e}")

                        tele_sessions = [it for it in run_sessions if it.get("telemetry")]
                        if tele_sessions:
                            view_it = target_session if target_session.get("telemetry") else tele_sessions[-1]
                            tele_data = view_it["telemetry"]
                            dur_str = cc.format_duration(tele_data.get("duration_sec", 0))
                            st.caption(
                                f"📊 Telemetry buổi **{view_it['day']}** (Nguồn: `{tele_data.get('source_file', 'activity')}`) · "
                                f"Quãng đường: **{tele_data.get('distance_km')} km** · "
                                f"Thời gian di chuyển: **{dur_str}** · Pace TB: **{tele_data.get('avg_pace')}/km**"
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
                                    for col_t, (cap_t, ch_t) in zip(st.columns(len(row_items)), row_items):
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

                a1, a2 = st.columns(2)
                ics = cc.plan_to_ics(curr_project["name"], plan)
                if ics:
                    a1.download_button(
                        "📅 Xuất lịch (.ics)", data=ics, file_name=f"{plan['title']}.ics",
                        mime="text/calendar", key=f"ics_{selected_proj_id}_{plan_id}", **BTN_STRETCH,
                    )
                if pending == (selected_proj_id, plan_id):
                    a2.warning("Xóa tuần này? Không thể hoàn tác.")
                    d1, d2 = a2.columns(2)
                    d1.button("✅ Xóa", type="primary", key=f"yes_del_{plan_id}", on_click=cb_delete_plan, args=(selected_proj_id, plan_id), **BTN_STRETCH)
                    d2.button("Hủy", key=f"no_del_{plan_id}", on_click=cb_cancel_delete, **BTN_STRETCH)
                else:
                    a2.button(
                        "🗑️ Xóa tuần này", key=f"del_plan_{selected_proj_id}_{plan_id}",
                        on_click=cb_ask_delete, args=(selected_proj_id, plan_id), **BTN_STRETCH,
                    )

# ==========================================
# TAB 4: GIÀY & CÔNG CỤ
# ==========================================
with tab_gear_tools:
    st.subheader("👟 Theo dõi giày chạy")
    st.caption("Tự động cộng dồn số km từ các buổi chạy đã hoàn thành để cảnh báo thời điểm đệm giày hết độ đàn hồi.")

    c_shoe_list, c_shoe_add = st.columns([3, 2])
    with c_shoe_list:
        if not shoe_stats_now:
            ui_kit.empty_state("Chưa có đôi giày nào", "Thêm đôi giày chạy của bạn ở khung bên phải để bắt đầu theo dõi số km.")
        else:
            for s in shoe_stats_now:
                ui_kit.shoe_card(s)

            c_act1, c_act2 = st.columns(2)
            sel_shoe_id = c_act1.selectbox(
                "Chọn giày thao tác:", [s["id"] for s in shoe_stats_now],
                format_func=lambda sid: next(x["name"] for x in shoe_stats_now if x["id"] == sid),
                key=f"shoe_act_sel_{selected_proj_id}",
            )
            if c_act2.button("⭐ Đặt làm giày mặc định", key=f"shoe_def_{selected_proj_id}", **BTN_STRETCH):
                for sh in curr_project["shoes"]:
                    sh["is_default"] = (sh["id"] == sel_shoe_id)
                persist(selected_proj_id)
                st.rerun()
            if c_act2.button("🗑️ Xóa đôi giày này", key=f"shoe_del_{selected_proj_id}", **BTN_STRETCH):
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
                if st.form_submit_button("👟 Thêm vào tủ giày", type="primary"):
                    if not sh_name.strip():
                        st.error("Nhập tên đôi giày.")
                    else:
                        if sh_def or not curr_project.get("shoes"):
                            sh_def = True
                            for existing_sh in curr_project.setdefault("shoes", []):
                                existing_sh["is_default"] = False
                        curr_project.setdefault("shoes", []).append({
                            "id": cc.new_id(), "name": sh_name.strip(), "brand": sh_brand.strip(),
                            "initial_km": float(sh_init), "max_km": float(sh_max), "is_default": sh_def,
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
            st.dataframe(pd.DataFrame(cc.predict_race_times(t_dist, t_sec)), hide_index=True, **EDITOR_STRETCH)
        else:
            st.warning("Nhập đúng định dạng thời gian (vd: 32:00 hoặc 1:45:00).")

    with c_tool2:
        st.subheader("❤️ Vùng nhịp tim")
        st.caption("Hữu ích khi chạy thời tiết nóng ẩm (nên ưu tiên giữ nhịp tim Zone 2 cho bài Easy/Long Run).")
        age = st.number_input("Tuổi của bạn:", min_value=12, max_value=90, value=21)
        custom_max_hr = st.number_input("Nhịp tim tối đa HRmax (mặc định 220 - tuổi):", min_value=120, max_value=230, value=220 - age)
        st.dataframe(pd.DataFrame(cc.compute_hr_zones(custom_max_hr)), hide_index=True, **EDITOR_STRETCH)
