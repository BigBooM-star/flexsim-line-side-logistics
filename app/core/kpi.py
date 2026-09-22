"""四段成本函数 —— 全软件唯一口径出口（看板/测算/仿真/导出共用）。

C_total = C_运输 + C_库存 + C_人工 + C_缺料
  C_运输 = c_d × 行驶段数
  C_库存 = h × 平均在库件数(10库合计) × 窗口小时数
  C_人工 = c_labor × 人·小时（设定A：固定班组 → 组间常数，禁止声称省人工）
  C_缺料 = c_stop × 缺料分钟（what-if 场景才有非零值；现行四组实测=0）
"""


def cost_breakdown(basis: dict, *, legs: float, wip_avg_units: float,
                   hours: float, stockout_min: float = 0.0) -> dict:
    co = basis["coefficients"]
    q = basis.get("quantities", {})
    c_transport = co["c_d_per_leg"] * legs
    c_inventory = co["h_per_unit_hour"] * wip_avg_units * hours
    c_labor = co["c_labor_per_shift_hour"] * q.get("labor_person_hours", 1200)
    c_stockout = co["c_stop_per_minute"] * stockout_min
    total = c_transport + c_inventory + c_labor + c_stockout
    return {
        "transport": round(c_transport, 2),
        "inventory": round(c_inventory, 2),
        "labor": round(c_labor, 2),
        "stockout": round(c_stockout, 2),
        "total": round(total, 2),
        "currency": basis.get("currency", "相对系数"),
        "preset": basis.get("preset"),
        "disclaimer": basis.get("disclaimer", ""),
    }
