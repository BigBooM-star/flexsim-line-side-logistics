---
name: line-side-logistics
description: 汽车总装车间线边物料配送仿真软件（安徽省"AI+物流"大赛参赛作品）。当需要在本仓库运行/修改软件、接入新的 FlexSim 实验数据、调整成本口径或补货参数测算模型、重打免安装绿包时使用。
---

# 线边物料配送 · 可视化与成本测算软件

FlexSim 四组对照实验（静态 vs 动态补货参数）的配套演示软件：
FastAPI + 离线 ECharts 前端，**解析公式 × 迷你离散事件仿真双引擎**参数测算，
成本口径联动，SS_t 参数表一键导出回灌 FlexSim。数据全部从原始日志重算，不手抄。

## 快速命令

```bash
pip install -r requirements.txt   # fastapi/uvicorn/pandas/numpy/PyMuPDF/pydantic
python run.py                     # 启动（默认 127.0.0.1:8765，占用自动 +8）
python -m app.precompute --force  # 数据变化后重建缓存（~30-60s）
python tools/verify_data.py       # 提交前核对：原始文件 vs 缓存 vs v3 口径
python tools/make_dist.py         # 打免安装绿包 dist/（PyInstaller onedir，勿提交）
```

## 架构地图

- `data/` — FlexSim 原始导出（`lab{g} 432000.csv` 事件日志、`summaryreport{g}.csv`、`statereport{g}.csv`、坐标表、平面图）。文件名格式 `{group}` ∈ {1,2,3,4,5.1}
- `app/settings.py` — 路径解析中枢。**冻结模式**：exe 运行时 config/cache/data 在 exe 同级可写目录，static 打进 `_internal`（`sys._MEIPASS`）；settings 支持相对路径
- `app/ingest/` — 报表解析（`reports.py`，statereport 表头不在固定行、数值含 `%` 字符串）、事件日志重建（`events.py`：OnEntry+1/OnExit−1 分箱、c0 常数标定至报表均值、car legs、Engine 家族重复记录剔除）
- `app/precompute.py` — 缓存产物生成；`_fresh()` 按 mtime 判新鲜（copy2 保时戳 = 绿包秒开的关键）
- `app/sim/` — `analytic.py` 闭式公式（Ī定时=Q−λf/2；Ī阈值=(SS+target)/2）、`engine.py` 迷你 DES（heapq，组3 逻辑复刻）、`calibrate.py` 三种子标定（验收 ≤10%）
- `app/api/` — dashboard / replay / estimate(POST) / cost / export / misc(health)
- `static/js/pages/` — 五页前端；配色在 `palette.js`（Okabe-Ito 色盲安全，组5.1=#009E73）
- `config/` — settings.json 路径端口 · cost_basis.json 当前口径（PUT 持久化）· presets.json

## 接入新实验组（如压力组 5R/6R/7R）

1. 数据文件放进 `data/`，命名 `labX 432000.csv` + `summaryreportX.csv` + `statereportX.csv`
2. `app/settings.py` 的 `_GROUPS` 加映射；压力组**不要**进 `MAIN_GROUPS`（主四组故事与标定表必须隔离，防车队拥堵污染距离标定）
3. `app/precompute.py`：`GROUP_LABELS`、`EXPECTED_LEGS`、`_fresh()` 的文件存在性装配逻辑仿照 `"5.1"` 扩展
4. `app/api/replay.py` 的 `_LABELS/_LEGS_EXP`、`tools/verify_data.py` 的 `EXP` 同步
5. `python -m app.precompute --force && python tools/verify_data.py` 全绿才算完

## 口径红线（改动/写文档必须遵守）

- v3 现行基准：四组库存 **59.474 / 54.002 / 20.650 / 23.250** 件、段数 **2581 / 1296 / 1118 / 1299**、产出 1291、缺料 0；组4 vs 组3 真实价值 = 触零 **972→120 库·分钟（−87%）**
- 压力组 5.1：消耗≈×1.5（1.15 与 1.3 叠加），库存 19.230、段数 1627、产出 1951、触零 2193（×2.25）
- 成本单价是**行业占位值**（预设 B）有免责声明；**永远不得声称省人工**（人工是常数项）
- 早期 PDF 材料的 59.53/2344/AI+0.5% 是已作废旧口径
- 统计窗 = 7200s–432000s（预热 2h，120h 全程）
