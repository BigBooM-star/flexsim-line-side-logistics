"""测算路由：/api/estimate —— 解析即时值 + 迷你仿真校验值 + 当前口径成本。"""
from fastapi import APIRouter

from ..core.kpi import cost_breakdown
from ..core.schemas import EstimateReq
from ..sim.analytic import analytic_estimate
from ..sim.engine import Sim, STRATEGY_PRESETS
from .cacheio import config

router = APIRouter(tags=["estimate"])

SEEDS = (7, 11, 23)
# 标定等效映射：用户滑杆是“名义参数”，引擎按组3标定换算（见 calibration.json note）
EQ = {"check_mult": 0.5, "cart_cap_max": 4}
ACTUALS = {"1": {"wip_avg_total": 59.474, "legs": 2581},
           "2": {"wip_avg_total": 54.002, "legs": 1296},
           "3": {"wip_avg_total": 20.650, "legs": 1118},
           "4": {"wip_avg_total": 23.250, "legs": 1299}}


def _sim(req: EstimateReq):
    preset = dict(STRATEGY_PRESETS[req.strategy])
    p = {**preset,
         "ss": req.ss, "target": req.target, "cap": req.cap,
         "check_period": max(300.0, req.check_period * EQ["check_mult"]),
         "cart_cap": min(req.cart_cap, EQ["cart_cap_max"])}
    runs = [Sim(p, seed=sd).run() for sd in SEEDS]
    out = {}
    for k in ("wip_avg_total", "legs", "output", "stockout_min", "zero_buf_min"):
        vals = [r[k] for r in runs]
        out[k] = round(sum(vals) / len(vals), 2)
    out["seeds"] = list(SEEDS)
    return out


def _cost(basis, legs, inv, stockout_min):
    return cost_breakdown(basis, legs=legs, wip_avg_units=inv,
                          hours=basis["quantities"]["cost_window_hours"],
                          stockout_min=stockout_min)


@router.post("/api/estimate")
def estimate(req: EstimateReq):
    ana = analytic_estimate(strategy=req.strategy, ss=req.ss, target=req.target,
                            cap=req.cap, check_period=req.check_period,
                            cart_cap=req.cart_cap, hours=req.hours)
    basis = config("cost_basis.json")
    sim = _sim(req)
    return {
        "params": req.model_dump(),
        "analytic": {**ana, "cost": _cost(basis, ana["legs_est"], ana["wip_avg_total"], 0.0)},
        "sim": {**sim, "cost": _cost(basis, sim["legs"], sim["wip_avg_total"],
                                     sim["stockout_min"])},
        "equivalent_mapping": {**EQ, "note": "仿真按组3标定做等效映射（f→f/2，单车容量≤4），详见标定说明"},
        "basis": {"preset": basis["preset"], "currency": basis["currency"],
                  "label": basis["label"]},
    }


@router.get("/api/calibration")
def calibration():
    import json
    from ..settings import CACHE_DIR
    p = CACHE_DIR / "calibration.json"
    return {"calibration": json.loads(p.read_text(encoding="utf-8")) if p.exists() else None,
            "actuals_ref": ACTUALS}
