"""导出路由：/api/export/kpi.csv（Excel 无乱码）与 /api/export/ss-table（FlexSim importtable 直读）。"""
import csv
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..core.kpi import cost_breakdown
from .cacheio import cache, cache_ready, config

router = APIRouter(tags=["export"])


@router.get("/api/export/kpi.csv")
def kpi_csv():
    if not cache_ready():
        raise HTTPException(404, "cache missing")
    k = cache("kpi_actuals.json")
    basis = config("cost_basis.json")
    hours = basis["quantities"]["cost_window_hours"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["组", "方案", "平均在库(10库合计,件)", "入库箱数", "行驶段数", "车1段", "车2段",
                "产出(台)", "缺料(分,实测)", "触零时长(库·分,重建)",
                "运输成本", "库存成本", "人工成本", "缺料成本", "总成本", "口径"])
    for g in ("1", "2", "3", "4"):
        d = k["groups"][g]
        c = cost_breakdown(basis, legs=d["legs_total"], wip_avg_units=d["wip_avg_total"],
                           hours=hours, stockout_min=0.0)
        w.writerow([g, d["label"], d["wip_avg_total"], d["boxes_in"], d["legs_total"],
                    d["legs_car1"], d["legs_car2"], d["station_output"], 0,
                    d["recon_zero_min_total"],
                    c["transport"], c["inventory"], c["labor"], c["stockout"], c["total"],
                    basis["label"]])
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kpi_actuals.csv"'})


@router.get("/api/export/ss-table")
def ss_table(hour_from: int = 0, hour_to: int = 120,
             base: float = 1.0, surge_boost: float = 1.0, mode: str = "surge"):
    """生成 FlexSim 可直接 importtable 的 SS_t：无表头、hour,value、CRLF、0..120 共 121 行。
    mode=surge：班次(8h)最后 2h 提升 boost；mode=static：恒为 base。"""
    if not 0 <= hour_from <= hour_to <= 120:
        raise HTTPException(422, "需 0 ≤ hour_from ≤ hour_to ≤ 120")
    lines = []
    for h in range(0, 121):
        in_hour = h % 8
        v = base
        if mode == "surge" and in_hour >= 6:
            v = base + surge_boost
        if h < hour_from or h > hour_to:
            v = base
        lines.append(f"{h},{v:g}")
    return Response(
        content="\r\n".join(lines) + "\r\n",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ss_table.csv"'})
