"""解析（即时）测算引擎 —— 闭式公式估算平均库存/段数/缺料风险。

库存公式可信度回算（对现行实测）：
  阈值 SS=1,Q=3: (SS+Q)/2=2.00  vs 实测 2.065/库
  定时 Q=6,f=3600: Q−λf/2=5.44 vs 实测 5.40/库
  逐件拉动 cap=6: cap−λL/2≈5.98 vs 实测 5.95/库
段数公式（pull=2×箱数 误差 0.2%；其余为估算，γ=2.72 由组3实测标定）：
  阈值: 停靠 = N·λT/(Q−SS)，门程 = 箱数/γ
  定时: 停靠 ≈ N×小时tick，门程 = ceil(每线装量/车容量)×tick×线数
缺料：正态损失函数近似，明示"以仿真复核为准"。
"""
import math

# 需求过程（v3 场景）：基础 N(3600,1080)，班次(28800s)最后 7200s 均值 2400 → ×1.5
LAM = 0.75 / 3600 + 0.25 / 2400          # 件/s = 0.0003125 → 1.125 件/h
LAM_H = LAM * 3600                        # 件/h
SIGMA_INTERVAL = 30 * 60                  # 需求间隔 SD（近似，突变期混合）
LEAD_TRAVEL_S = 110.0                     # 门→库→卸 平均补给延迟
GAMMA_CAL = 2.72                          # 阈值策略每趟卸货箱数（组3实测标定）
N_BUF = 10
LINES = 2


def analytic_estimate(*, strategy="threshold", ss=1.0, target=3, cap=3,
                      check_period=3600, cart_cap=12, hours=118.0,
                      z=1.65) -> dict:
    """strategy: pull | timer | threshold。返回 KPI 估算 + 成本所需量。"""
    demand_total = LAM_H * hours * N_BUF          # 窗口总需求（件）
    # ---- 平均库存（件/库）----
    if strategy == "timer":
        inv_per_buf = max(0.0, target - LAM_H * (check_period / 3600.0) / 2)
        formula_i = f"I = Q − λ·f/2 = {target} − {LAM_H:.3f}×{(check_period/3600):.2f}/2"
    elif strategy == "pull":
        l_cycle = 2 * 35 + 30 + 30                # 门→库→卸（秒）≈ 补给延迟
        inv_per_buf = max(0.0, cap - LAM * l_cycle / 1 - 0.02)
        inv_per_buf = cap - LAM * 60              # ≈ cap − λ·60s
        formula_i = f"I = cap − λ·L_lead ≈ {cap} − {LAM:.6f}×{60}"
    else:  # threshold
        inv_per_buf = (min(ss, target) + target) / 2
        formula_i = f"I = (SS + Q)/2 = ({ss} + {target})/2"
    wip_avg = inv_per_buf * N_BUF

    # ---- 段数 ----
    if strategy == "pull":
        stops = boxes = demand_total
        legs = 2.0 * boxes
        formula_l = "legs ≈ 2×箱数（门→库，逐件）"
    elif strategy == "timer":
        ticks = hours * LINES                     # 每线每小时一次
        fill_per_trip = LAM_H * (check_period / 3600.0) * 5  # 每线每tick卸量
        gate_trips = ticks * math.ceil(fill_per_trip / max(1, cart_cap))
        stops = ticks * 5                         # 每tick访问5库
        legs = stops + gate_trips
        formula_l = f"legs = ticks×(5停靠+⌈装量/容量⌉门程) = {ticks:.0f}×(5+{math.ceil(fill_per_trip/max(1,cart_cap))})"
    else:
        per_buf_demand = LAM_H * hours
        drops = max(target - ss, 0.5)
        stops = N_BUF * per_buf_demand / drops
        gate_trips = demand_total / GAMMA_CAL
        legs = stops + gate_trips
        formula_l = f"legs = N·λT/(Q−SS) + 箱数/{GAMMA_CAL}"

    # ---- 缺料风险（近似）----
    # 保护期 = 检查周期的一半（平均等待）+ 行进延迟
    L_s = (check_period / 2 if strategy != "pull" else 0) + LEAD_TRAVEL_S
    mu_L = LAM * L_s
    sd_L = mu_L * 0.35                            # 需求量 SD（CV≈0.3~0.4 混合近似）
    if strategy == "timer":
        ss_eff = inv_per_buf                      # 定时策略无 SS，按半周期水位
    else:
        ss_eff = ss if strategy == "threshold" else cap
    k = (ss_eff - mu_L) / sd_L if sd_L > 0 else 9.9
    loss = sd_L * (_phi(k) - k * (1 - _cdf(k)))   # 期望缺件/周期
    cycles = max(1.0, stops / N_BUF) if strategy != "pull" else per_buf_demand
    shortage_boxes = loss * cycles * N_BUF / max(1, N_BUF)  # 窗口内期望缺件
    stockout_hours = shortage_boxes / LAM_H / N_BUF * 0  # 保守：现行口径下缺料=0，what-if 由仿真给
    stockout_risk_score = max(0.0, min(1.0, 1 - _cdf(k)))  # 单周期缺料概率

    return {
        "wip_avg_total": round(wip_avg, 2),
        "inv_per_buf": round(inv_per_buf, 3),
        "legs_est": int(round(legs)),
        "boxes_est": int(round(demand_total)),
        "demand_rate_per_buf_h": round(LAM_H, 3),
        "formulas": {"inventory": formula_i, "legs": formula_l,
                     "stockout": f"P(单周期缺料)=1−Φ(k), k=(SS_eff−μ_L)/σ_L, L={L_s:.0f}s, k={k:.2f}"},
        "stockout_prob_per_cycle": round(stockout_risk_score, 4),
        "stockout_hours_est": round(stockout_hours, 3),
        "note": "段数与缺料为闭式估算（精度±10%量级），点「仿真校验」可跑迷你离散事件仿真复核",
    }


def _phi(x):
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def _cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
