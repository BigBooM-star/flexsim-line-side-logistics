"""缓存 JSON 的统一读取（带 mtime 失效，热改口径即时生效）。"""
import json
import threading
from pathlib import Path

from ..settings import CACHE_DIR, CONFIG_DIR

_LOCK = threading.Lock()
_MEM: dict = {}


def _load(path: Path):
    key = str(path)
    mt = path.stat().st_mtime
    with _LOCK:
        hit = _MEM.get(key)
        if hit and hit[0] == mt:
            return hit[1]
        obj = json.loads(path.read_text(encoding="utf-8"))
        _MEM[key] = (mt, obj)
        return obj


def cache(name: str):
    p = CACHE_DIR / name
    if not p.exists():
        raise FileNotFoundError(f"缓存缺失 {name}，请先运行 python -m app.precompute")
    return _load(p)


def config(name: str):
    return _load(CONFIG_DIR / name)


def cache_ready() -> bool:
    need = ["kpi_actuals.json", "layout.json", "distances.json"] + \
           [f"replay_g{i}.json" for i in (1, 2, 3, 4)]
    return all((CACHE_DIR / n).exists() for n in need)
