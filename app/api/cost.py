"""成本口径路由：/api/cost GET/PUT（原子写盘）+ /api/cost/presets。"""
import json
import os
import tempfile

from fastapi import APIRouter, HTTPException

from ..core.schemas import CostBasisPut
from ..settings import CONFIG_DIR
from .cacheio import config

router = APIRouter(tags=["cost"])

_PATH = CONFIG_DIR / "cost_basis.json"
_PRESETS = CONFIG_DIR / "presets.json"


@router.get("/api/cost")
def get_cost():
    return {"active": config("cost_basis.json"),
            "presets": config("presets.json")}


@router.put("/api/cost")
def put_cost(body: CostBasisPut):
    data = body.model_dump()
    data["version"] = int(json.loads(_PATH.read_text(encoding="utf-8")).get("version", 1)) + 1
    _atomic_write(_PATH, data)
    return {"ok": True, "active": data}


@router.post("/api/cost/preset/{name}")
def use_preset(name: str):
    presets = config("presets.json")
    if name not in presets:
        raise HTTPException(404, f"预设 {name} 不存在")
    data = dict(presets[name])
    data["version"] = int(json.loads(_PATH.read_text(encoding="utf-8")).get("version", 1)) + 1
    _atomic_write(_PATH, data)
    return {"ok": True, "active": data}


def _atomic_write(path, obj):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
