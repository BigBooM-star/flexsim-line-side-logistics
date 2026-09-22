"""misc 路由：/api/health、/api/meta。"""
import time
from pathlib import Path

from fastapi import APIRouter

from ..settings import SETTINGS, source_mtimes
from .cacheio import cache, cache_ready

router = APIRouter(tags=["misc"])


@router.get("/api/health")
def health():
    ok = cache_ready()
    warn = []
    if ok:
        k = cache("kpi_actuals.json")
        src = source_mtimes()
        # 按文件名对齐（绿包打包后绝对路径会变，文件名唯一且 mtime 随 copy2 保留）
        gen = {Path(p).name: mt for p, mt in k["meta"].get("source_mtime", {}).items()}
        stale = [p for p, mt in src.items()
                 if gen.get(Path(p).name) is None or mt > gen[Path(p).name]]
        if stale:
            warn.append(f"{len(stale)} 个数据文件比缓存新，建议重跑预计算")
    else:
        warn.append("缓存缺失：运行 python -m app.precompute")
    missing = [str(SETTINGS[k]) for k in ("data_dir", "coords_csv", "plan_pdf")
               if not SETTINGS[k].exists()]
    return {"status": "ok" if ok else "cache_missing", "cache_ready": ok,
            "warnings": warn + ([f"数据路径缺失: {m}" for m in missing] if missing else []),
            "server_time": time.strftime("%F %T")}


@router.get("/api/meta")
def meta():
    if not cache_ready():
        return {"ready": False}
    k = cache("kpi_actuals.json")
    return {"ready": True, "labels": k["meta"]["labels"], "window": k["meta"]["window"],
            "surge_windows": k["meta"]["surge_windows"],
            "generated": k["meta"].get("generated")}
