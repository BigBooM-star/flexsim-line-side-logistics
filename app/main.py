"""FastAPI 装配：API 路由 + 静态前端 + 启动钩子（缓存自检）。

开发运行：python -m uvicorn app.main:app --reload --port 8765
答辩运行：双击 start.bat → python run.py
"""
import mimetypes

# Windows 注册表可能把 .js 映射成 text/plain → ES module 会被浏览器拒绝，显式钉死
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .api import cost, dashboard, estimate, export, misc, replay
from .settings import STATIC_DIR


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """缓存缺失时自动预计算（答辩机挪了数据目录也能直接演示）。"""
    from .api.cacheio import cache_ready
    if not cache_ready():
        import threading
        from .precompute import main as pre_main

        def _go():
            try:
                pre_main(force=False)
            except Exception as e:  # noqa: BLE001
                print(f"[warn] 自动预计算失败（演示页将提示缓存缺失）: {e}")

        threading.Thread(target=_go, daemon=True).start()
    yield


app = FastAPI(title="线边物流可视化与成本测算", version="0.1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.include_router(misc.router)
app.include_router(dashboard.router)
app.include_router(replay.router)
app.include_router(estimate.router)
app.include_router(cost.router)
app.include_router(export.router)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

