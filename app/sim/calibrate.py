"""标定验收：迷你仿真复刻组3 参数 × 多种子，网格搜 (cart_cap, check_period)，
以实测 20.65/1118/1291 为目标选出等效参数 → cache/calibration.json。

用法：python -m app.sim.calibrate [--force]
"""
import json
import sys
import time

from .engine import Sim, STRATEGY_PRESETS
from ..settings import CACHE_DIR

TARGET = {"wip_avg_total": 20.65, "legs": 1118, "output": 1291}
SEEDS = (7, 11, 23)
GRID = [(cc, f) for cc in (3, 4, 6, 8, 12) for f in (1200, 1800, 3600)]
TOL = 0.10


def _eval(cc, f):
    runs = []
    for sd in SEEDS:
        p = dict(STRATEGY_PRESETS["threshold"])
        p["cart_cap"], p["check_period"] = cc, f
        runs.append(Sim(p, seed=sd).run())
    avg = {k: sum(r[k] for r in runs) / len(runs) for k in ("wip_avg_total", "legs", "output")}
    dev = {k: (avg[k] - TARGET[k]) / TARGET[k] for k in TARGET}
    score = sum(abs(v) for v in dev.values())
    return avg, dev, score


def main(force=False):
    out = CACHE_DIR / "calibration.json"
    if out.exists() and not force:
        print("calibration.json 已存在（--force 重标定）")
        return
    t0 = time.time()
    best = None
    for cc, f in GRID:
        avg, dev, score = _eval(cc, f)
        print(f"cart_cap={cc:>2} f={f:>4}  inv={avg['wip_avg_total']:.2f} "
              f"legs={avg['legs']:.0f} out={avg['output']:.0f}  "
              f"dev: {dev['wip_avg_total']*100:+.1f}% / {dev['legs']*100:+.1f}% / "
              f"{dev['output']*100:+.1f}%  score={score:.3f}")
        if best is None or score < best["score"]:
            best = {"cart_cap": cc, "check_period": f, "avg": avg, "dev": dev,
                    "score": score, "seeds": list(SEEDS)}
    ok = all(abs(v) <= TOL for v in best["dev"].values())
    pay = {
        "target_actuals": TARGET,
        "best": best,
        "pass_10pct": ok,
        "note": ("组3（SS=1,Q=3,双车）用等效参数复现实测：轮询等效周期与单车容量为标定旋钮，"
                 "等效≠FlexSim原值（原值3600s/代码8/表12），用于向评委解释仿真校验口径。"),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
    }
    out.write_text(json.dumps(pay, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ cache/calibration.json  {'PASS ≤10%' if ok else 'FAIL >10%（作灵敏度呈现）'} "
          f"best={best['cart_cap']},{best['check_period']} {pay['elapsed_s']}s")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
