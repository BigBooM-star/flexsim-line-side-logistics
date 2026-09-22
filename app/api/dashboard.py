"""看板路由：/api/dashboard —— 四组实测 KPI + 当前口径下的四段成本。"""
from fastapi import APIRouter

from ..core.kpi import cost_breakdown
from .cacheio import cache, cache_ready, config

router = APIRouter(tags=["dashboard"])

_SERIES_MEM: dict = {}

# statereport 中各对象类别的关键状态（利用率环形图用）
WS_KEYS = ("processing", "idle", "waiting for transporter", "blocked")
CAR_KEYS = ("travel empty", "travel loaded", "loading", "unloading", "idle", "waiting for transporter")


def _pick(state_pct: dict, keys) -> dict:
    return {k: round(float(state_pct.get(k, 0.0)), 2) for k in keys}


@router.get("/api/dashboard")
def dashboard():
    if not cache_ready():
        return {"ready": False, "hint": "请先运行 python -m app.precompute"}
    k = cache("kpi_actuals.json")
    basis = config("cost_basis.json")
    hours = basis.get("quantities", {}).get("cost_window_hours", 120)
    out = {"ready": True, "basis": {
        "preset": basis.get("preset"), "label": basis.get("label"),
        "currency": basis.get("currency"), "disclaimer": basis.get("disclaimer", ""),
        "coefficients": basis.get("coefficients"), "cost_window_hours": hours,
    }, "groups": []}
    for g in ("1", "2", "3", "4"):
        d = k["groups"][g]
        cost = cost_breakdown(basis, legs=d["legs_total"],
                              wip_avg_units=d["wip_avg_total"], hours=hours,
                              stockout_min=0.0)  # 现行口径四组缺料=0，页面上明示
        st = d.get("state", {})
        ws = {o: _pick(p, WS_KEYS) for o, p in st.get("workstations", {}).items()}
        cars = {o: _pick(p, CAR_KEYS) for o, p in st.get("cars", {}).items()}
        out["groups"].append({
            "group": int(g), "label": d["label"],
            "kpi": {k2: d[k2] for k2 in (
                "wip_avg_total", "wip_min_total", "zero_buffers", "legs_car1", "legs_car2",
                "legs_total", "raw_travel_events", "boxes_in", "station_output",
                "recon_zero_min_total", "any_zero_min", "calibration_ok")},
            "cost": cost,
            "workstations": ws, "cars": cars,
            "c0_by_buffer": d["c0_by_buffer"],
        })
    out["meta"] = {"window": k["meta"]["window"], "labels": k["meta"]["labels"],
                   "surge_windows": k["meta"]["surge_windows"],
                   "generated": k["meta"].get("generated")}
    return out


_STEP = 6  # 60s bins → 360s 采样


def _series_one(k: dict, g: str):
    """单组 10 库合计库存序列（带 mtime 内存缓存）。"""
    import json
    from ..settings import CACHE_DIR
    f = CACHE_DIR / f"replay_g{g}.json"
    key = f"{f}:{f.stat().st_mtime}"
    cached = _SERIES_MEM.get(key)
    if cached is None:
        rp = json.loads(f.read_text(encoding="utf-8"))
        nb = len(next(iter(rp["buffers"].values()))["bins"])
        tot = [0] * nb
        for b in rp["buffers"].values():
            for i, v in enumerate(b["bins"]):
                tot[i] += v
        tot = [t / 100.0 for t in tot]
        series = []
        for i in range(0, nb, _STEP):
            chunk = tot[i:i + _STEP]
            series.append(round(sum(chunk) / len(chunk), 2))
        cached = [[i * _STEP * 60 + 7200 for i in range(len(series))], series]
        if len(_SERIES_MEM) > 12:
            _SERIES_MEM.clear()
        _SERIES_MEM[key] = cached
    t, v = cached
    return {"group": g, "label": k["groups"][g]["label"], "t": t, "v": v}


@router.get("/api/dashboard/series")
def dashboard_series(groups: str = "1,2,3,4"):
    """10 库合计库存时间序列（分箱均值下采样），带内存缓存。groups 逗号分隔，可含 5.1。"""
    if not cache_ready():
        return {"ready": False}
    k = cache("kpi_actuals.json")
    out = {"ready": True, "groups": []}
    for g in [x.strip() for x in groups.split(",") if x.strip()]:
        if g in k["groups"]:
            out["groups"].append(_series_one(k, g))
    return out


_KPI_KEYS = ("wip_avg_total", "wip_min_total", "zero_buffers", "legs_car1", "legs_car2",
             "legs_total", "raw_travel_events", "boxes_in", "station_output",
             "recon_zero_min_total", "any_zero_min", "calibration_ok")


@router.get("/api/stress")
def stress():
    """压力工况对照：组3（静态SS基线） vs 组5.1（消耗×1.5 压力）。"""
    if not cache_ready():
        return {"ready": False, "hint": "缓存未就绪"}
    k = cache("kpi_actuals.json")
    if "5.1" not in k["groups"]:
        return {"ready": False,
                "hint": "组5.1 未接入：将 lab5.1/summaryreport5.1/statereport5.1 放入数据目录后重跑预计算"}
    basis = config("cost_basis.json")
    hours = basis.get("quantities", {}).get("cost_window_hours", 120)

    def entry(g):
        d = k["groups"][g]
        cost = cost_breakdown(basis, legs=d["legs_total"], wip_avg_units=d["wip_avg_total"],
                              hours=hours, stockout_min=0.0)
        return {"group": g, "label": d["label"],
                "kpi": {k2: d[k2] for k2 in _KPI_KEYS}, "cost": cost}

    return {"ready": True, "basis": {"label": basis.get("label"), "currency": basis.get("currency")},
            "base": entry("3"), "stress": entry("5.1"),
            "note": ("组5.1 与组3 唯一差异：工位消耗过程整体提速 ≈×1.5（需求间隔均值/σ 同除 1.495）。"
                     "该工况下产出同步放大至满负荷、缺料停线=0（台前操作手队列吸收了分钟级断料），"
                     "但线边空库暴露时长 ×2.25——静态 SS=1 的安全边际已被吃穿，"
                     "为动态 SS_t 的必要性提供压力侧证据。")}
