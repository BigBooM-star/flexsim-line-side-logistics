"""回放与布局路由：/api/replay/{g}、/api/layout。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from .cacheio import cache, cache_ready

router = APIRouter(tags=["replay"])

_LABELS = {"1": "组1 基线·逐件拉动", "2": "组2 定时补满", "3": "组3 固定SS",
           "4": "组4 动态SS_t", "5.1": "组5.1 压力工况·消耗×1.5(静态SS)"}
_LEGS_EXP = {"1": 2581, "2": 1296, "3": 1118, "4": 1299, "5.1": 1627}


@router.get("/api/replay/{g}")
def replay(g: str):
    if g not in _LABELS or not cache_ready():
        raise HTTPException(404, "replay cache missing")
    try:
        data = cache(f"replay_g{g}.json")
    except FileNotFoundError:
        raise HTTPException(404, f"组{g} 数据未接入（缓存缺失）") from None
    kpi = cache("kpi_actuals.json")
    meta = {
        "group": g, "label": _LABELS[g],
        "surge_windows": kpi["meta"]["surge_windows"],
        "legs_expected": _LEGS_EXP[g],
    }
    return JSONResponse({"meta": meta, **data})


@router.get("/api/layout")
def layout():
    if not cache_ready():
        raise HTTPException(404, "layout cache missing")
    return cache("layout.json")
