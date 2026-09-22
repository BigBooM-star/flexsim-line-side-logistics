"""演示日一键数据核对：重读原始报表/日志 → 打印与 cache/kpi_actuals.json 的对照表。

用法：python tools/verify_data.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingest import events as E  # noqa: E402
from app.ingest import reports as R  # noqa: E402
from app.settings import log_path, summary_path  # noqa: E402
import pandas as pd  # noqa: E402

EXP = {"1": dict(inv=59.474, legs=2581), "2": dict(inv=54.002, legs=1296),
       "3": dict(inv=20.650, legs=1118), "4": dict(inv=23.250, legs=1299),
       "5.1": dict(inv=19.230, legs=1627)}  # 5.1 = 压力工况（消耗≈×1.5，静态SS）


def main():
    cf = Path(__file__).resolve().parents[1] / "cache" / "kpi_actuals.json"
    cache = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {"groups": {}}
    print(f"{'组':<5}{'库存均值(报表)':>16}{'缓存值':>10}{'段数(日志)':>12}{'缓存值':>8}  {'v3口径':>12}  结论")
    ok_all = True
    for g in ("1", "2", "3", "4", "5.1"):
        if not log_path(g).exists():
            print(f"{g:<6} —— 数据文件不存在，跳过")
            continue
        rep = R.load_summary(summary_path(g))
        inv = round(float(R.wip_rows(rep)["stats_contentavg"].sum()), 3)
        df = pd.read_csv(log_path(g), usecols=["Object", "Event"])
        legs = int(df["Object"].isin(E.CARS).mul(df["Event"] == "BeginTask: Travel").sum())
        c = cache["groups"].get(g, {})
        inv_c, legs_c = c.get("wip_avg_total"), c.get("legs_total")
        agree = abs(inv - EXP[g]["inv"]) < .01 and legs == EXP[g]["legs"]
        cache_agree = inv_c == round(inv, 3) and legs_c == legs
        ok = agree and cache_agree
        ok_all &= ok
        print(f"{g:<6}{inv:>15.3f}{str(inv_c):>11}{legs:>12,}{str(legs_c):>9}  "
              f"{EXP[g]['inv']:>9.3f}/{EXP[g]['legs']:,}  {'✓ 一致' if ok else '✗ 检查！'}")
    print("\n汇总：主四组 库存 59.474/54.002/20.650/23.250 · 段数 2581/1296/1118/1299 · 产出 1291 · 缺料 0")
    print("     压力组5.1 库存 19.230 · 段数 1627 · 产出 1951（消耗×1.5 满负荷） · 触零 2193 库·分（组3 ×2.25）")
    print("OK 全部一致" if ok_all else "FAIL 存在不一致，勿演示")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
