# -*- coding: utf-8 -*-
"""Logic thuần của AI Running Coach: lưu trữ SQLite WAL, kiểm tra kế hoạch,
tính tải tập, dự đoán thành tích, phân tích FIT/GPX chuẩn Strava, theo dõi giày, gọi Gemini."""

import copy
import csv
import gzip as _gzip
import io
import json
import math
import os
import re
import shutil
import sqlite3
import struct
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile as _zipfile
from collections import deque
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

try:
    import streamlit as st
except ImportError:
    st = None

try:
    from supabase import create_client
except ImportError:
    create_client = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import fitdecode
except ImportError:
    fitdecode = None

try:
    import gpxpy
except ImportError:
    gpxpy = None

try:
    from zoneinfo import ZoneInfo
    VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    VN_TZ = timezone(timedelta(hours=7))

# ==========================================
# CẤU HÌNH API KEYS & THỨ TỰ ƯU TIÊN MODEL AI
# ==========================================
HARDCODED_API_KEYS = [
    # Dán thẳng các API key của bạn vào đây, mỗi key 1 dòng:
    # "",
    # "",
]

# Ưu tiên Hydrogen trước; hết lượt (429/quota) hoặc lỗi model sẽ tự động switch sang 3.8 Flash
MODEL_PRIORITY = [
    "hydrogen",
    "gemini-3.8-flash",
]
MODEL_OPTIONS = list(MODEL_PRIORITY)

# ==========================================
# HẰNG SỐ
# ==========================================
ALL_DAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
GOALS = ["5K", "10K", "Half-Marathon (21K)", "Full Marathon (42K)", "Trail", "Phục hồi"]
GOAL_DISTANCE_KM = {
    "5K": 5.0, "10K": 10.0, "Half-Marathon (21K)": 21.0975, "Full Marathon (42.2K)": 42.195,
    "Full Marathon (42K)": 42.195,
}
WORKOUT_TYPES = ["Easy Run", "Long Run", "Interval", "Tempo", "Threshold", "Walk", "Rest"]
HARD_TYPES = ("Interval", "Tempo", "Threshold")
LOW_INTENSITY_TYPES = ("Easy Run", "Long Run", "Walk")

# Ngưỡng phân tích sinh lý & học thói quen (tính bằng Python thuần, 0 token)
HR_SPIKE_BPM, HR_SPIKE_WINDOW_SEC = 20, 10      # HR nhảy >20 bpm trong 10 giây = nhiễu
CADENCE_LOCK_MIN_HR, CADENCE_LOCK_TOL = 150, 3  # HR ≈ cadence (±3) khi >=150 bpm = nghi cadence lock
HR_BAD_KM_RATIO = 0.25                          # km có >25% mẫu HR nghi nhiễu thì loại
HR_KM_JUMP_BPM = 20                             # avg HR 2 km liên tiếp lệch >20 bpm = nhiễu (dùng cho dữ liệu cũ)
DRIFT_WATCH_PCT, DRIFT_LIMIT_PCT = 5.0, 8.0
DRIFT_MIN_KM = 6                                # cần >=6 km sau khi bỏ km khởi động
DRIFT_MIN_VALID_SHARE = 0.75
DRIFT_MAX_PACE_SPREAD = 1.25                    # pace chậm nhất / nhanh nhất; vượt = bài không đều (interval/dốc)
DRIFT_MAX_ELE_PER_KM = 25.0                     # m leo dốc / km
CONFIRM_RPE, CONFIRM_PAIN = 7, 3                # lớp xác thực chéo bằng RPE / đau
HABIT_MIN_WEEKS, HABIT_LOG_WEEKS, HABIT_MAX_RULES = 2, 6, 5
WEEKLY_INCREASE = 0.15                         # trần tăng km tuần so với km thực tế tuần trước
HABIT_KM_DELTA = 1.0                            # chỉnh km >= 1.0 mới tính là "sửa có chủ đích"

PHASE_LABEL = {
    "Base": "Xây nền (Base)", "Build": "Tăng tiến (Build)", "Peak": "Đỉnh phong độ (Peak)",
    "Taper": "Giảm tải (Taper)", "Race": "Tuần thi đấu (Race)", "Maintain": "Duy trì nền tảng",
}
PHASE_BLEND = {"Base": 0.0, "Build": 0.35, "Peak": 0.7, "Taper": 0.7, "Race": 0.7, "Maintain": 0.2}
ZONE_OFFSETS = {
    "Easy Run": (45, 90), "Long Run": (35, 80), "Tempo": (10, 25),
    "Threshold": (5, 15), "Interval": (-20, -5),
}

DayName = Literal["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
WorkoutName = Literal["Easy Run", "Long Run", "Interval", "Tempo", "Threshold", "Walk", "Rest"]


class SessionModel(BaseModel):
    day: DayName
    workout_type: WorkoutName
    distance_km: float
    pace_target: str
    notes: str


class PlanModel(BaseModel):
    default_title: str
    week_summary: str
    schedule: list[SessionModel]


class AIOutputError(ValueError):
    """AI trả về dữ liệu không dùng được."""


# ==========================================
# TIỆN ÍCH CHUNG
# ==========================================
def new_id():
    return str(uuid.uuid4())[:8]


def to_float(v, default=None):
    if isinstance(v, (tuple, list)):
        v = v[0] if len(v) == 1 else None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if (math.isnan(f) or math.isinf(f)) else f


def round_half_km(val):
    return round(float(val) * 2) / 2.0


def to_text(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ("nan", "<NA>", "None", "NaT") else s


def sanitize_api_keys(keys_source):
    if not keys_source:
        return []
    raw_list = keys_source.split(",") if isinstance(keys_source, str) else list(keys_source)
    out, seen = [], set()
    for item in raw_list:
        k = str(item or "").strip()
        if k and not k.startswith("YOUR_") and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def get_configured_api_keys():
    """Gộp API keys từ HARDCODED_API_KEYS và st.secrets / biến môi trường (loại trùng)."""
    combined = list(HARDCODED_API_KEYS)
    secret_val = ""
    try:
        if st is not None:
            secret_val = st.secrets.get("GEMINI_API_KEYS", "")
    except Exception:
        secret_val = ""
    env_val = secret_val or os.environ.get("GEMINI_API_KEYS", "")
    if env_val:
        combined.extend(env_val.split(","))
    return sanitize_api_keys(combined)


def now_vn():
    return datetime.now(VN_TZ)


def today_vn():
    return now_vn().date()


def monday_of(d):
    return d - timedelta(days=d.weekday())


def default_week_start(today=None):
    today = today or today_vn()
    mon = monday_of(today)
    return mon if today.weekday() <= 2 else mon + timedelta(days=7)


def parse_iso_date(s):
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def fmt_dm(iso):
    d = parse_iso_date(iso)
    return d.strftime("%d/%m") if d else ""


def week_range_text(week_start_iso):
    ws = parse_iso_date(week_start_iso)
    if not ws:
        return ""
    return f"{ws:%d/%m/%Y} – {ws + timedelta(days=6):%d/%m/%Y}"


def session_date(week_start, day):
    if day not in ALL_DAYS or week_start is None:
        return None
    return week_start + timedelta(days=ALL_DAYS.index(day))


def normalize_day(day_str):
    s = str(day_str or "").strip().lower()
    table = {
        "thứ 2": "Thứ 2", "thứ hai": "Thứ 2", "t2": "Thứ 2", "monday": "Thứ 2",
        "thứ 3": "Thứ 3", "thứ ba": "Thứ 3", "t3": "Thứ 3", "tuesday": "Thứ 3",
        "thứ 4": "Thứ 4", "thứ tư": "Thứ 4", "t4": "Thứ 4", "wednesday": "Thứ 4",
        "thứ 5": "Thứ 5", "thứ năm": "Thứ 5", "t5": "Thứ 5", "thursday": "Thứ 5",
        "thứ 6": "Thứ 6", "thứ sáu": "Thứ 6", "t6": "Thứ 6", "friday": "Thứ 6",
        "thứ 7": "Thứ 7", "thứ bảy": "Thứ 7", "t7": "Thứ 7", "saturday": "Thứ 7",
        "chủ nhật": "Chủ Nhật", "cn": "Chủ Nhật", "sunday": "Chủ Nhật",
    }
    return table.get(s, str(day_str or "").strip())


_TYPE_ALIASES = {t.lower(): t for t in WORKOUT_TYPES}
_TYPE_ALIASES.update({
    "easy": "Easy Run", "long": "Long Run", "recovery": "Easy Run",
    "recovery run": "Easy Run", "intervals": "Interval", "rest day": "Rest"
})


def normalize_type(s):
    return _TYPE_ALIASES.get(str(s or "").strip().lower())


# ==========================================
# PACE, THỜI GIAN & CÔNG CỤ DỰ ĐOÁN
# ==========================================
_PACE_RE = re.compile(r"(\d{1,2}):([0-5]\d)")


def validate_pace(pace_str):
    s = (pace_str or "").strip()
    return bool(re.fullmatch(r"\d{1,2}:[0-5]\d", s)) and (pace_to_sec(s) or 0) > 0


def pace_to_sec(s):
    m = _PACE_RE.search(str(s or ""))
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def sec_to_pace(sec):
    sec = max(0, int(round(sec)))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def format_duration(total_sec):
    total_sec = max(0, int(round(total_sec)))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def parse_duration(s):
    parts = str(s or "").strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts]
    if len(nums) == 3:
        h, m, sec = nums
        if m > 59 or sec > 59:
            return None
        total = h * 3600 + m * 60 + sec
    else:
        m, sec = nums
        if sec > 59:
            return None
        total = m * 60 + sec
    return total or None


def resolve_target_pace(profile):
    dist = GOAL_DISTANCE_KM.get(profile.get("goal"))
    t = parse_duration(profile.get("target_time"))
    if dist and t:
        return sec_to_pace(t / dist)
    return profile.get("target_pace") or "05:30"


def predict_race_times(known_dist_km, known_time_sec):
    if known_dist_km <= 0 or known_time_sec <= 0:
        return []
    targets = [
        ("5K", 5.0),
        ("10K", 10.0),
        ("Half Marathon (21.1K)", 21.0975),
        ("Full Marathon (42.2K)", 42.195),
    ]
    results = []
    for label, d2 in targets:
        t2 = known_time_sec * ((d2 / known_dist_km) ** 1.06)
        pace_sec = t2 / d2
        results.append({
            "distance": label,
            "predicted_time": format_duration(t2),
            "avg_pace": f"{sec_to_pace(pace_sec)} /km",
        })
    return results


def compute_hr_zones(max_hr):
    if not max_hr or max_hr < 100:
        return []
    zones = [
        ("Zone 1 - Phục hồi (Recovery)", 0.50, 0.60, "Đi bộ nhanh, thả lỏng sau bài nặng"),
        ("Zone 2 - Nền tảng (Aerobic / Easy)", 0.60, 0.70, "Đốt mỡ, xây hệ tim mạch, nói chuyện thoải mái"),
        ("Zone 3 - Nhịp độ (Tempo / Marathon)", 0.70, 0.80, "Tăng sức bền tốc độ, hơi thở sâu nhưng kiểm soát"),
        ("Zone 4 - Ngưỡng (Threshold)", 0.80, 0.90, "Chịu đựng axit lactic, chạy ngưỡng 10K–21K"),
        ("Zone 5 - Tối đa (VO2 Max / Interval)", 0.90, 1.00, "Bứt tốc ngắn, cải thiện công suất tối đa"),
    ]
    return [
        {
            "zone": name,
            "bpm": f"{int(round(max_hr * lo))} – {int(round(max_hr * hi))} bpm",
            "percent": f"{int(lo*100)}–{int(hi*100)}%",
            "purpose": desc,
        }
        for name, lo, hi, desc in zones
    ]


# ==========================================
# PHÂN TÍCH FILE HOẠT ĐỘNG (.FIT / .GPX) CHUẨN STRAVA & GOTOES
# ==========================================
def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _norm_coord(raw_val, limit):
    if raw_val is None:
        return None
    v = float(raw_val)
    if abs(v) > 180.0:
        if v >= 2147483648.0:
            v -= 4294967296.0
        v = v * (180.0 / 2147483648.0)
    if -limit <= v <= limit and abs(v) > 1e-6:
        return v
    return None


def _safe_dt_seconds(t_prev, t_curr):
    """Tính chênh lệch giây an toàn giữa 2 datetime bất kể naive hay timezone-aware."""
    if t_prev is None or t_curr is None:
        return None
    if t_prev.tzinfo is None:
        t_prev = t_prev.replace(tzinfo=timezone.utc)
    if t_curr.tzinfo is None:
        t_curr = t_curr.replace(tzinfo=timezone.utc)
    return (t_curr - t_prev).total_seconds()


def _aggregate_splits(points, session_override=None):
    if not points and session_override and session_override.get("total_distance") and session_override.get("total_timer_time"):
        td = float(session_override["total_distance"])
        tt = float(session_override["total_timer_time"])
        if td > 0 and tt > 0:
            n_steps = max(1, int(round(tt / 5.0)))
            points = [(td / n_steps, tt / n_steps, None, None, None) for _ in range(n_steps)]

    if not points:
        diag = session_override.get("_diag", "") if session_override else ""
        raise ValueError(f"File không có dữ liệu tọa độ hoặc quãng đường hợp lệ. {diag}".strip())

    raw_dist = sum(p[0] for p in points)
    raw_time = sum(p[1] for p in points)

    dist_scale = 1.0
    time_scale = 1.0
    if session_override:
        if session_override.get("total_distance") and raw_dist > 0:
            dist_scale = float(session_override["total_distance"]) / raw_dist
        if session_override.get("total_timer_time") and raw_time > 0:
            time_scale = float(session_override["total_timer_time"]) / raw_time

    splits = []
    cur_km_idx = 1
    km_dist, km_time = 0.0, 0.0
    hrs, cads = [], []
    ele_gain = 0.0
    ele_window = []
    last_smooth_ele = None

    total_dist, total_time, total_ele_gain = 0.0, 0.0, 0.0
    all_hrs, all_cads = [], []
    hr_hist = deque()          # (thời điểm, hr) trong 10 giây gần nhất để bắt HR nhảy vọt
    km_hr_n, km_hr_bad = 0, 0  # số mẫu HR / số mẫu nghi nhiễu trong km đang chạy

    for d_raw, dt_raw, hr, cad, ele in points:
        d_m = d_raw * dist_scale
        dt_s = dt_raw * time_scale

        total_dist += d_m
        total_time += dt_s
        km_dist += d_m
        km_time += dt_s

        if hr and 40 <= hr <= 230:
            hrs.append(hr)
            all_hrs.append(hr)
            while hr_hist and total_time - hr_hist[0][0] > HR_SPIKE_WINDOW_SEC:
                hr_hist.popleft()
            spike = any(abs(hr - h) > HR_SPIKE_BPM for _, h in hr_hist)
            hr_hist.append((total_time, hr))
            spm_now = (cad * 2 if cad < 120 else cad) if (cad and cad > 0) else None
            km_hr_n += 1
            if spike or (spm_now and hr >= CADENCE_LOCK_MIN_HR and abs(hr - spm_now) <= CADENCE_LOCK_TOL):
                km_hr_bad += 1
        if cad and cad > 0:
            spm = cad * 2 if cad < 120 else cad
            if 100 <= spm <= 240:
                cads.append(spm)
                all_cads.append(spm)

        if ele is not None:
            ele_window.append(ele)
            if len(ele_window) > 5:
                ele_window.pop(0)
            if len(ele_window) == 5:
                avg_ele = sum(ele_window) / 5.0
                if last_smooth_ele is None:
                    last_smooth_ele = avg_ele
                else:
                    diff = avg_ele - last_smooth_ele
                    if 1.5 <= diff < 15.0:
                        ele_gain += diff
                        total_ele_gain += diff
                        last_smooth_ele = avg_ele
                    elif diff < -1.5:
                        last_smooth_ele = avg_ele

        while km_dist >= 999.999:
            ratio = min(1.0, 1000.0 / km_dist) if km_dist > 0 else 1.0
            split_time = km_time * ratio
            pace_sec = split_time
            splits.append({
                "km_label": f"Km {cur_km_idx}",
                "km_num": cur_km_idx,
                "distance_km": 1.0,
                "pace_sec": round(pace_sec),
                "pace_str": sec_to_pace(pace_sec),
                "avg_hr": round(sum(hrs) / len(hrs)) if hrs else None,
                "avg_cadence": round(sum(cads) / len(cads)) if cads else None,
                "ele_gain": round(ele_gain * ratio, 1),
                "hr_bad_ratio": round(km_hr_bad / km_hr_n, 2) if km_hr_n else None,
            })
            cur_km_idx += 1
            km_dist = max(0.0, km_dist - 1000.0)
            km_time = max(0.0, km_time - split_time)
            ele_gain *= (1.0 - ratio)
            hrs, cads = [], []
            km_hr_n, km_hr_bad = 0, 0

    if km_dist >= 30.0:
        pace_sec = (km_time / (km_dist / 1000.0)) if km_dist > 0 else 0
        rem_km = round(km_dist / 1000.0, 2)
        splits.append({
            "km_label": f"Km {cur_km_idx} ({rem_km:.2f})",
            "km_num": cur_km_idx,
            "distance_km": rem_km,
            "pace_sec": round(pace_sec),
            "pace_str": sec_to_pace(pace_sec),
            "avg_hr": round(sum(hrs) / len(hrs)) if hrs else None,
            "avg_cadence": round(sum(cads) / len(cads)) if cads else None,
            "ele_gain": round(ele_gain, 1),
            "hr_bad_ratio": round(km_hr_bad / km_hr_n, 2) if km_hr_n else None,
        })

    if session_override:
        if session_override.get("total_distance"):
            total_dist = float(session_override["total_distance"])
        if session_override.get("total_timer_time"):
            total_time = float(session_override["total_timer_time"])
        if session_override.get("total_ascent") is not None:
            total_ele_gain = float(session_override["total_ascent"])

    dist_km = round(total_dist / 1000.0, 2)
    avg_pace_sec = (total_time / (total_dist / 1000.0)) if total_dist > 0 else 0
    return {
        "distance_km": dist_km,
        "duration_sec": round(total_time),
        "avg_pace": sec_to_pace(avg_pace_sec) if avg_pace_sec > 0 else "",
        "avg_hr": round(sum(all_hrs) / len(all_hrs)) if all_hrs else None,
        "avg_cadence": round(sum(all_cads) / len(all_cads)) if all_cads else None,
        "total_ele_gain": round(total_ele_gain, 1),
        "splits": splits,
    }


def _records_to_points(records, mode="auto"):
    points = []
    prev_dist, prev_ts, prev_lat, prev_lon = None, None, None, None
    pend_dist, pend_dt = 0.0, 0.0
    pend_hrs, pend_cads = [], []
    pend_ele = None
    is_paused = False

    for rec in records:
        kind = rec[0]
        if kind == "event":
            ev_state = rec[1]
            if ev_state == "stop":
                is_paused = True
            elif ev_state == "start":
                is_paused = False
                prev_ts = None
            continue

        _, ts_sec, dist, lat, lon, spd, hr, cad, ele = rec

        if prev_ts is None:
            prev_ts = ts_sec if ts_sec is not None else 0.0
            if dist is not None and dist >= 0:
                prev_dist = dist
            if lat is not None and lon is not None:
                prev_lat, prev_lon = lat, lon
            if hr and 40 <= hr <= 230:
                pend_hrs.append(hr)
            if cad and cad > 0:
                pend_cads.append(cad)
            if ele is not None:
                pend_ele = ele
            continue

        if ts_sec is not None:
            dt_s = ts_sec - prev_ts
            if dt_s < 0:
                prev_ts = ts_sec
                continue
            prev_ts = ts_sec
        else:
            dt_s = 1.0

        d_dist = 0.0
        if dist is not None and dist >= 0:
            if prev_dist is not None and dist >= prev_dist:
                d_dist = dist - prev_dist
            prev_dist = dist

        d_gps = 0.0
        if lat is not None and lon is not None:
            if prev_lat is not None and prev_lon is not None:
                step_m = _haversine_m(prev_lat, prev_lon, lat, lon)
                if step_m < 500.0:
                    d_gps = step_m
            prev_lat, prev_lon = lat, lon

        d_spd = (spd * dt_s) if (spd is not None and spd > 0 and dt_s > 0) else 0.0

        if mode == "dist":
            d_m = d_dist if d_dist > 0 else d_gps
        elif mode == "gps":
            d_m = d_gps if d_gps > 0 else d_dist
        elif mode == "speed":
            d_m = d_spd
        else:
            d_m = max(d_dist, d_gps) if max(d_dist, d_gps) > 0 else d_spd

        if is_paused:
            if 0 < dt_s <= 20.0 and d_m > 0.3:
                is_paused = False
            else:
                pend_dist, pend_dt = 0.0, 0.0
                pend_hrs, pend_cads, pend_ele = [], [], None
                continue

        if dt_s > 600.0:
            pend_dist, pend_dt = 0.0, 0.0
            pend_hrs, pend_cads, pend_ele = [], [], None
            continue

        pend_dist += d_m
        pend_dt += dt_s
        if hr and 40 <= hr <= 230:
            pend_hrs.append(hr)
        if cad and cad > 0:
            pend_cads.append(cad)
        if ele is not None:
            pend_ele = ele

        if pend_dt <= 0 or (pend_dist <= 0.0 and pend_dt < 12.0):
            continue

        if pend_dist > 0.0:
            avg_speed = pend_dist / pend_dt
            if 0.05 <= avg_speed <= 25.0:
                avg_hr = (sum(pend_hrs) / len(pend_hrs)) if pend_hrs else None
                avg_cad = (sum(pend_cads) / len(pend_cads)) if pend_cads else None
                points.append((pend_dist, pend_dt, avg_hr, avg_cad, pend_ele))

        pend_dist, pend_dt = 0.0, 0.0
        pend_hrs, pend_cads, pend_ele = [], [], None

    return points


def _finalize_fit_records(records, session_info):
    rec_rows = [r for r in records if r[0] == "record"]
    gps_cnt = sum(1 for r in rec_rows if r[3] is not None and r[4] is not None)
    dist_vals = [r[2] for r in rec_rows if r[2] is not None and r[2] > 0]

    session_info = dict(session_info or {})
    session_info["_diag"] = (
        f"(Chi tiết file: {len(rec_rows)} records, {gps_cnt} điểm GPS, "
        f"max_dist={round(max(dist_vals), 1) if dist_vals else 0}m, "
        f"session_dist={round(session_info.get('total_distance') or 0, 1)}m)"
    )

    best_points = []
    for mode in ("dist", "gps", "auto", "speed"):
        pts = _records_to_points(records, mode=mode)
        tot_d = sum(p[0] for p in pts)
        if tot_d >= 50.0:
            best_points = pts
            break
        if tot_d > sum(p[0] for p in best_points):
            best_points = pts

    if not best_points and rec_rows:
        ts_list = [r[1] for r in rec_rows if r[1] is not None]
        if len(ts_list) >= 2 and ts_list[-1] > ts_list[0]:
            dur_s = ts_list[-1] - ts_list[0]
        else:
            dur_s = float(len(rec_rows))
        if session_info.get("total_timer_time"):
            dur_s = float(session_info["total_timer_time"])
        hrs_only = [r[6] for r in rec_rows if r[6] and 40 <= r[6] <= 230]
        cads_raw = [r[7] for r in rec_rows if r[7] and r[7] > 0]
        cads_only = [c for c in ((x * 2 if x < 120 else x) for x in cads_raw) if 100 <= c <= 240]
        dist_m = float(session_info.get("total_distance") or (max(dist_vals) if dist_vals else 0.0))
        dist_km = round(dist_m / 1000.0, 2)
        avg_pace = sec_to_pace(dur_s / (dist_m / 1000.0)) if (dist_m > 0 and dur_s > 0) else ""
        return {
            "distance_km": dist_km,
            "duration_sec": max(1, round(dur_s)),
            "avg_pace": avg_pace,
            "avg_hr": round(sum(hrs_only) / len(hrs_only)) if hrs_only else None,
            "avg_cadence": round(sum(cads_only) / len(cads_only)) if cads_only else None,
            "total_ele_gain": round(float(session_info.get("total_ascent") or 0.0), 1),
            "splits": [],
        }

    return _aggregate_splits(best_points, session_override=session_info)


_FIT_BASE_TYPES = {
    0x00: ("B", 1, 0xFF),
    0x01: ("b", 1, 0x7F),
    0x02: ("B", 1, 0xFF),
    0x83: ("h", 2, 0x7FFF),
    0x84: ("H", 2, 0xFFFF),
    0x85: ("i", 4, 0x7FFFFFFF),
    0x86: ("I", 4, 0xFFFFFFFF),
    0x07: ("s", 1, None),
    0x88: ("f", 4, None),
    0x89: ("d", 8, None),
    0x0A: ("B", 1, 0x00),
    0x8B: ("H", 2, 0x0000),
    0x8C: ("I", 4, 0x00000000),
    0x0D: ("B", 1, None),
    0x8E: ("q", 8, 0x7FFFFFFFFFFFFFFF),
    0x8F: ("Q", 8, 0xFFFFFFFFFFFFFFFF),
    0x90: ("Q", 8, 0x0000000000000000),
}


def _parse_fit_raw_binary(raw_bytes, session_override=None):
    if len(raw_bytes) < 14:
        raise ValueError("File .fit quá ngắn hoặc bị hỏng.")
    header_size = raw_bytes[0]
    if header_size < 12 or len(raw_bytes) < header_size or raw_bytes[8:12] != b".FIT":
        raise ValueError("File không đúng định dạng FIT chuẩn.")

    data_size = struct.unpack("<I", raw_bytes[4:8])[0]
    if data_size == 0 or header_size + data_size > len(raw_bytes):
        end_pos = max(header_size, len(raw_bytes) - 2)
    else:
        end_pos = header_size + data_size
    pos = header_size

    defs = {}
    records = []
    last_base_ts = None
    session_info = {}
    lap_dist = 0.0
    lap_time = 0.0

    while pos < end_pos:
        rh = raw_bytes[pos]
        pos += 1

        if rh & 0x80:
            lmt = (rh >> 5) & 0x03
            ts_offset = rh & 0x1F
            defn = defs.get(lmt)
            if not defn:
                break
            comp_ts = None
            if last_base_ts is not None:
                comp_ts = (last_base_ts & ~0x1F) + ts_offset
                if ts_offset < (last_base_ts & 0x1F):
                    comp_ts += 0x20
                last_base_ts = comp_ts
        elif rh & 0x40:
            if pos + 5 > end_pos:
                break
            lmt = rh & 0x0F
            has_dev = bool(rh & 0x20)
            arch = ">" if raw_bytes[pos + 1] == 1 else "<"
            gmn = struct.unpack(arch + "H", raw_bytes[pos + 2:pos + 4])[0]
            n_fields = raw_bytes[pos + 4]
            pos += 5
            if pos + n_fields * 3 > end_pos:
                break
            f_specs = []
            for _ in range(n_fields):
                fnum, fsize, btype = raw_bytes[pos], raw_bytes[pos + 1], raw_bytes[pos + 2]
                pos += 3
                f_specs.append((fnum, fsize, btype))
            dev_bytes = 0
            if has_dev and pos < end_pos:
                n_dev = raw_bytes[pos]
                pos += 1
                for _ in range(n_dev):
                    if pos + 3 <= end_pos:
                        dev_bytes += raw_bytes[pos + 1]
                        pos += 3
            defs[lmt] = (arch, gmn, f_specs, dev_bytes)
            continue
        else:
            lmt = rh & 0x0F
            defn = defs.get(lmt)
            if not defn:
                break
            comp_ts = None

        arch, gmn, f_specs, dev_bytes = defn
        vals = {}
        if comp_ts is not None:
            vals[253] = comp_ts

        for fnum, fsize, btype in f_specs:
            if pos + fsize > end_pos:
                pos = end_pos
                break
            chunk = raw_bytes[pos:pos + fsize]
            pos += fsize
            info = _FIT_BASE_TYPES.get(btype)
            if not info:
                continue
            fmt_ch, unit_sz, invalid_val = info
            if fmt_ch == "s":
                continue
            count = fsize // unit_sz
            if count == 1:
                v = struct.unpack(arch + fmt_ch, chunk)[0]
                if invalid_val is None or v != invalid_val:
                    vals[fnum] = v
                    if fnum == 253:
                        last_base_ts = v
            elif count > 1:
                arr = struct.unpack(arch + (fmt_ch * count), chunk[:count * unit_sz])
                valid_arr = [x for x in arr if invalid_val is None or x != invalid_val]
                if valid_arr:
                    vals[fnum] = valid_arr[0]

        pos = min(end_pos, pos + dev_bytes)

        if gmn == 21:
            if vals.get(0) == 0:
                et = vals.get(1)
                if et in (1, 4):
                    records.append(("event", "stop"))
                elif et == 0:
                    records.append(("event", "start"))
        elif gmn == 19:
            if 9 in vals and vals[9] > 0:
                lap_dist += vals[9] / 100.0
            if 8 in vals and vals[8] > 0:
                lap_time += vals[8] / 1000.0
        elif gmn == 18:
            if 9 in vals and vals[9] > 0:
                session_info["total_distance"] = vals[9] / 100.0
            if 8 in vals and vals[8] > 0:
                session_info["total_timer_time"] = vals[8] / 1000.0
            if 22 in vals:
                session_info["total_ascent"] = float(vals[22])
        elif gmn == 20:
            ts_raw = float(vals[253]) if 253 in vals else None
            dist = (vals[5] / 100.0) if 5 in vals else None
            hr = float(vals[3]) if 3 in vals else None
            cad = float(vals[4]) if 4 in vals else None
            ele = ((vals[78] / 5.0) - 500.0) if 78 in vals else (((vals[2] / 5.0) - 500.0) if 2 in vals else None)
            spd = (vals[73] / 1000.0) if 73 in vals else ((vals[6] / 1000.0) if 6 in vals else None)
            lat = _norm_coord(vals.get(0), 90.0)
            lon = _norm_coord(vals.get(1), 180.0)
            records.append(("record", ts_raw, dist, lat, lon, spd, hr, cad, ele))

    if not session_info.get("total_distance") and lap_dist > 0:
        session_info["total_distance"] = lap_dist
    if not session_info.get("total_timer_time") and lap_time > 0:
        session_info["total_timer_time"] = lap_time
    if session_override:
        session_info.update(session_override)

    return _finalize_fit_records(records, session_info)


def _make_safe_fit_processor():
    class _SafeFitProcessor(fitdecode.StandardUnitsDataProcessor):
        def _process_field(self, frame, field):
            val = getattr(field, "value", None)
            if isinstance(val, (tuple, list)):
                if len(val) == 1:
                    field.value = val[0]
                else:
                    return
            try:
                super()._process_field(frame, field)
            except Exception:
                pass
    return _SafeFitProcessor()


def _parse_fit_with_fitdecode(raw_bytes, session_override=None):
    records = []
    session_info = {}
    lap_dist = 0.0
    lap_time = 0.0

    if len(raw_bytes) >= 14 and raw_bytes[8:12] == b".FIT":
        h_sz = raw_bytes[0]
        d_sz = struct.unpack("<I", raw_bytes[4:8])[0]
        if d_sz == 0 and len(raw_bytes) > h_sz + 2:
            raw_bytes = raw_bytes[:4] + struct.pack("<I", len(raw_bytes) - h_sz - 2) + raw_bytes[8:]

    reader_kwargs = {"processor": _make_safe_fit_processor()}
    if hasattr(fitdecode, "CrcCheck"):
        reader_kwargs["check_crc"] = fitdecode.CrcCheck.DISABLED

    with fitdecode.FitReader(io.BytesIO(raw_bytes), **reader_kwargs) as fit:
        for frame in fit:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue

            if frame.name == "event":
                e_fields = {f.name: f.value for f in frame.fields}
                ev = e_fields.get("event")
                if ev in ("timer", 0):
                    etype = e_fields.get("event_type")
                    if etype in ("stop", "stop_all", 1, 4):
                        records.append(("event", "stop"))
                    elif etype in ("start", 0):
                        records.append(("event", "start"))
                continue

            if frame.name == "lap":
                l_fields = {f.name: f.value for f in frame.fields}
                if to_float(l_fields.get("total_distance")):
                    lap_dist += to_float(l_fields.get("total_distance"))
                if to_float(l_fields.get("total_timer_time")):
                    lap_time += to_float(l_fields.get("total_timer_time"))
                continue

            if frame.name == "session":
                s_fields = {f.name: f.value for f in frame.fields}
                if to_float(s_fields.get("total_distance")):
                    session_info["total_distance"] = to_float(s_fields.get("total_distance"))
                if to_float(s_fields.get("total_timer_time")):
                    session_info["total_timer_time"] = to_float(s_fields.get("total_timer_time"))
                if to_float(s_fields.get("total_ascent")) is not None:
                    session_info["total_ascent"] = to_float(s_fields.get("total_ascent"))
                continue

            if frame.name != "record":
                continue

            fields = {f.name: f.value for f in frame.fields}
            ts = fields.get("timestamp")
            if isinstance(ts, datetime):
                ts_sec = ts.timestamp()
            else:
                ts_sec = to_float(ts)

            dist = to_float(fields.get("distance"))
            hr = to_float(fields.get("heart_rate"))
            cad = to_float(fields.get("cadence"))
            ele = to_float(fields.get("enhanced_altitude"))
            if ele is None:
                ele = to_float(fields.get("altitude"))
            spd = to_float(fields.get("enhanced_speed"))
            if spd is None:
                spd = to_float(fields.get("speed"))

            lat = _norm_coord(to_float(fields.get("position_lat")), 90.0)
            lon = _norm_coord(to_float(fields.get("position_long")), 180.0)

            records.append(("record", ts_sec, dist, lat, lon, spd, hr, cad, ele))

    if not session_info.get("total_distance") and lap_dist > 0:
        session_info["total_distance"] = lap_dist
    if not session_info.get("total_timer_time") and lap_time > 0:
        session_info["total_timer_time"] = lap_time
    if session_override:
        session_info.update(session_override)

    return _finalize_fit_records(records, session_info)


def _parse_fit_bytes(raw_bytes, session_override=None):
    if raw_bytes[:2] == b"\x1f\x8b":
        raw_bytes = _gzip.decompress(raw_bytes)
    elif raw_bytes[:4] == b"PK\x03\x04":
        with _zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            for name in zf.namelist():
                if name.lower().endswith((".fit", ".gpx")):
                    raw_bytes = zf.read(name)
                    break

    head_txt = raw_bytes.lstrip()[:30]
    if head_txt.startswith((b"<?xml", b"<gpx")):
        return _parse_gpx_bytes(raw_bytes, session_override=session_override)

    if fitdecode is not None:
        try:
            return _parse_fit_with_fitdecode(raw_bytes, session_override=session_override)
        except Exception:
            pass
    return _parse_fit_raw_binary(raw_bytes, session_override=session_override)


def _parse_iso_gpx_time(ts_str):
    if not ts_str:
        return None
    s = ts_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _extract_gpx_segments_xml(raw_bytes):
    """Fallback đọc trực tiếp XML GPX chuẩn 7-tuple (lat, lon, ele, time, hr, cad, acc)."""
    root = ET.fromstring(raw_bytes.decode("utf-8", errors="ignore"))
    segments = []
    for trkseg in root.iter():
        if not trkseg.tag.lower().endswith("trkseg"):
            continue
        seg = []
        for trkpt in trkseg:
            if not trkpt.tag.lower().endswith("trkpt"):
                continue
            lat = to_float(trkpt.attrib.get("lat"))
            lon = to_float(trkpt.attrib.get("lon"))
            if lat is None or lon is None:
                continue
            ele, pt_time, hr, cad, acc = None, None, None, None, None
            for child in trkpt.iter():
                tag = child.tag.lower()
                txt = (child.text or "").strip()
                if not txt:
                    continue
                if tag.endswith("ele"):
                    ele = to_float(txt)
                elif tag.endswith("time"):
                    pt_time = _parse_iso_gpx_time(txt)
                elif tag.endswith(("hr", "heartrate")):
                    hr = to_float(txt)
                elif tag.endswith(("cad", "cadence")):
                    cad = to_float(txt)
                elif tag.endswith("hdop"):
                    v = to_float(txt)
                    if v is not None:
                        acc = v * 5.0
                elif tag.endswith(("accuracy", "hacc")):
                    acc = to_float(txt)
            seg.append((lat, lon, ele, pt_time, hr, cad, acc))
        if len(seg) >= 2:
            segments.append(seg)
    return segments


def _filter_gpx_segment(seg):
    """Chỉ loại bỏ điểm GPS nhiễu nặng (>30m), giữ nguyên tọa độ gốc để không cắt góc cua."""
    filtered = [pt for pt in seg if pt[6] is None or pt[6] <= 30.0]
    return filtered if len(filtered) >= 2 else seg


def _parse_gpx_bytes(raw_bytes, session_override=None):
    """Phân tích GPX mô phỏng thuật toán Moving Time & Splits của Strava."""
    segments = []
    if gpxpy is not None:
        try:
            gpx = gpxpy.parse(raw_bytes.decode("utf-8", errors="ignore"))
            for track in gpx.tracks:
                for segment in track.segments:
                    if len(segment.points) < 2:
                        continue
                    seg = []
                    for pt in segment.points:
                        hr, cad, acc = None, None, None
                        if getattr(pt, "horizontal_dilution", None):
                            acc = float(pt.horizontal_dilution) * 5.0
                        for ext in pt.extensions:
                            for child in ext.iter():
                                tag = child.tag.lower()
                                if tag.endswith(("hr", "heartrate")) and child.text:
                                    hr = to_float(child.text)
                                elif tag.endswith(("cad", "cadence")) and child.text:
                                    cad = to_float(child.text)
                                elif tag.endswith(("accuracy", "hacc")) and child.text:
                                    acc = to_float(child.text)
                        seg.append((pt.latitude, pt.longitude, pt.elevation, pt.time, hr, cad, acc))
                    segments.append(seg)
        except Exception:
            segments = _extract_gpx_segments_xml(raw_bytes)
    else:
        segments = _extract_gpx_segments_xml(raw_bytes)

    points = []
    has_any_time = False

    for raw_seg in segments:
        seg = _filter_gpx_segment(raw_seg)
        raw_steps = []
        prev_lat, prev_lon, _, prev_time, _, _, _ = seg[0]
        for lat, lon, ele, pt_time, hr, cad, _ in seg[1:]:
            d_m = _haversine_m(prev_lat, prev_lon, lat, lon)
            dt_raw = _safe_dt_seconds(prev_time, pt_time)
            if dt_raw is not None:
                has_any_time = True
                dt_s = max(0.0, dt_raw)
            else:
                dt_s = 1.0
            prev_lat, prev_lon, prev_time = lat, lon, pt_time

            if dt_s <= 0:
                continue
            if dt_s > 10.0:
                raw_steps.append(None)
                continue
            if (d_m / dt_s) > 11.0 or d_m > 100.0:
                continue

            raw_steps.append((d_m, dt_s, hr, cad, ele))

        n = len(raw_steps)
        for i, step in enumerate(raw_steps):
            if step is None:
                continue
            if not has_any_time:
                points.append(step)
                continue
            w_dist, w_time = 0.0, 0.0
            for j in range(max(0, i - 2), min(n, i + 3)):
                if raw_steps[j] is None:
                    continue
                w_dist += raw_steps[j][0]
                w_time += raw_steps[j][1]
            rolling_speed = (w_dist / w_time) if w_time > 0 else 0.0
            if rolling_speed >= 0.85:
                points.append(step)

    res = _aggregate_splits(points, session_override=session_override)
    if not has_any_time and not (session_override and session_override.get("total_timer_time")):
        res["duration_sec"] = 0
        res["avg_pace"] = ""
        for sp in res["splits"]:
            sp["pace_sec"] = 0
            sp["pace_str"] = ""
    return res


def parse_activity_file(filename, raw_bytes, strava_km=None, strava_time_sec=None):
    """Phân tích tệp .fit hoặc .gpx tải lên từ Strava / Garmin."""
    fname = (filename or "").lower()
    session_override = {}
    if strava_km and strava_km > 0:
        session_override["total_distance"] = float(strava_km) * 1000.0
    if strava_time_sec and strava_time_sec > 0:
        session_override["total_timer_time"] = float(strava_time_sec)
    override_arg = session_override or None

    if fname.endswith(".fit"):
        res = _parse_fit_bytes(raw_bytes, session_override=override_arg)
    elif fname.endswith(".gpx"):
        res = _parse_gpx_bytes(raw_bytes, session_override=override_arg)
    else:
        raise ValueError("Chỉ hỗ trợ định dạng .fit hoặc .gpx.")
    res["source_file"] = filename
    return res


# ==========================================
# THEO DÕI GIÀY CHẠY (GEAR TRACKER)
# ==========================================
def compute_shoe_stats(project):
    shoes = project.get("shoes", [])
    plans = project.get("plans", [])
    default_shoe_id = next((s["id"] for s in shoes if s.get("is_default")), None)

    km_by_shoe = {s["id"]: float(s.get("initial_km") or 0.0) for s in shoes}
    runs_by_shoe = {s["id"]: 0 for s in shoes}

    for p in plans:
        for it in p.get("schedule", []):
            if is_run(it) and it.get("completed"):
                k = km_done(it)
                if k <= 0:
                    continue
                sid = it.get("shoe_id") or default_shoe_id
                if sid and sid in km_by_shoe:
                    km_by_shoe[sid] += k
                    runs_by_shoe[sid] += 1

    out = []
    for s in shoes:
        sid = s["id"]
        total_km = round(km_by_shoe.get(sid, 0.0), 1)
        max_km = max(100.0, float(s.get("max_km") or 700.0))
        pct = min(100, int(round(total_km / max_km * 100)))
        if total_km >= max_km:
            status = "🔴 Hết tuổi thọ đệm"
        elif pct >= 80:
            status = "🟠 Sắp thay (>80%)"
        else:
            status = "🟢 Đệm tốt"
        out.append({
            "id": sid,
            "name": s.get("name", "Giày chạy"),
            "brand": s.get("brand", ""),
            "total_km": total_km,
            "max_km": max_km,
            "pct": pct,
            "runs": runs_by_shoe.get(sid, 0),
            "is_default": bool(s.get("is_default")),
            "status": status,
        })
    return out


# ==========================================
# TẢI TẬP, GIAI ĐOẠN, VÙNG PACE
# ==========================================
def days_to_race(profile, today=None):
    today = today or today_vn()
    rd = parse_iso_date(profile.get("race_date"))
    return None if rd is None else (rd - today).days


def training_phase(days_left):
    if days_left is None:
        return "Maintain"
    if days_left <= 0:
        return "Race"
    if days_left <= 14:
        return "Taper"
    if days_left <= 21:
        return "Peak"
    if days_left <= 56:
        return "Build"
    return "Base"


def resolve_effective_max_dist(profile, plans):
    base_max = float(profile.get("max_distance") or 8.0)
    if not plans:
        return base_max

    best_safe_km = 0.0
    for p in plans:
        for it in p.get("schedule", []):
            if is_run(it) and it.get("completed"):
                k = km_done(it)
                pain = to_float(it.get("pain"))
                rpe = to_float(it.get("rpe"))
                if (pain is None or pain < 4) and (rpe is None or rpe < 8.5):
                    best_safe_km = max(best_safe_km, k)

    if best_safe_km <= 0:
        return base_max

    progressed = max(base_max, round_half_km(best_safe_km * 1.2), round_half_km(best_safe_km + 1.5))
    goal_dist = GOAL_DISTANCE_KM.get(profile.get("goal"))
    if goal_dist:
        progressed = min(progressed, round(goal_dist * 0.9, 1))
    return progressed


def resolve_effective_pace(profile, plans):
    base_sec = pace_to_sec(profile.get("current_pace"))
    if not base_sec or not plans:
        return base_sec

    recent_paces = []
    for p in plans[-2:]:
        s = plan_stats(p)
        ok_rpe = s["rpe_avg"] is None or s["rpe_avg"] <= 7.5
        ok_pain = s["max_pain"] is None or s["max_pain"] < 4
        if s["avg_pace"] and s["rate"] >= 75 and ok_rpe and ok_pain:
            recent_paces.append(s["avg_pace"])

    if not recent_paces:
        return base_sec

    actual_sec = sum(recent_paces) / len(recent_paces)
    return round(actual_sec * 0.85 + base_sec * 0.15)


def compute_zones(profile, phase, plans=None):
    cur = resolve_effective_pace(profile, plans)
    if not cur:
        return {}
    tgt = pace_to_sec(resolve_target_pace(profile)) or cur
    ref = cur + (tgt - cur) * PHASE_BLEND.get(phase, 0.0)
    return {t: (ref + lo, ref + hi) for t, (lo, hi) in ZONE_OFFSETS.items()}


def zones_text(zones):
    return "\n".join(
        f"  + {t}: {sec_to_pace(lo)} – {sec_to_pace(hi)} /km" for t, (lo, hi) in zones.items()
    )


def is_run(item):
    return item.get("workout_type") != "Rest"


def km_planned(item):
    return to_float(item.get("distance_km"), 0.0) or 0.0


def km_done(item):
    if not item.get("completed"):
        return 0.0
    actual = to_float(item.get("actual_km"))
    return actual if (actual is not None and actual >= 0) else km_planned(item)


def plan_stats(plan):
    runs = [it for it in plan.get("schedule", []) if is_run(it)]
    done_items = [it for it in runs if it.get("completed")]
    weighted, weights = 0.0, 0.0
    for it in done_items:
        ps, k = pace_to_sec(it.get("actual_pace")), km_done(it)
        if ps and k > 0:
            weighted += ps * k
            weights += k
    rpes = [v for v in (to_float(it.get("rpe")) for it in runs) if v is not None]
    pains = [v for v in (to_float(it.get("pain")) for it in runs) if v is not None]
    return {
        "total": len(runs),
        "done": len(done_items),
        "planned_km": sum(km_planned(it) for it in runs),
        "done_km": sum(km_done(it) for it in runs),
        "rate": int(len(done_items) / len(runs) * 100) if runs else 100,
        "avg_pace": (weighted / weights) if weights else None,
        "rpe_avg": (sum(rpes) / len(rpes)) if rpes else None,
        "max_pain": max(pains) if pains else None,
    }


# ==========================================
# PHÂN TÍCH SINH LÝ (Cardiac Drift / Efficiency Factor) - Python thuần, 0 token
# ==========================================
def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _usable_km_splits(splits):
    out = []
    for sp in splits or []:
        pace, hr = to_float(sp.get("pace_sec")), to_float(sp.get("avg_hr"))
        if (to_float(sp.get("distance_km"), 0.0) or 0.0) >= 0.999 and pace and pace > 0 and hr:
            out.append(sp)
    return out


def _km_hr_bad_flags(kms):
    """Đánh dấu km có HR nghi nhiễu: mẫu nhảy vọt, cadence lock, hoặc avg HR lệch >20 bpm so với km kề."""
    flags = []
    for sp in kms:
        hr = float(sp["avg_hr"])
        cad = to_float(sp.get("avg_cadence"))
        bad = (to_float(sp.get("hr_bad_ratio"), 0.0) or 0.0) > HR_BAD_KM_RATIO
        bad = bad or bool(cad and hr >= CADENCE_LOCK_MIN_HR and abs(hr - cad) <= CADENCE_LOCK_TOL)
        flags.append(bad)
    for i in range(1, len(kms)):
        if abs(float(kms[i]["avg_hr"]) - float(kms[i - 1]["avg_hr"])) > HR_KM_JUMP_BPM:
            flags[i] = flags[i - 1] = True
    return flags


def analyze_session_physio(item):
    """Cardiac Drift + Efficiency Factor cho 1 buổi Easy/Long có telemetry.
    status: ok | invalid (HR nhiễu) | skip (không đủ điều kiện). confirmed: True/False/None (đối chiếu RPE/đau)."""
    wtype = item.get("workout_type")
    res = {"status": "skip", "reason": "", "type": wtype, "ef": None, "drift_pct": None,
           "level": None, "confirmed": None}
    tele = item.get("telemetry") or {}
    if wtype not in ("Long Run", "Easy Run"):
        res["reason"] = "không phải bài đều (Easy/Long)"
        return res
    dist = to_float(tele.get("distance_km"), 0.0) or 0.0
    if dist > 0 and (to_float(tele.get("total_ele_gain"), 0.0) or 0.0) / dist > DRIFT_MAX_ELE_PER_KM:
        res["reason"] = "địa hình dốc, drift không còn phản ánh thể lực"
        return res
    kms = _usable_km_splits(tele.get("splits"))[1:]  # bỏ km đầu (khởi động)
    if len(kms) < DRIFT_MIN_KM:
        res["reason"] = f"quá ngắn (<{DRIFT_MIN_KM} km sau khởi động)"
        return res

    flags = _km_hr_bad_flags(kms)
    valid = [i for i, bad in enumerate(flags) if not bad]
    mid = len(kms) // 2
    h1, h2 = [i for i in valid if i < mid], [i for i in valid if i >= mid]
    if len(valid) / len(kms) < DRIFT_MIN_VALID_SHARE or len(h1) < 2 or len(h2) < 2:
        res.update(status="invalid", reason="HR không đủ tin cậy (nghi nhiễu cổ tay / cadence lock)")
        return res
    paces = [float(kms[i]["pace_sec"]) for i in valid]
    if max(paces) / min(paces) > DRIFT_MAX_PACE_SPREAD:
        res["reason"] = "pace dao động lớn, không phải bài đều"
        return res

    def ef(i):  # tốc độ (m/phút) chia nhịp tim
        return (60000.0 / float(kms[i]["pace_sec"])) / float(kms[i]["avg_hr"])

    ef1, ef2 = _mean(ef(i) for i in h1), _mean(ef(i) for i in h2)
    drift = (ef1 - ef2) / ef1 * 100.0
    level = "high" if drift > DRIFT_LIMIT_PCT else ("watch" if drift > DRIFT_WATCH_PCT else "good")
    res.update(status="ok", ef=round(_mean(ef(i) for i in valid), 3), drift_pct=round(drift, 1), level=level)
    if level == "high":
        rpe, pain = to_float(item.get("rpe")), to_float(item.get("pain"))
        if rpe is not None or pain is not None:
            res["confirmed"] = bool((rpe is not None and rpe >= CONFIRM_RPE) or (pain is not None and pain >= CONFIRM_PAIN))
    return res


def physio_signals(plans):
    """Quét tuần gần nhất: reduce_reasons (đủ 2 lớp xác thực mới hạ tải), hold (chặn tăng tải), bullets."""
    out = {"reduce_reasons": [], "hold": False, "bullets": []}
    if not plans:
        return out
    prev_ef = {}
    for plan in plans[:-1]:
        for it in plan.get("schedule", []):
            if it.get("telemetry"):
                a = analyze_session_physio(it)
                if a["status"] == "ok":
                    prev_ef[a["type"]] = a["ef"]
    for it in plans[-1].get("schedule", []):
        if not it.get("telemetry"):
            continue
        a = analyze_session_physio(it)
        where = f"{it.get('day')} ({a['type']})"
        if a["status"] == "invalid":
            out["bullets"].append(f"HR buổi {where} nghi nhiễu cảm biến cổ tay: bỏ qua, KHÔNG dùng HR để chỉnh lịch.")
            continue
        if a["status"] != "ok":
            continue
        d = a["drift_pct"]
        trend = ""
        if prev_ef.get(a["type"]):
            trend = f", EF {a['ef']:.2f} ({(a['ef'] - prev_ef[a['type']]) / prev_ef[a['type']] * 100:+.1f}% so với lần trước cùng loại)"
        if a["level"] == "good":
            out["bullets"].append(f"Cardiac Drift {where} = {d:.1f}% (<{DRIFT_WATCH_PCT:g}%): nền hiếu khí ổn{trend}.")
        elif a["level"] == "watch":
            out["hold"] = True
            out["bullets"].append(f"Cardiac Drift {where} = {d:.1f}% (vùng theo dõi {DRIFT_WATCH_PCT:g}-{DRIFT_LIMIT_PCT:g}%): không tăng Long Run/cường độ tuần này{trend}.")
        elif a["confirmed"]:
            out["hold"] = True
            rpe, pain = it.get("rpe"), it.get("pain")
            out["reduce_reasons"].append(
                f"nền hiếu khí chưa đủ: Cardiac Drift {d:.1f}% (>{DRIFT_LIMIT_PCT:g}%) ở {where}, HR hợp lệ, "
                f"runner chấm RPE {rpe if rpe is not None else '-'}/10, đau {pain if pain is not None else '-'}/10 xác nhận")
        elif a["confirmed"] is None:
            out["hold"] = True
            out["bullets"].append(f"Cardiac Drift {where} = {d:.1f}% (>{DRIFT_LIMIT_PCT:g}%) nhưng runner chưa chấm RPE/đau: chưa hạ tải, giữ nguyên khối lượng.")
        else:
            out["hold"] = True
            out["bullets"].append(f"Cardiac Drift {where} = {d:.1f}% (>{DRIFT_LIMIT_PCT:g}%) nhưng RPE/đau thấp (mâu thuẫn, có thể do nóng/thiếu nước): không hạ tải, giữ nguyên.")
    if out["reduce_reasons"]:
        out["bullets"] = [f"Hạ tải tuần này: {out['reduce_reasons'][0]}."] + out["bullets"]
    return out


# ==========================================
# HỌC THÓI QUEN CHỈNH LỊCH (draft AI vs bản runner chốt) - Python thuần, 0 token
# ==========================================
def default_memory():
    return {"edit_log": [], "rules": []}


def _day_map(schedule):
    out = {}
    for it in schedule or []:
        day, wtype = normalize_day(it.get("day")), normalize_type(it.get("workout_type"))
        if day in ALL_DAYS and wtype and wtype != "Rest":
            out[day] = (wtype, km_planned(it))
    return out


def diff_plan_edits(ai_schedule, final_schedule):
    """So bản AI đề xuất với bản runner chốt -> danh sách 'kiểu chỉnh sửa' trừu tượng (không gắn tuần cụ thể)."""
    ai, fin = _day_map(ai_schedule), _day_map(final_schedule)
    kinds, removed, added = [], {}, {}
    for day in ALL_DAYS:
        a, f = ai.get(day), fin.get(day)
        if a and f:
            if a[0] != f[0]:
                kinds.append(f"swap|{a[0]}|{f[0]}")
            elif abs(f[1] - a[1]) >= HABIT_KM_DELTA:
                kinds.append(f"km_{'up' if f[1] > a[1] else 'down'}|{day}")
        elif a:
            removed.setdefault(a[0], []).append(day)
        elif f:
            added.setdefault(f[0], []).append(day)
    for wtype, days in removed.items():
        for src in days:
            if added.get(wtype):
                kinds.append(f"move|{wtype}|{src}|{added[wtype].pop(0)}")
            else:
                kinds.append(f"drop|{wtype}|{src}")
    for wtype, days in added.items():
        for dst in days:
            kinds.append(f"add|{wtype}|{dst}")
    return sorted(set(kinds))


def _opposite_habit_key(key):
    p = key.split("|")
    if p[0] == "swap":
        return f"swap|{p[2]}|{p[1]}"
    if p[0] == "km_up":
        return f"km_down|{p[1]}"
    if p[0] == "km_down":
        return f"km_up|{p[1]}"
    if p[0] == "move":
        return f"move|{p[1]}|{p[3]}|{p[2]}"
    if p[0] == "drop":
        return f"add|{p[1]}|{p[2]}"
    if p[0] == "add":
        return f"drop|{p[1]}|{p[2]}"
    return ""


def habit_text(rule):
    p = rule["key"].split("|")
    n = rule.get("weeks", HABIT_MIN_WEEKS)
    k = p[0]
    if k == "swap":
        body = f"hay đổi {p[1]} thành {p[2]}: hạn chế xếp {p[1]}, ưu tiên {p[2]}"
    elif k == "km_down":
        body = f"hay giảm km ngày {p[1]}: xếp ngày {p[1]} ngắn/nhẹ hơn"
    elif k == "km_up":
        body = f"hay tăng km ngày {p[1]}: có thể xếp ngày {p[1]} dài hơn (trong trần km)"
    elif k == "move":
        body = f"hay dời {p[1]} từ {p[2]} sang {p[3]}: xếp {p[1]} vào {p[3]}"
    elif k == "drop":
        body = f"hay bỏ buổi {p[1]} ngày {p[2]}: không xếp {p[1]} vào {p[2]}"
    else:
        body = f"hay tự thêm buổi {p[1]} vào {p[2]}: cân nhắc xếp {p[1]} ngày {p[2]}"
    return f"Thói quen runner (lặp {n} tuần): {body}."


def learn_from_edits(memory, week_index, ai_schedule, final_schedule):
    """Ghi nhật ký chỉnh sửa của tuần vừa chốt; chỉ nâng thành quy tắc khi cùng kiểu lặp >=2 tuần
    trong cửa sổ gần nhất. Giữ tối đa HABIT_MAX_RULES quy tắc gần nhất (cửa sổ trượt)."""
    mem = memory or {}
    log = [dict(e) for e in (mem.get("edit_log") or [])]
    rules = [dict(r) for r in (mem.get("rules") or [])]
    if not ai_schedule:
        return {"edit_log": log, "rules": rules}
    kinds = diff_plan_edits(ai_schedule, final_schedule)
    log = [e for e in log if e.get("week") != week_index]
    log.append({"week": week_index, "kinds": kinds})
    log = log[-HABIT_LOG_WEEKS:]
    for key in kinds:
        weeks = sum(1 for e in log if key in e.get("kinds", []))
        if weeks < HABIT_MIN_WEEKS:
            continue
        rules = [r for r in rules if r["key"] != _opposite_habit_key(key)]
        for r in rules:
            if r["key"] == key:
                r.update(weeks=weeks, last_week=week_index)
                break
        else:
            rules.append({"key": key, "weeks": weeks, "last_week": week_index})
    rules.sort(key=lambda r: (r.get("last_week", 0), r.get("weeks", 0)), reverse=True)
    return {"edit_log": log, "rules": rules[:HABIT_MAX_RULES]}


def build_insight_block(plans, memory=None, max_bullets=5):
    """Gộp kết luận sinh lý + thói quen thành tối đa 5 gạch đầu dòng (an toàn ưu tiên trước)."""
    bullets = physio_signals(plans)["bullets"][:2]
    for r in (memory or {}).get("rules", []):
        if len(bullets) >= max_bullets:
            break
        bullets.append(habit_text(r))
    return bullets


def load_signals(plans):
    out = {"reduce": False, "boost": False, "reasons": [], "last_feedback": ""}
    if not plans:
        return out
    phys = physio_signals(plans)
    s = plan_stats(plans[-1])
    if s["max_pain"] is not None and s["max_pain"] >= 4:
        out["reasons"].append(f"đau {s['max_pain']:.0f}/10 trong tuần trước")
    if s["rpe_avg"] is not None and s["rpe_avg"] >= 8.5:
        out["reasons"].append(f"RPE trung bình {s['rpe_avg']:.1f}/10 (quá nặng)")
    if s["total"] and s["rate"] < 50:
        out["reasons"].append(f"chỉ hoàn thành {s['rate']}% buổi tuần trước")
    out["reasons"].extend(phys["reduce_reasons"])
    out["reduce"] = bool(out["reasons"])

    if not out["reduce"] and not phys["hold"] and s["rate"] >= 90 and (s["rpe_avg"] is not None and s["rpe_avg"] <= 5.5):
        out["boost"] = True
    out["last_feedback"] = to_text(plans[-1].get("user_feedback"))
    return out


def next_week_index(plans):
    return max([int(p.get("week_index") or 0) for p in plans] + [0]) + 1


def compute_weekly_cap(plans, week_index, days_left):
    if not plans:
        return None, "", 0.0
    last = plan_stats(plans[-1])
    base = last["done_km"] if last["done_km"] > 0 else last["planned_km"] * 0.5
    if base <= 0:
        return None, "", 0.0
    candidates = [(1 + WEEKLY_INCREASE, f"tăng tối đa {WEEKLY_INCREASE * 100:g}% so với km thực tế tuần trước")]
    if week_index % 4 == 0:
        candidates.append((0.75, "tuần giảm tải định kỳ (mỗi 4 tuần)"))
    if days_left is not None and 0 < days_left <= 7:
        candidates.append((0.5, "tuần cuối trước race"))
    elif days_left is not None and 0 < days_left <= 14:
        candidates.append((0.7, "giai đoạn taper trước race"))
    sig = load_signals(plans)
    if sig["reduce"]:
        candidates.append((0.85, "giảm tải vì " + "; ".join(sig["reasons"])))
    factor, reason = min(candidates, key=lambda c: c[0])
    return round_half_km(base * factor), reason, round(base, 1)


# ==========================================
# KIỂM TRA & SỬA KẾ HOẠCH DO AI TẠO
# ==========================================
def validate_plan(schedule, profile, *, week_start=None, zones=None, cap_km=None, lenient=False):
    warnings, cleaned, seen = [], [], set()
    allowed_days = set(profile.get("days") or [])
    max_dist = to_float(profile.get("max_distance"))
    zones = zones or {}
    has_injury = to_text(profile.get("injuries")) not in ("", "Không có")

    for raw in schedule or []:
        if not isinstance(raw, dict):
            continue
        day = normalize_day(raw.get("day"))
        if day not in ALL_DAYS:
            warnings.append(f"Bỏ buổi có ngày không hợp lệ: {to_text(raw.get('day'))!r}.")
            continue
        if not lenient:
            if allowed_days and day not in allowed_days:
                warnings.append(f"Bỏ buổi {day}: ngoài lịch rảnh của bạn.")
                continue
            if day in seen:
                warnings.append(f"Bỏ buổi thứ 2 trong cùng {day} (mỗi ngày tối đa 1 buổi).")
                continue
        seen.add(day)

        wtype = normalize_type(raw.get("workout_type"))
        if wtype is None:
            warnings.append(f"{day}: loại buổi '{to_text(raw.get('workout_type'))}' không hợp lệ, đổi thành Easy Run.")
            wtype = "Easy Run"

        if not lenient and has_injury and wtype == "Interval":
            warnings.append(f"{day}: đổi Interval thành Easy Run để bảo vệ chấn thương.")
            wtype = "Easy Run"

        notes = to_text(raw.get("notes"))
        dist = round_half_km(max(to_float(raw.get("distance_km"), 0.0) or 0.0, 0.0))
        if wtype == "Rest":
            dist = 0.0
        elif not lenient and max_dist and dist > max_dist:
            dist = max_dist
            notes = (notes + " (đã giới hạn theo Max KM)").strip()
            warnings.append(f"{day}: km vượt Max KM/buổi, đã giảm còn {max_dist:g} km.")

        pace = to_text(raw.get("pace_target"))
        p = pace_to_sec(pace)
        zone = zones.get(wtype)
        if wtype == "Rest":
            pace = ""
        elif p is None:
            pace = sec_to_pace((zone[0] + zone[1]) / 2) if (zone and not lenient) else ""
            if pace:
                warnings.append(f"{day}: thiếu pace hợp lệ, dùng giữa vùng {wtype} ({pace}).")
        elif zone and not lenient and not (zone[0] - 15 <= p <= zone[1] + 15):
            fixed = min(max(p, zone[0]), zone[1])
            warnings.append(f"{day}: pace {sec_to_pace(p)} lệch vùng {wtype}, chỉnh thành {sec_to_pace(fixed)}.")
            pace = sec_to_pace(fixed)
            notes = (notes + " (pace đã chỉnh theo vùng)").strip()
        else:
            pace = sec_to_pace(p)

        item = {
            "day": day, "workout_type": wtype, "distance_km": round(dist, 1),
            "pace_target": pace, "notes": notes, "completed": False,
            "actual_km": None, "actual_pace": "", "rpe": None, "pain": None, "date": "",
            "shoe_id": None, "telemetry": None,
        }
        d = session_date(week_start, day)
        if d:
            item["date"] = d.isoformat()
        cleaned.append(item)

    cleaned.sort(key=lambda it: ALL_DAYS.index(it["day"]))

    if not lenient:
        hard_count = 0
        prev_hard_idx = None
        easy_zone = zones.get("Easy Run")
        for it in cleaned:
            if it["workout_type"] in HARD_TYPES:
                day_idx = ALL_DAYS.index(it["day"])
                is_consecutive = prev_hard_idx is not None and (day_idx - prev_hard_idx == 1)
                if hard_count >= 2 or is_consecutive:
                    reason = "sát ngày buổi nặng trước" if is_consecutive else "vượt quá 2 buổi tốc độ/tuần"
                    warnings.append(f"{it['day']}: hạ {it['workout_type']} xuống Easy Run ({reason}).")
                    it["workout_type"] = "Easy Run"
                    if easy_zone:
                        it["pace_target"] = sec_to_pace((easy_zone[0] + easy_zone[1]) / 2)
                    it["notes"] = (it["notes"] + " (tự điều chỉnh về Easy để phục hồi)").strip()
                else:
                    hard_count += 1
                    prev_hard_idx = day_idx

    if not lenient and cap_km:
        total = sum(it["distance_km"] for it in cleaned if is_run(it))
        if total > cap_km > 0:
            factor = cap_km / total
            for it in cleaned:
                if is_run(it) and it["distance_km"] > 0:
                    it["distance_km"] = max(0.5, round_half_km(it["distance_km"] * factor))
                    it["notes"] = (it["notes"] + " (giảm theo trần tải tuần)").strip()
            warnings.append(f"Tổng km AI đề xuất {total:.1f} vượt trần {cap_km:.1f} km, đã giảm đều các buổi.")
    return cleaned, warnings


def apply_log_edits(plan, edited_rows, shoe_name_to_id=None):
    schedule = plan.get("schedule", [])
    shoe_name_to_id = shoe_name_to_id or {}
    for k, changes in (edited_rows or {}).items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            continue
        if not (0 <= idx < len(schedule)) or not isinstance(changes, dict):
            continue
        item = schedule[idx]
        if "shoe_name" in changes:
            sname = to_text(changes["shoe_name"])
            item["shoe_id"] = shoe_name_to_id.get(sname)
        if "actual_km" in changes:
            v = to_float(changes["actual_km"])
            item["actual_km"] = round(v, 1) if (v is not None and v >= 0) else None
            if v and v > 0 and "completed" not in changes:
                item["completed"] = True
        if "actual_pace" in changes:
            ps = pace_to_sec(changes["actual_pace"])
            item["actual_pace"] = sec_to_pace(ps) if ps else ""
        if "rpe" in changes:
            v = to_float(changes["rpe"])
            item["rpe"] = int(min(max(v, 1), 10)) if v is not None else None
        if "pain" in changes:
            v = to_float(changes["pain"])
            item["pain"] = int(min(max(v, 0), 10)) if v is not None else None
        if "completed" in changes:
            done = bool(changes["completed"])
            item["completed"] = done
            if done:
                if to_float(item.get("actual_km")) is None and km_planned(item) > 0:
                    item["actual_km"] = km_planned(item)
                if not to_text(item.get("actual_pace")) and to_text(item.get("pace_target")):
                    item["actual_pace"] = item["pace_target"]


# ==========================================
# THỐNG KÊ CHO DASHBOARD
# ==========================================
def week_label(plan, i):
    idx = int(plan.get("week_index") or (i + 1))
    ws = parse_iso_date(plan.get("week_start"))
    return f"W{idx:02d}" + (f" {ws:%d/%m}" if ws else "")


def weekly_table(plans):
    rows = []
    for i, p in enumerate(plans):
        s = plan_stats(p)
        rows.append({
            "label": week_label(p, i),
            "planned_km": round(s["planned_km"], 1),
            "done_km": round(s["done_km"], 1),
            "remaining_km": round(max(s["planned_km"] - s["done_km"], 0.0), 1),
            "rate": s["rate"],
            "avg_pace_min": round(s["avg_pace"] / 60, 2) if s["avg_pace"] else None,
        })
    return rows


def type_distribution(plans):
    dist = {}
    for p in plans:
        for it in p.get("schedule", []):
            if is_run(it) and it.get("completed"):
                k = km_done(it)
                if k > 0:
                    dist[it.get("workout_type")] = round(dist.get(it.get("workout_type"), 0.0) + k, 1)
    return dist


def low_intensity_share(dist):
    total = sum(dist.values())
    if total <= 0:
        return None
    return int(sum(v for t, v in dist.items() if t in LOW_INTENSITY_TYPES) / total * 100)


def completion_streak(plans, threshold=80):
    n = 0
    for p in reversed(plans):
        if plan_stats(p)["rate"] >= threshold:
            n += 1
        else:
            break
    return n


def build_history_text(plans, n=3):
    if not plans:
        return "Chưa có dữ liệu lịch sử. Đây là tuần đầu tiên của dự án."
    lines = ["LỊCH SỬ CÁC TUẦN GẦN NHẤT (số liệu thực tế runner đã ghi):"]
    for p in plans[-n:]:
        s = plan_stats(p)
        line = f"- {p.get('title', '')}: hoàn thành {s['done']}/{s['total']} buổi, {s['done_km']:.1f}/{s['planned_km']:.1f} km"
        if s["avg_pace"]:
            line += f", pace thực TB {sec_to_pace(s['avg_pace'])}"
        if s["rpe_avg"] is not None:
            line += f", RPE TB {s['rpe_avg']:.1f}/10"
        if s["max_pain"] is not None:
            line += f", đau tối đa {s['max_pain']:.0f}/10"
        fb = to_text(p.get("user_feedback"))
        if fb:
            line += f" | Phản hồi của runner: {fb[:300]}"
        lines.append(line)
    return "\n".join(lines)


# ==========================================
# LƯU TRỮ (SQLite WAL) + MIGRATE + SAO LƯU
# ==========================================
def make_default_projects():
    return {
        new_id(): {
            "name": "Dự án Half Marathon 21K",
            "profile": {
                "goal": "Half-Marathon (21K)", "current_pace": "07:30", "target_pace": "06:30", "target_time": "",
                "max_distance": 12.0, "injuries": "Không có",
                "notes": "Phân bổ 80% Easy/Long Run và 20% tốc độ.",
                "days": ["Thứ 2", "Thứ 3", "Thứ 5", "Thứ 7"], "race_date": "",
            },
            "shoes": [
                {
                    "id": new_id(), "name": "Giày Chạy Chính (Daily Trainer)",
                    "brand": "Stability / Cushion", "initial_km": 0.0, "max_km": 750.0, "is_default": True,
                }
            ],
            "plans": [], "draft": None, "memory": default_memory(),
        }
    }


def _parse_created(s):
    try:
        return datetime.strptime(str(s), "%d/%m/%Y %H:%M").date()
    except (TypeError, ValueError):
        return None


def migrate_projects(projects):
    for pdata in projects.values():
        pdata.setdefault("name", "Dự án")
        pdata.setdefault("profile", {}).setdefault("target_time", "")
        pdata.setdefault("shoes", [])
        pdata.setdefault("plans", [])
        pdata.setdefault("draft", None)
        pdata.setdefault("memory", default_memory())
        for i, plan in enumerate(pdata["plans"]):
            plan.setdefault("id", new_id())
            plan.setdefault("title", f"Tuần {i + 1}")
            plan.setdefault("created_at", "")
            plan.setdefault("week_summary", "")
            plan.setdefault("user_feedback", "")
            plan.setdefault("schedule", [])
            plan.setdefault("week_index", i + 1)
            if not plan.get("week_start"):
                created = _parse_created(plan.get("created_at"))
                plan["week_start"] = monday_of(created).isoformat() if created else ""
            ws = parse_iso_date(plan["week_start"])
            for item in plan["schedule"]:
                item.setdefault("completed", False)
                item.setdefault("actual_km", None)
                item.setdefault("actual_pace", "")
                item.setdefault("rpe", None)
                item.setdefault("pain", None)
                item.setdefault("shoe_id", None)
                item.setdefault("telemetry", None)
                if not item.get("date"):
                    d = session_date(ws, normalize_day(item.get("day")))
                    item["date"] = d.isoformat() if d else ""
    return projects


def import_projects(existing, data):
    if not isinstance(data, dict):
        raise ValueError("File không đúng định dạng sao lưu.")
    added = {}
    for pid, pdata in data.items():
        if not isinstance(pdata, dict) or ("plans" not in pdata and "profile" not in pdata):
            continue
        new_pid = pid if (pid not in existing and pid not in added) else new_id()
        added[new_pid] = pdata
    if not added:
        raise ValueError("Không tìm thấy dự án nào trong file.")
    return migrate_projects(added)


class Storage:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "running.db")
        self.legacy_path = os.path.join(data_dir, "running_data.json")
        self.recovery_warning = None
        self.sb = self._init_supabase()

        try:
            self._init_db()
            self._read_rows()
        except sqlite3.DatabaseError:
            self._quarantine_db()

    def _init_supabase(self):
        if create_client is None:
            return None
        url, key = None, None
        try:
            if st is not None and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
                url = st.secrets["SUPABASE_URL"]
                key = st.secrets["SUPABASE_KEY"]
        except Exception:
            pass
        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_KEY")
        if url and key:
            try:
                return create_client(url.strip(), key.strip())
            except Exception as e:
                self.recovery_warning = f"Lỗi kết nối Supabase (đang dùng dữ liệu máy): {e}"
        return None

    def _quarantine_db(self):
        backup = f"{self.db_path}.corrupt-{now_vn():%Y%m%d-%H%M%S}"
        shutil.copy(self.db_path, backup)
        os.remove(self.db_path)
        self._init_db()
        self.recovery_warning = f"Database bị lỗi, đã sao lưu tại: {backup}"

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return closing(conn)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS projects ("
                "id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            conn.commit()

    def _read_rows(self):
        with self._connect() as conn:
            return conn.execute("SELECT id, data FROM projects ORDER BY rowid").fetchall()

    def save_project(self, pid, pdata):
        payload = json.dumps(pdata, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects (id, data, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                (pid, payload, now_vn().isoformat()),
            )
            conn.commit()

        if self.sb is not None:
            try:
                self.sb.table("app_storage").upsert({
                    "key": f"project_{pid}",
                    "value": pdata
                }).execute()
            except Exception as e:
                self.recovery_warning = f"Không thể đồng bộ lên Cloud: {e}"

    def save_all(self, projects):
        for pid, pdata in projects.items():
            self.save_project(pid, pdata)

    def delete_project(self, pid):
        with self._connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
            conn.commit()

        if self.sb is not None:
            try:
                self.sb.table("app_storage").delete().eq("key", f"project_{pid}").execute()
            except Exception:
                pass

    def load_all(self):
        warning = self.recovery_warning
        stamp = now_vn().strftime("%Y%m%d-%H%M%S")

        if self.sb is not None:
            try:
                res = self.sb.table("app_storage").select("key, value").like("key", "project_%").execute()
                if res.data:
                    cloud_projects = {}
                    for row in res.data:
                        pid = row["key"].removeprefix("project_")
                        if isinstance(row.get("value"), dict):
                            cloud_projects[pid] = row["value"]
                    if cloud_projects:
                        return migrate_projects(cloud_projects), warning
            except Exception as e:
                warning = (warning or "") + f" Lỗi đọc dữ liệu từ Cloud: {e}"

        rows = self._read_rows()
        projects = {}
        for pid, payload in rows:
            try:
                projects[pid] = json.loads(payload)
            except json.JSONDecodeError:
                warning = (warning or "") + f" Bỏ qua dự án {pid} vì dữ liệu hỏng."
        if projects:
            projects = migrate_projects(projects)
            if self.sb is not None:
                self.save_all(projects)
            return projects, warning

        if os.path.exists(self.legacy_path):
            try:
                with open(self.legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    projects = migrate_projects(data)
            except Exception:
                backup = f"{self.legacy_path}.corrupt-{stamp}"
                try:
                    shutil.copy(self.legacy_path, backup)
                    warning = f"File dữ liệu cũ bị lỗi, đã sao lưu tại: {backup}"
                except OSError:
                    pass

        if not projects:
            projects = make_default_projects()
        self.save_all(projects)
        return projects, warning


# ==========================================
# XUẤT FILE: .ics VÀ CSV
# ==========================================
def _ics_escape(s):
    return (str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _ics_fold(line):
    out, cur, size = [], "", 0
    for ch in line:
        b = len(ch.encode("utf-8"))
        if size + b > 73:
            out.append(cur)
            cur, size = " " + ch, 1 + b
        else:
            cur += ch
            size += b
    out.append(cur)
    return "\r\n".join(out)


def plan_to_ics(project_name, plan):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    events = []
    for i, it in enumerate(plan.get("schedule", [])):
        d = parse_iso_date(it.get("date"))
        if not d or not is_run(it):
            continue
        desc = []
        if it.get("pace_target"):
            desc.append(f"Pace mục tiêu: {it['pace_target']} /km")
        if it.get("notes"):
            desc.append(str(it["notes"]))
        summary = "{} {:.1f} km".format(it.get("workout_type"), km_planned(it))
        events += [
            "BEGIN:VEVENT",
            f"UID:{plan.get('id')}-{i}@running-coach",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
            f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
            "SUMMARY:" + _ics_escape(summary),
            "DESCRIPTION:" + _ics_escape("\n".join(desc)),
            "END:VEVENT",
        ]
    if not events:
        return ""
    head = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AI Running Coach//VN//",
            "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{_ics_escape(project_name)}"]
    return "\r\n".join(_ics_fold(l) for l in head + events + ["END:VCALENDAR"]) + "\r\n"


def project_to_csv(project):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Tuần", "Bắt đầu tuần", "Ngày", "Ngày tháng", "Loại", "Km kế hoạch", "Pace kế hoạch",
                "Hoàn thành", "Km thực", "Pace thực", "RPE", "Đau", "Ghi chú"])
    for i, p in enumerate(project.get("plans", [])):
        for it in p.get("schedule", []):
            w.writerow([
                p.get("title", ""), p.get("week_start", ""), it.get("day", ""), it.get("date", ""),
                it.get("workout_type", ""), km_planned(it), it.get("pace_target", ""),
                "x" if it.get("completed") else "",
                "" if to_float(it.get("actual_km")) is None else it.get("actual_km"),
                it.get("actual_pace", ""),
                "" if it.get("rpe") is None else it.get("rpe"),
                "" if it.get("pain") is None else it.get("pain"),
                it.get("notes", ""),
            ])
    return buf.getvalue()


# ==========================================
# GỌI AI (google-genai) — TỰ ĐỘNG ƯU TIÊN HYDROGEN -> 3.8 FLASH
# ==========================================
_RESOLVED_MODEL_CACHE = {}


def extract_valid_json(raw_response):
    clean_text = (raw_response or "").strip()
    clean_text = re.sub(r'^```(json)?\s*', '', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\s*```$', '', clean_text)
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass
    start, end = clean_text.find("{"), clean_text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(clean_text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise AIOutputError(f"Dữ liệu JSON từ AI bị lỗi hoặc bị cắt cụt. Trích đoạn cuối: {clean_text[-80:]}")


def classify_error(exc):
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = f"{type(exc).__name__} {exc}".lower()
    if code == 429 or any(k in text for k in ("resource_exhausted", "quota", "rate limit", "429")):
        return "quota"
    if code in (401, 403) or any(k in text for k in ("api key", "api_key_invalid", "permission_denied", "unauthenticated")):
        return "auth"
    if code == 404 or "not_found" in text or "not found" in text:
        return "model"
    if code in (500, 502, 503, 504) or any(k in text for k in ("unavailable", "overloaded", "deadline", "timeout", "503")):
        return "transient"
    return "other"


def _default_factory(key):
    if genai is None:
        raise RuntimeError("Chưa cài thư viện google-genai (pip install google-genai).")
    return genai.Client(api_key=key)


def _resolve_model_alias(client, model_name):
    """Chỉ chạy khi tên model rút gọn trả về 404: tự dò đúng mã model đầy đủ trên API."""
    if model_name in _RESOLVED_MODEL_CACHE:
        return _RESOLVED_MODEL_CACHE[model_name]
    target = model_name.lower()
    keywords = ["hydrogen"] if "hydrogen" in target else (["3.8", "flash"] if "3.8" in target else [])
    if not keywords:
        _RESOLVED_MODEL_CACHE[model_name] = None
        return None
    try:
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None)
            if actions is not None and "generateContent" not in actions:
                continue
            cand = (getattr(m, "name", "") or "").removeprefix("models/")
            low = cand.lower()
            if cand != model_name and all(kw in low for kw in keywords):
                _RESOLVED_MODEL_CACHE[model_name] = cand
                return cand
    except Exception:
        pass
    _RESOLVED_MODEL_CACHE[model_name] = None
    return None


def _call_model(client, model_name, prompt, schema=None):
    cfg = dict(
        temperature=0.2,
        max_output_tokens=8192,
        response_mime_type="application/json",
    )
    if schema is not None:
        cfg["response_schema"] = schema
    response = client.models.generate_content(
        model=model_name, contents=prompt, config=types.GenerateContentConfig(**cfg)
    )
    return extract_valid_json(response.text)


def _normalize_model_list(model_name):
    if model_name is None or model_name == "auto":
        return list(MODEL_PRIORITY)
    if isinstance(model_name, (list, tuple)):
        return [m for m in model_name if str(m).strip()] or list(MODEL_PRIORITY)
    return [str(model_name).strip()]


def run_with_models_and_keys(api_keys, models, task_for_model, *, client_factory=None, sleep=time.sleep, max_transient=2):
    """Thử lần lượt từng model theo thứ tự ưu tiên (Hydrogen -> 3.8 Flash) qua toàn bộ API keys."""
    if not api_keys:
        return None, None, "Chưa có API key. Hãy thêm key vào HARDCODED_API_KEYS trong coach_core.py."
    factory = client_factory or _default_factory
    last_error = "Không có API key."

    for model_name in models:
        active_model = model_name
        alias_checked = False
        for key in api_keys:
            use_schema, retried_other, transient = True, False, 0
            try:
                client = factory(key)
            except Exception as e:
                last_error = f"Không tạo được client: {e}"
                continue

            while True:
                try:
                    result = task_for_model(client, active_model, use_schema)
                    return result, active_model, ""
                except Exception as e:
                    kind = classify_error(e)
                    last_error = f"[{active_model}] {type(e).__name__}: {str(e)[:300]}"
                    if kind == "model" and not alias_checked:
                        alias_checked = True
                        resolved = _resolve_model_alias(client, active_model)
                        if resolved:
                            active_model = resolved
                            continue
                    if kind in ("quota", "auth", "model"):
                        break
                    if kind == "transient" and transient < max_transient:
                        transient += 1
                        sleep(1.5 * transient)
                        continue
                    if kind == "other" and not retried_other:
                        retried_other, use_schema = True, False
                        continue
                    break

    return None, None, f"Lỗi tạo lịch (đã thử hết model & key): {last_error}"


def list_models(api_key, *, client_factory=None):
    client = (client_factory or _default_factory)(api_key)
    names = set()
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None)
        if actions is not None and "generateContent" not in actions:
            continue
        name = (getattr(m, "name", "") or "").removeprefix("models/")
        if name:
            names.add(name)
    return sorted(names, reverse=True)


def _race_info(profile, today):
    race_date = profile.get("race_date", "")
    left = days_to_race(profile, today)
    if not race_date:
        return "Không có ngày thi đấu cụ thể."
    if left is None:
        return "Lỗi định dạng ngày Race."
    if left <= 0:
        return f"{race_date} (Đã đến ngày Race!)."
    if left <= 14:
        return f"{race_date} (Còn {left} ngày. Giai đoạn TAPERING: giảm khối lượng, giữ cường độ nhẹ)."
    return f"{race_date} (Còn {left} ngày)."


def build_prompt(profile, history, week_index, week_start, today, phase, zones, cap, cap_reason, signals, has_history=False, insights=None):
    days_str = ", ".join(profile.get("days", []))
    max_dist = float(profile.get("max_distance") or 8.0)
    target_pace = resolve_target_pace(profile)
    target_line = f", Thời gian đích: {profile['target_time']}" if parse_duration(profile.get("target_time")) else ""
    rules = [
        f"- Chỉ xếp buổi tập vào các ngày: {days_str}. Mỗi ngày tối đa 1 buổi.",
        f"- distance_km của mỗi buổi KHÔNG vượt quá {max_dist:g}.",
        "- workout_type chỉ được là một trong: " + ", ".join(WORKOUT_TYPES) + ".",
        "- Tên ngày phải đúng một trong: " + ", ".join(ALL_DAYS) + ".",
        "- Tối đa 2 buổi cường độ cao (Interval/Tempo/Threshold) mỗi tuần và KHÔNG xếp 2 buổi nặng vào 2 ngày liên tiếp; khoảng 80% km ở Easy/Long.",
        "- pace_target dạng mm:ss và nằm trong vùng pace đã tính ở trên (Rest/Walk để trống hoặc tùy ý).",
        "- distance_km của mỗi buổi PHẢI là số chẵn hoặc số lẻ 0.5 km (ví dụ: 3.0, 3.5, 4.0, 5.5), không dùng số lẻ 0.1–0.4 km.",
    ]
    if cap:
        rules.append(f"- TỔNG km cả tuần KHÔNG vượt quá {cap:g} km ({cap_reason}).")
    else:
        rules.append("- Tuần đầu tiên: bắt đầu thận trọng, không dồn khối lượng.")
    if signals["reduce"]:
        rules.append("- BẮT BUỘC giảm tải tuần này: " + "; ".join(signals["reasons"]) + ".")
    if signals.get("boost"):
        rules.append("- Tuần trước runner hoàn thành tốt với RPE nhẹ: hãy nâng nhẹ độ thử thách (tăng nhẹ pace hoặc ưu tiên dồn km vào bài Long Run trong giới hạn Max KM) và nhắc tới sự tiến bộ này trong week_summary.")
    if signals.get("last_feedback"):
        rules.append(f"- BẮT BUỘC phản hồi trực tiếp và điều chỉnh giáo án theo cảm nhận tuần trước của runner: \"{signals['last_feedback']}\".")
    if has_history:
        rules.append("- Coi thông số hồ sơ ban đầu chỉ là điểm xuất phát; hãy thiết kế giáo án dựa trên phong độ thực tế và cảm nhận trong [LỊCH SỬ].")
    if to_text(profile.get("injuries")) not in ("", "Không có"):
        rules.append("- Runner có chấn thương: tránh Interval và giảm cường độ nếu liên quan.")
    rules.append("- Chỉ trả về JSON hợp lệ, không thêm giải thích hay markdown.")

    zone_block = ("[VÙNG PACE ĐÃ TÍNH (hãy dùng, đừng tự đoán)]\n" + zones_text(zones)) if zones else ""
    insight_block = ""
    if insights:
        insight_block = ("[PHÂN TÍCH TỰ ĐỘNG TỪ DỮ LIỆU THẬT (đã lọc nhiễu; tín hiệu sinh lý phải tuân theo, "
                         "thói quen thì ưu tiên nếu không vi phạm ràng buộc bên dưới)]\n"
                         + "\n".join(f"- {b}" for b in insights))
    return f"""
Bạn là Huấn luyện viên Chạy bộ AI chuyên nghiệp. Thiết kế giáo án 1 tuần dạng JSON.

[THÔNG TIN RUNNER]
- Hôm nay: {today.strftime('%d/%m/%Y')} ({ALL_DAYS[today.weekday()]})
- Tuần số: {week_index} (từ {week_start:%d/%m/%Y} đến {week_start + timedelta(days=6):%d/%m/%Y})
- Giai đoạn huấn luyện: {PHASE_LABEL[phase]}
- Mục tiêu: {profile.get('goal')}
- Pace hiện tại (đã hiệu chỉnh theo thực tế): {profile.get('current_pace')} /km, Pace mục tiêu: {target_pace} /km{target_line}
- Ngày thi đấu: {_race_info(profile, today)}
- Khoảng cách tối đa mỗi buổi (đã mở rộng theo tiến độ): {max_dist:g} km
- Chấn thương: {to_text(profile.get('injuries')) or 'Không có'}
- Ghi chú của runner: {to_text(profile.get('notes')) or 'Không có'}
- Các ngày có thể tập: {days_str}

{zone_block}

[LỊCH SỬ]
{history}

{insight_block}

[RÀNG BUỘC BẮT BUỘC]
{chr(10).join(rules)}

[CẤU TRÚC JSON]
{{
    "default_title": "Tuần {week_index}: [Tên]",
    "week_summary": "Lời khuyên ngắn gọn (<50 từ)",
    "schedule": [
        {{
            "day": "Thứ X",
            "workout_type": "Easy Run",
            "distance_km": 5.0,
            "pace_target": "06:30",
            "notes": "Ghi chú ngắn"
        }}
    ]
}}
"""


def generate_running_plan(api_keys, profile, plans, model_name=None, *, week_start=None, today=None,
                          client_factory=None, sleep=time.sleep, memory=None):
    today = today or today_vn()
    week_start = monday_of(week_start or default_week_start(today))
    week_index = next_week_index(plans)
    days_left = days_to_race(profile, today)
    phase = training_phase(days_left)

    eff_pace_sec = resolve_effective_pace(profile, plans)
    eff_max_dist = resolve_effective_max_dist(profile, plans)
    effective_profile = dict(
        profile,
        current_pace=sec_to_pace(eff_pace_sec) if eff_pace_sec else profile.get("current_pace"),
        target_pace=resolve_target_pace(profile),
        max_distance=eff_max_dist,
    )

    zones = compute_zones(effective_profile, phase, plans)
    signals = load_signals(plans)
    cap, cap_reason, _ = compute_weekly_cap(plans, week_index, days_left)
    insights = build_insight_block(plans, memory)
    prompt = build_prompt(effective_profile, build_history_text(plans), week_index, week_start, today,
                          phase, zones, cap, cap_reason, signals, has_history=bool(plans), insights=insights)

    def task(client, active_model, use_schema):
        data = _call_model(client, active_model, prompt, PlanModel if use_schema else None)
        if not isinstance(data, dict) or not isinstance(data.get("schedule"), list):
            raise AIOutputError("JSON thiếu cấu trúc 'schedule'.")
        cleaned, warns = validate_plan(data["schedule"], effective_profile, week_start=week_start,
                                       zones=zones, cap_km=cap)
        if not cleaned:
            raise AIOutputError("AI không trả về buổi tập hợp lệ nào.")
        return {
            "default_title": to_text(data.get("default_title")) or f"Tuần {week_index}",
            "week_summary": to_text(data.get("week_summary")),
            "schedule": cleaned, "warnings": warns,
            "ai_schedule": copy.deepcopy(cleaned),
        }

    models = _normalize_model_list(model_name)
    result, used_model, err = run_with_models_and_keys(
        api_keys, models, task, client_factory=client_factory, sleep=sleep
    )
    if err:
        return {"error": err}
    result.update({
        "week_start": week_start.isoformat(), "week_index": week_index, "phase": phase,
        "cap_km": cap, "cap_reason": cap_reason, "model_used": used_model, "insights": insights,
        "zones": {t: [round(lo), round(hi)] for t, (lo, hi) in zones.items()},
    })
    return result


def regenerate_session(api_keys, profile, draft, day, model_name=None, hint="", *,
                       client_factory=None, sleep=time.sleep):
    others = [it for it in draft.get("schedule", []) if normalize_day(it.get("day")) != day]
    cap = draft.get("cap_km")
    remaining = max(cap - sum(km_planned(o) for o in others if is_run(o)), 1.0) if cap else None
    zones = {t: tuple(v) for t, v in (draft.get("zones") or {}).items()}
    ws = parse_iso_date(draft.get("week_start"))
    prof = dict(profile, days=sorted(set(profile.get("days") or []) | {day}))
    max_dist = float(profile.get("max_distance") or 8.0)

    ctx = "\n".join(f"- {o.get('day')}: {o.get('workout_type')} {km_planned(o):.1f} km @ {o.get('pace_target')}" for o in others) or "(không có)"
    prompt = f"""
Bạn là Huấn luyện viên Chạy bộ AI. Hãy thiết kế LẠI đúng 1 buổi tập cho {day} trong tuần đang soạn.

[CÁC BUỔI KHÁC TRONG TUẦN]
{ctx}

[RÀNG BUỘC]
- Mục tiêu: {profile.get('goal')}. Chấn thương: {to_text(profile.get('injuries')) or 'Không có'}.
- distance_km không vượt quá {max_dist:g}{f'; km còn lại của tuần tối đa {remaining:.1f}' if remaining else ''}.
- workout_type chỉ là một trong: {', '.join(WORKOUT_TYPES)}.
{('- Vùng pace:' + chr(10) + zones_text(zones)) if zones else ''}
- Yêu cầu thêm của runner: {to_text(hint) or 'không có'}
- Buổi mới phải KHÁC buổi hiện tại ở {day}. Chỉ trả về 1 đối tượng JSON.

[CẤU TRÚC JSON]
{{"day": "{day}", "workout_type": "Easy Run", "distance_km": 5.0, "pace_target": "06:30", "notes": "Ghi chú ngắn"}}
"""

    def task(client, active_model, use_schema):
        data = _call_model(client, active_model, prompt, SessionModel if use_schema else None)
        if isinstance(data, dict) and isinstance(data.get("schedule"), list) and data["schedule"]:
            data = data["schedule"][0]
        if not isinstance(data, dict):
            raise AIOutputError("JSON buổi tập không hợp lệ.")
        data["day"] = day
        cleaned, warns = validate_plan([data], prof, week_start=ws, zones=zones, cap_km=remaining)
        if not cleaned:
            raise AIOutputError("AI không trả về buổi tập hợp lệ.")
        return {"item": cleaned[0], "warnings": warns}

    models = _normalize_model_list(model_name)
    result, used_model, err = run_with_models_and_keys(
        api_keys, models, task, client_factory=client_factory, sleep=sleep
    )
    if err:
        return {"error": err}
    result["model_used"] = used_model
    return result
