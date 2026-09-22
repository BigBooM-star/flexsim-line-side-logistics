"""预计算：日志+报表 → cache/*.json，并打印全量验证表。

用法：python -m app.precompute [--force]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

from .ingest import coords as C
from .ingest import events as E
from .ingest import reports as R
from .settings import CACHE_DIR, MAIN_GROUPS, SETTINGS, log_path, source_mtimes, state_path, summary_path

GROUP_LABELS = {
    "1": "组1 基线·逐件拉动", "2": "组2 定时补满", "3": "组3 固定SS",
    "4": "组4 动态SS_t", "5.1": "组5.1 压力工况·消耗×1.5(静态SS)"}
EXPECTED_LEGS = {"1": 2581, "2": 1296, "3": 1118, "4": 1299, "5.1": 1627}  # v3 报告口径，仅作对照打印
W0, W1 = 7200.0, 432000.0


def _write(name, obj):
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / name).write_text(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _fresh():
    src = source_mtimes()
    if not src:
        return False          # 一个数据源都没找到：视为不新鲜，交给 build() 报明确错误
    needed = ["kpi_actuals.json", "layout.json", "distances.json"] + \
             [f"replay_g{i}.json" for i in MAIN_GROUPS]
    if log_path("5.1").exists():
        needed.append("replay_g5.1.json")
    for n in needed:
        f = CACHE_DIR / n
        if not f.exists():
            return False
    cm = min((CACHE_DIR / n).stat().st_mtime for n in needed)
    return cm >= max(src.values())


def surge_windows():
    ws = []
    k = 0
    while k * 28800 + 21600 < W1:
        a, b = k * 28800 + 21600, min((k + 1) * 28800, W1)
        if b > W0:
            ws.append([max(a, W0), b])
        k += 1
    return ws


def build():
    t0 = time.time()
    rects, xy, size = C.load_coords(SETTINGS["coords_csv"])
    flex2id = C.flexsim_to_id

    def xy_of_id(i):
        if i in xy:
            return xy[i]
        raise KeyError(f"坐标表缺少对象 {i}")

    _write("layout.json", C.layout_model(rects, xy))

    kpi = {"meta": {"window": [W0, W1], "labels": {g: GROUP_LABELS[g] for g in MAIN_GROUPS},
                    "surge_windows": surge_windows(),
                    "source_mtime": source_mtimes()}, "groups": {}}
    all_pairs = {}

    groups = list(MAIN_GROUPS) + (["5.1"] if log_path("5.1").exists() else [])
    for g in groups:
        rep = R.load_summary(summary_path(g))
        st = R.load_state(state_path(g))
        df = E.load_log(log_path(g))
        pay = E.reconstruct_group(df, rep, xy_of_id, flex2id, W0, W1)
        pay["label"] = GROUP_LABELS[g]
        _write(f"replay_g{g}.json", pay)
        if g in MAIN_GROUPS:  # 距离/标定表只用主四组，压力组不污染（车队拥堵会拉长腿时长）
            for k, v in pay["pair_durations"].items():
                all_pairs.setdefault(k, []).extend(v)

        # ---- 验证打印 ----
        raw_travels = int((df["Object"].isin(E.CARS) &
                           (df["Event"] == "BeginTask: Travel")).sum())
        legs_total = sum(len(p["legs"]) for p in pay["cars"].values())
        cal = pay["calibration"]
        wip_cal = [c for c in cal if c["kind"] == "wip"]
        ok_all = all(c["ok"] for c in cal) and not pay["flags"]
        print(f"[组{g}] rows={len(df)} 段数: 原始Travel={raw_travels} "
              f"(未映射目的={pay['travel_unmapped']}) 重建腿={legs_total} "
              f"对照v3={EXPECTED_LEGS[g]} 标定{'全部OK' if ok_all else 'FAIL:' + str(pay['flags'])}")
        if not ok_all:
            for c in wip_cal:
                if not c["ok"]:
                    print("   FAIL", c)

        wip = R.wip_rows(rep)
        wsrows = R.ws_rows(rep)
        cars = R.car_rows(rep)
        bins_stack = np.array([[b / 100 for b in pay["buffers"][f"L{L}-WIP-{i}"]["bins"]]
                               for L in (1, 2) for i in range(1, 6)])
        any_zero_min = int((bins_stack <= 0.5).any(axis=0).sum())
        per_buf_zero = {oid: p["zero_min"] for oid, p in pay["buffers"].items()}
        kpi["groups"][g] = {
            "label": GROUP_LABELS[g],
            "wip_avg_total": round(float(wip["stats_contentavg"].sum()), 3),
            "wip_min_total": float(wip["stats_contentmin"].min()),
            "zero_buffers": int((wip["stats_contentmin"] == 0).sum()),
            "legs_car1": len(pay["cars"]["car 1"]["legs"]),
            "legs_car2": len(pay["cars"]["car 2"]["legs"]),
            "legs_total": legs_total,
            "raw_travel_events": raw_travels,
            "boxes_in": int(wip["stats_input"].sum()),
            "station_output": int(wsrows["stats_output"].sum()),
            "recon_zero_min_total": int(sum(per_buf_zero.values())),
            "any_zero_min": any_zero_min,
            "c0_by_buffer": {oid: pay["buffers"][oid]["c0"] for oid in pay["buffers"]},
            "state": {
                "workstations": {o: st.get(o, {}).get("pct", {}) for o in
                                 rep[rep["Class"] == "Processor"]["Object"]},
                "cars": {r["Object"]: {k2: r[k2] for k2 in
                                       ("idle", "travel empty", "travel loaded",
                                        "loading", "unloading") if k2 in st.get(r["Object"], {}).get("pct", {})}
                         for _, r in cars.iterrows()},
            },
            "calibration_ok": ok_all,
        }

    # ---- distances.json ----
    dist = {}
    ratios = []
    for pair, ds in all_pairs.items():
        a, b = pair.split("->")
        med = float(np.median(ds))
        pa, pb = xy.get(a), xy.get(b)
        man = (abs(pa[0] - pb[0]) + abs(pa[1] - pb[1])) if pa and pb else None
        dist[pair] = {"median_s": round(med, 1), "n": len(ds),
                      "manhattan_m": round(man, 1) if man else None}
        if man and man > 0.5:
            ratios.append(med / man)
    alpha = float(np.median(ratios)) if ratios else 1.4
    _write("distances.json", {"pairs": dist, "fallback_alpha_s_per_m": round(alpha, 3),
                              "note": "由主四组日志实测腿时长中位数标定（压力组5.1剔除，避免车队拥堵污染标定）；兜底=曼哈顿距离×alpha"})

    kpi["meta"]["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    kpi["meta"]["elapsed_s"] = round(time.time() - t0, 1)
    _write("kpi_actuals.json", kpi)
    print(f"预计算完成 {kpi['meta']['elapsed_s']}s → cache/{', '.join(sorted(p.name for p in CACHE_DIR.glob('*.json')))}")
    return kpi


def convert_plan_pdf():
    """用户实际模型平面图 PDF → SVG（尽力而为，失败仅警告）。"""
    from .settings import FROZEN
    if FROZEN:
        return None  # 绿包内 plan.svg 已随 static/gen 打包，无需（也不能）重转
    try:
        import fitz
        pdf = SETTINGS["plan_pdf"]
        if not pdf.exists():
            print(f"[warn] 平面图 PDF 不存在: {pdf}")
            return None
        doc = fitz.open(pdf)
        out = Path(SETTINGS.get("static_dir", Path(__file__).resolve().parents[1])) / "static" / "gen"
        out.mkdir(parents=True, exist_ok=True)
        svg = doc[0].get_svg_image(matrix=fitz.Matrix(1, 1))
        f = out / "plan.svg"
        f.write_text(svg, encoding="utf-8")
        doc.close()
        print(f"平面图 PDF→SVG: {f} ({f.stat().st_size // 1024} KB)")
        return f
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 平面图转换失败（不影响主功能）: {e}")
        return None


def main(force=False):
    if not force and _fresh():
        print("缓存已新鲜，跳过预计算（--force 重建）")
        return
    build()
    convert_plan_pdf()


if __name__ == "__main__":
    main(force="--force" in sys.argv)
