"""事件日志解析：WIP/FG 库存曲线重建（报表常数标定）、AGV 行驶腿、站点产出分箱。

关键口径（均已在真实数据上验证）:
- 只信 Trigger: OnEntry/OnExit（±1）；Engine: Send/Receive 是同一流动的重复记录，必须剔除。
- 日志本身即因果序，不重新排序（同时戳保持原序）。
- 水位初值未知 → 常数偏移标定：c0 = 报表 contentavg − 重建(c0=0)时间加权均值，向整数吸附。
"""
import re

import pandas as pd

WIP_EVT_ADD = "Trigger: OnEntry"
WIP_EVT_SUB = "Trigger: OnExit"
CARS = ["/car 1", "/car 2"]

WIP_PATH_RE = re.compile(r"^/Line \d WIP Buffer Area \d+$")
FG_PATH_RE = re.compile(r"^/Line \d Finished Goods Buffer Area \d+$")
WS_PATH_RE = re.compile(r"^/Line \d Workstation \d+$")


def load_log(path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=["Time", "Event", "Object", "Involved"],
                     encoding="utf-8-sig", dtype={"Time": "float64"})
    for c in ("Event", "Object", "Involved"):
        df[c] = df[c].astype("string")
    return df


def _check_monotonic(df: pd.DataFrame, tag: str):
    t = df["Time"].to_numpy()
    if len(t) > 1 and (t[1:] - t[:-1] < -1e-9).any():
        raise AssertionError(f"{tag}: 日志时间非单调，重建假设不成立")


def _bin_sums(ts, lv, w0, w1, bin=60):
    """步进水位的每分箱时间加权积分（level 在各 ts 后跳变为 lv 值，首段取 0）。"""
    nb = int((w1 - w0) / bin)
    sums = [0.0] * nb
    seg_a = [w0] + list(ts)
    seg_b = list(ts) + [w1]
    seg_v = [0.0] + list(lv)
    for a, b, v in zip(seg_a, seg_b, seg_v):
        if b <= a:
            continue
        i0 = max(int((a - w0) // bin), 0)
        i1 = min(int((b - 1e-9 - w0) // bin), nb - 1)
        for i in range(i0, i1 + 1):
            lo = max(a, w0 + i * bin)
            hi = min(b, w0 + (i + 1) * bin)
            if hi > lo:
                sums[i] += (hi - lo) * v
    return sums, nb


def reconstruct_group(df, report_summary, xy_of_id, flexsim_to_id,
                      w0=7200.0, w1=432000.0):
    """一组日志 → replay JSON 载荷（含标定验证表 + 跨路段时长样本）。"""
    _check_monotonic(df, "log")
    out = {"window": [w0, w1], "bin": 60, "buffers": {}, "calibration": [],
           "flags": [], "fg": {}, "station_out": {}, "cars": {},
           "pair_durations": {}, "travel_unmapped": 0}

    # ---- WIP / FG 曲线 ----
    for pat, key in ((WIP_PATH_RE, "buffers"), (FG_PATH_RE, "fg")):
        for obj in sorted(o for o in df["Object"].unique() if o and pat.match(o)):
            oid = flexsim_to_id(obj)
            rep_name = obj.lstrip("/")
            d = df[(df["Object"] == obj) &
                   (df["Event"].isin([WIP_EVT_ADD, WIP_EVT_SUB]))]
            t = d["Time"].to_numpy()
            v = (d["Event"] == WIP_EVT_ADD).to_numpy(dtype="float64") * 2 - 1
            lv0 = v.cumsum()
            sums, nb = _bin_sums(t, lv0, w0, w1)
            mean_raw = sum(sums) / (w1 - w0)
            avg_rep = float(report_summary.loc[rep_name, "stats_contentavg"])
            offset = avg_rep - mean_raw
            c0 = round(offset) if abs(offset - round(offset)) <= 0.25 else offset
            lv = lv0 + c0
            final = lv[-1] if len(lv) else c0
            mn = float(lv.min()) if len(lv) else c0
            mx = float(lv.max()) if len(lv) else c0
            cmin_rep = float(report_summary.loc[rep_name, "stats_contentmin"])
            cmax_rep = float(report_summary.loc[rep_name, "stats_contentmax"])
            fin_rep = float(report_summary.loc[rep_name, "stats_content"])
            ok = (abs(final - fin_rep) <= 0.51 and mn >= -0.01
                  and mn >= cmin_rep - 1.01 and mx <= cmax_rep + 1.01)
            bins = [int(round(s / 60 * 100)) + int(round(c0 * 100)) for s in sums]
            out[key][oid] = {"bins": bins, "c0": c0,
                             "zero_min": sum(1 for b in bins if b <= 0), "ok": ok}
            out["calibration"].append({
                "obj": rep_name, "kind": "wip" if key == "buffers" else "fg",
                "avg_report": round(avg_rep, 3), "mean_recon_c0": round(mean_raw, 3),
                "offset": round(offset, 3), "c0": c0, "final": float(final),
                "final_report": fin_rep, "minmax": [mn, mx],
                "minmax_report": [cmin_rep, cmax_rep], "ok": ok})
            if not ok:
                out["flags"].append(rep_name)

    # ---- AGV 行驶腿 ----
    for car in CARS:
        dc = df[df["Object"] == car]
        cid = car.lstrip("/")
        pos_id = cid
        pos = xy_of_id(cid)
        onboard = 0
        pending = None  # (t0, from_id, to_id)
        legs = []
        unmapped = 0
        for row in dc.itertuples(index=False):
            e = row.Event
            if e == "BeginTask: Travel":
                if pending is not None:  # 异常：上一段无到达任务，就地闭合
                    t0, a, b = pending
                    _close_leg(legs, out, xy_of_id, t0, row.Time, a, b, onboard)
                    pending = None
                dest = flexsim_to_id((row.Involved or "").strip())
                if dest is None:
                    unmapped += 1
                    continue
                pending = (row.Time, pos_id, dest)
            elif e in ("BeginTask: Load", "BeginTask: Unload"):
                if pending is not None:
                    t0, a, b = pending
                    _close_leg(legs, out, xy_of_id, t0, row.Time, a, b, onboard)
                    pos_id, pos = b, xy_of_id(b)
                    pending = None
            elif e == "Trigger: OnLoad":
                onboard += 1
            elif e == "Trigger: OnUnload":
                onboard = max(0, onboard - 1)
            elif e == "TaskSequence: Finish TS":
                if pending is not None:
                    t0, a, b = pending
                    _close_leg(legs, out, xy_of_id, t0, row.Time, a, b, onboard)
                    pos_id, pos = b, xy_of_id(b)
                    pending = None
        out["cars"][cid] = {"legs": legs}
        out["travel_unmapped"] += unmapped

    # ---- 站点产出（Engine: Send Object from Workstation，与报表 output 对账）----
    so = df[(df["Event"] == "Engine: Send Object") &
            (df["Object"].str.match(WS_PATH_RE))]
    nb = int((w1 - w0) / 60)
    for ws in sorted(so["Object"].dropna().unique()):
        oid = flexsim_to_id(ws)
        idx = ((so[so["Object"] == ws]["Time"].to_numpy() - w0) // 60).astype("int64")
        counts = [0] * nb
        for i in idx:
            if 0 <= i < nb:
                counts[i] += 1
        cum, run = [], 0
        for c in counts:
            run += c
            cum.append(run)
        out["station_out"][oid] = cum
    return out


def _close_leg(legs, out, xy_of_id, t0, t1, a_id, b_id, onboard):
    ax, ay = xy_of_id(a_id)
    bx, by = xy_of_id(b_id)
    legs.append([round(t0, 1), round(t1, 1), round(ax, 2), round(ay, 2),
                 round(bx, 2), round(by, 2), 1 if onboard > 0 else 0])
    if t1 - t0 >= 1.0:  # 退化 0 时长不计入距离样本
        out["pair_durations"].setdefault(f"{a_id}->{b_id}", []).append(t1 - t0)
