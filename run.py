"""答辩日一键启动：缓存自检/重建 → 端口探测 → 起 uvicorn → 自动开浏览器。

用法：python run.py（双击 start.bat 等价）；绿包 exe（PyInstaller frozen）同样走这里。
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))


def port_free(p: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", p)) != 0


def main():
    here = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    os.chdir(here)
    from app.settings import SETTINGS
    from app.precompute import main as pre_main

    print("== 线边物流可视化与成本测算 · 本地服务 ==")
    t0 = time.time()
    try:
        pre_main(force=False)          # 缓存缺失/过期时自动重建（pandas 全量 <60s）
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 预计算异常（将以现有缓存启动）：{e}")
    if not os.environ.get("LSL_NO_SIM"):
        try:
            from app.sim.calibrate import main as cal_main
            cal_main(force=False)      # calibration.json 存在即跳过
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 标定跳过：{e}")

    port = SETTINGS["port"]
    while not port_free(port):
        port += 8                      # 冲突时按 +8 递增
    url = f"http://127.0.0.1:{port}/"
    print(f"启动中… 冷启动含预计算约 {max(1, int(time.time() - t0))}s 已过")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    import uvicorn
    if FROZEN:
        # 冻结模式下 import-string 不可用（无源码寻路），直接传 app 对象
        from app.main import app as _app
        uvicorn.run(_app, host=SETTINGS["host"], port=port, log_level="warning")
    else:
        uvicorn.run("app.main:app", host=SETTINGS["host"], port=port, log_level="warning")


if __name__ == "__main__":
    main()
