@echo off
chcp 65001 >nul
echo ========================================
echo   BSMS 项目跟踪看板 - 启动脚本
echo ========================================
echo.

:: 检查依赖
python -c "import fastapi, uvicorn, jinja2" 2>nul
if %errorlevel% neq 0 (
    echo [1/2] 安装 Python 依赖...
    pip install fastapi uvicorn jinja2 -q
) else (
    echo [1/2] 依赖已就绪
)

:: 检查数据库
if not exist "web\bsms.db" (
    echo [2/3] 生成数据库（首次需要，约 60 秒）...
    python scripts\export_to_sqlite.py
) else (
    echo [2/3] 数据库已存在
)

echo [3/3] 启动 Web 服务...
echo.
echo 访问地址：
echo   本机:  http://localhost:8000
echo   内网:  http://192.168.210.101:8000
echo.
echo 按 Ctrl+C 停止服务
echo ========================================
python web\main.py
