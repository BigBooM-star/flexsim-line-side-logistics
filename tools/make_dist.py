"""一键打绿包：PyInstaller onedir + 数据/缓存/配置组装 → dist/线边物流演示端/

用法：python tools/make_dist.py
产物整个文件夹拷到 U 盘即可，目标电脑免安装 Python、免联网、双击「启动演示.bat」运行。

要点：
- onedir（非 onefile）：启动快、杀软友好；cache/config/data 放 exe 同级（可写），
  static 打进 _internal（只读服务）。
- 用 shutil.copy2/copytree 保留 mtime → 收件人机器上缓存比数据新 → 秒开，不触发 60s 重建。
- fitz(PyMuPDF) 排除：plan.svg 已预生成在 static/gen 里随包走。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
NAME = "线边物流演示端"
DIST = REPO / "dist" / NAME
SRC_DATA = REPO / "data"  # 实验数据随仓库走（开源/绿包同一份）


# 本机 user-site 里与软件无关的重包（被 hooks 依赖图误拉），全部剔除；
# 保留 pandas 真正会碰的：pyarrow / dateutil / tzdata / numpy。
EXCLUDES = [
    "fitz", "pymupdf", "tkinter",
    "torch", "torchvision", "torchaudio", "cv2", "opencv_python",
    "transformers", "tokenizers", "safetensors", "hf_xet", "huggingface_hub",
    "onnxruntime", "av", "scipy", "sklearn", "seaborn", "statsmodels",
    "matplotlib", "PIL", "botocore", "boto3", "s3fs", "grpc",
    "cryptography", "psycopg", "psycopg_binary", "psycopg2", "lxml",
    "pythonwin", "websockets", "wsproto", "httptools", "watchfiles",
    "yt_dlp", "mutagen", "secretstorage", "curl_cffi", "keyring",
    "numba", "llvmlite", "IPython", "notebook", "jupyter",
    "imageio", "moviepy", "librosa", "soundfile", "pygame", "pyspark",
]


def run_pyinstaller():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--console",
        "--name", NAME,
        "--specpath", str(REPO / "build"),
        "--distpath", str(REPO / "dist"),
        "--add-data", f"{REPO / 'static'};static",
        "--collect-submodules", "uvicorn",
    ]
    for m in ("anyio", "starlette", "fastapi", "uvicorn", "pydantic", "pandas"):
        cmd += ["--copy-metadata", m]
    for m in EXCLUDES:
        cmd += ["--exclude-module", m]
    cmd.append(str(REPO / "run.py"))
    print("$", " ".join(cmd[:8]), "…")
    subprocess.run(cmd, check=True, cwd=REPO)


def assemble():
    # 1) config：settings.json 全相对路径（相对 exe 目录解析），随包数据自洽
    cfg = DIST / "config"
    cfg.mkdir(exist_ok=True)
    (cfg / "settings.json").write_text(
        '{\n  "data_dir": "data",\n'
        '  "coords_csv": "data/对象坐标表.csv",\n'
        '  "plan_pdf": "data/平面图-模型.pdf",\n'
        '  "host": "127.0.0.1",\n  "port": 8765\n}\n', encoding="utf-8")
    for f in ("cost_basis.json", "presets.json"):
        src = REPO / "config" / f
        if src.exists():
            shutil.copy2(src, cfg / f)

    # 2) cache：预计算产物随包 → 收件人秒开
    shutil.copytree(REPO / "cache", DIST / "cache", dirs_exist_ok=True)

    # 3) data：整目录随包（copytree 默认 copy2 保留 mtime → 缓存判定新鲜，收件人秒开）
    shutil.copytree(SRC_DATA, DIST / "data", dirs_exist_ok=True)
    have = {f.name for f in (DIST / "data").iterdir()}
    need = {"lab1 432000.csv", "lab5.1 432000.csv", "summaryreport4.csv",
            "statereport5.1.csv", "对象坐标表.csv", "平面图-模型.pdf"}
    if not need <= have:
        raise SystemExit(f"[FAIL] data 缺关键文件：{sorted(need - have)}")

    # 4) 启动器 + 使用说明
    (DIST / "启动演示.bat").write_bytes(
        ("@echo off\nchcp 65001 >nul\ncd /d %~dp0\n" + NAME + ".exe\npause\n"
         ).encode("gbk"))
    (DIST / "使用说明.txt").write_text(
        "线边物料配送 · 可视化与成本测算软件（演示端）\r\n"
        "═══════════════════════════════════════════\r\n\r\n"
        "【启动】双击「启动演示.bat」（或 线边物流演示端.exe）。\r\n"
        "  · 无需安装 Python、无需联网；自动打开浏览器，地址见命令行窗口（默认 http://127.0.0.1:8765）。\r\n"
        "  · 首次启动约 3~10 秒（缓存已随包，无需重建）。\r\n\r\n"
        "【整个文件夹拷贝即可】本目录 = 程序 + 数据 + 缓存 + 配置，放 U 盘 / 桌面 / D 盘均可运行；\r\n"
        "  仅要求路径不含只读权限限制（不要直接从 U 盘双击运行时写缓存——若报权限错误，\r\n"
        "  请先把整个文件夹拷到本地硬盘再启动）。\r\n\r\n"
        "【数据更新】把新的 FlexSim 导出文件（lab*.csv / summaryreport*.csv / statereport*.csv）\r\n"
        "  覆盖到 data\\ 目录后重新启动，软件会自动重建缓存（约 1 分钟）。\r\n\r\n"
        "【换电脑端口冲突】无需处理，程序自动 +8 递增，以命令行窗口显示的 URL 为准。\r\n",
        encoding="utf-8")
    size = sum(f.stat().st_size for f in DIST.rglob("*")) / 1e6
    print(f"组装完成：{DIST}\n总体积 {size:.0f} MB")


def verify():
    """组装产物硬性校验——缺一个关键文件就大声失败，绝不出半成品绿包。"""
    need = ["config/settings.json", "config/cost_basis.json", "config/presets.json",
            "cache/kpi_actuals.json", "data/lab1 432000.csv", "data/lab5.1 432000.csv",
            "data/summaryreport4.csv", "data/对象坐标表.csv",
            "线边物流演示端.exe", "_internal/static/index.html", "启动演示.bat"]
    miss = [n for n in need if not (DIST / n).exists()]
    if miss:
        raise SystemExit(f"[FAIL] 产物缺文件：{miss}")
    st = json.loads((DIST / "config/settings.json").read_text(encoding="utf-8"))
    assert st["data_dir"] == "data", "settings 应为相对路径"
    print("verify OK：关键文件全部就位")


def main():
    run_pyinstaller()
    assemble()
    verify()
    print("OK 绿包就绪，整个文件夹拷 U 盘即可。")


if __name__ == "__main__":
    main()
