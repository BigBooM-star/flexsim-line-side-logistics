"""全局配置：数据源路径、端口、缓存目录。

双形态运行：
- 开发：python run.py，路径基准 = 仓库根
- 绿包 exe（PyInstaller frozen）：config/cache/data 在 exe 同级目录（可写），
  static 打进 _MEIPASS（只读）；settings 里允许相对路径（相对 exe 目录解析）。
"""
import json
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))


def _base_dir() -> Path:
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _resource_dir() -> Path:
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", _base_dir() / "_internal"))
    return _base_dir()


ROOT = _base_dir()
CONFIG_DIR = ROOT / "config"
CACHE_DIR = ROOT / "cache"
STATIC_DIR = _resource_dir() / "static"

DEFAULTS = {
    "data_dir": "data",                      # 相对路径 = 仓库/exe 目录下的 data/
    "coords_csv": "data/对象坐标表.csv",
    "plan_pdf": "data/平面图-模型.pdf",
    "host": "127.0.0.1",
    "port": 8765,
    "sim_end": 432000,
    "warmup": 7200,
    "bin_seconds": 60,
}

_GROUPS = {
    "1": "lab1 432000.csv",
    "2": "lab2 432000.csv",
    "3": "lab3 432000.csv",
    "4": "lab4 432000.csv",
    # 压力工况（消耗过程整体提速≈×1.5，其余参数同组3）；文件存在才入缓存
    "5.1": "lab5.1 432000.csv",
}
MAIN_GROUPS = ("1", "2", "3", "4")


def _abs(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def load_settings() -> dict:
    s = dict(DEFAULTS)
    f = CONFIG_DIR / "settings.json"
    if f.exists():
        s.update(json.loads(f.read_text(encoding="utf-8")))
    # 环境变量覆盖（答辩机数据挪位时用）
    if os.environ.get("LSL_DATA_DIR"):
        s["data_dir"] = os.environ["LSL_DATA_DIR"]
    s["data_dir"] = _abs(s["data_dir"])
    s["coords_csv"] = _abs(s["coords_csv"])
    s["plan_pdf"] = _abs(s["plan_pdf"])
    return s


SETTINGS = load_settings()


def log_path(group: str) -> Path:
    return SETTINGS["data_dir"] / _GROUPS[str(group)]


def summary_path(group: str) -> Path:
    return SETTINGS["data_dir"] / f"summaryreport{group}.csv"


def state_path(group: str) -> Path:
    return SETTINGS["data_dir"] / f"statereport{group}.csv"


def source_mtimes() -> dict:
    """数据源文件的修改时间，用于缓存新鲜度判断。"""
    out = {}
    for g in _GROUPS:
        for p in (log_path(g), summary_path(g), state_path(g), SETTINGS["coords_csv"]):
            if Path(p).exists():
                out[str(p)] = Path(p).stat().st_mtime
    return out
