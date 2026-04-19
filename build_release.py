#!/usr/bin/env python3
"""Build a Self Manager release zip.

Usage:
    python build_release.py [--version OVERRIDE_VERSION]
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

INCLUDE_FILES = [
    "version.py",
    "main.py",
    "service.py",
    "logger_config.py",
    "requirements.txt",
    "LICENSE",
]

INCLUDE_DIRS = [
    "api",
    "services",
    "frontend",
]

IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc")


def read_version() -> str:
    content = (ROOT / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise RuntimeError("Cannot find __version__ in version.py")
    return match.group(1)


def build_startup_bat(version: str) -> str:
    return f"""@echo off
chcp 65001 >nul 2>&1
title Self Manager v{version}

echo ========================================
echo   Self Manager v{version}
echo   个人能效管理系统
echo ========================================
echo.

REM Check Python availability
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请安装 Python 3.11+ 并添加到 PATH。
    echo 下载地址: https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

REM Create virtual environment if it does not exist
if not exist ".venv\\Scripts\\python.exe" (
    echo [SETUP] 正在创建虚拟环境...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] 创建虚拟环境失败。
        pause
        exit /b 1
    )
    echo [SETUP] 虚拟环境创建成功。
)

REM Install dependencies if needed
if not exist ".venv\\Lib\\site-packages\\fastapi" (
    echo [SETUP] 正在安装依赖...
    .venv\\Scripts\\pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] 依赖安装失败，请检查网络连接。
        pause
        exit /b 1
    )
    echo [SETUP] 依赖安装完成。
)

echo.
echo [START] 启动 Self Manager...
echo         访问 http://127.0.0.1:8000
echo         按 Ctrl+C 停止服务器
echo.

start http://127.0.0.1:8000
.venv\\Scripts\\python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
"""


def build_readme_md(version: str) -> str:
    return f"""# Self Manager v{version}

个人能效管理系统：任务管理、习惯打卡、番茄钟、个人周报。

## 系统要求

- Windows 10 或更高版本
- Python 3.11 或更高版本
  - 下载地址: https://www.python.org/downloads/
  - 安装时请勾选 **"Add Python to PATH"**

## 快速开始

1. 将此压缩包解压到任意目录（例如 `D:\\self-manager`）
2. 双击 `startup.bat`
3. 首次运行会自动创建虚拟环境并安装依赖（需要联网）
4. 浏览器自动打开 http://127.0.0.1:8000
5. 注册新账号，开始使用

## 启动脚本说明

`startup.bat` 会在首次运行时自动完成以下操作：

- 创建 `.venv` 虚拟环境（隔离依赖，不污染系统 Python）
- 安装所需的 Python 依赖包
- 启动 Web 服务器

之后每次启动会跳过安装步骤，直接启动服务器。

## 数据存储

所有数据存储在当前目录下的 `productivity_manager.db`（SQLite 文件）。
备份数据只需复制此文件。

## 停止服务器

在命令行窗口中按 `Ctrl+C`，然后关闭窗口。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| SELF_MANAGER_DB_PATH | SQLite 数据库文件路径 | productivity_manager.db |

## 许可证

Apache License 2.0 — 详见 LICENSE 文件。
"""


def build(version: str) -> Path:
    staging = DIST / f"self-manager-{version}"
    zip_path = DIST / f"self-manager-{version}.zip"

    # Clean previous builds
    if staging.exists():
        shutil.rmtree(staging)
    if zip_path.exists():
        zip_path.unlink()

    staging.mkdir(parents=True, exist_ok=True)

    # Copy individual files
    for fname in INCLUDE_FILES:
        src = ROOT / fname
        if not src.exists():
            raise FileNotFoundError(f"Missing required file: {fname}")
        shutil.copy2(src, staging / fname)

    # Copy directories (excluding __pycache__)
    for dname in INCLUDE_DIRS:
        src = ROOT / dname
        if not src.exists():
            raise FileNotFoundError(f"Missing required directory: {dname}")
        shutil.copytree(src, staging / dname, ignore=IGNORE_PATTERNS)

    # Generate startup.bat
    (staging / "startup.bat").write_text(
        build_startup_bat(version), encoding="utf-8"
    )

    # Generate README.md
    (staging / "README.md").write_text(
        build_readme_md(version), encoding="utf-8"
    )

    # Create zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(staging.rglob("*")):
            if file_path.is_file():
                arcname = f"self-manager-{version}/{file_path.relative_to(staging)}"
                zf.write(file_path, arcname)

    # Remove staging directory
    shutil.rmtree(staging)

    return zip_path


def main() -> None:
    version = read_version()

    # Allow version override via CLI
    if "--version" in sys.argv:
        idx = sys.argv.index("--version")
        if idx + 1 < len(sys.argv):
            version = sys.argv[idx + 1]

    print(f"Building Self Manager v{version}...")
    zip_path = build(version)

    size_kb = zip_path.stat().st_size / 1024
    print(f"Created: {zip_path}")
    print(f"Size: {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
