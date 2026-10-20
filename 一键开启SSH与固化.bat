<# : batch script
@echo off
setlocal
cd /d "%~dp0"

:: 检查是否具备管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ======================================================================
    echo                【安全提示与权限申请说明】
    echo ======================================================================
    echo.
    echo 本脚本即将请求 Windows 管理员权限 (UAC 盾牌弹窗)。
    echo.
    echo ★ 提权用途公开说明（请放心授权）：
    echo   1. 本脚本绝不会修改任何系统核心文件或注册表。
    echo   2. 申请权限【仅且只用于】在 Win11 本地防火墙临时放行 8123 端口，
    echo      确保路由器在出厂未联网状态下，能顺畅连接本机完成脚本传输。
    echo   3. 解锁完成后，脚本会自动注销并删除该规则，不留任何安全残留。
    echo.
    echo ★ 您可以自主选择：
    echo   - 直接按回车：弹出授权窗口，点击【是】（推荐，全自动免配置）
    echo   - 输入 N 回车：不给管理员权限，以普通权限继续（需手动点击防火墙允许）
    echo.
    echo ======================================================================
    set "user_choice="
    set /p "user_choice=请选择 [按回车继续授权 / 输入 N 放弃]: "
    if /i "%user_choice%"=="N" goto :run_normal
    
    echo.
    echo 正在调起 Windows 授权弹窗，请在随后的窗口中点击【是】...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd.exe -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:run_normal
cls
echo ======================================================================
echo   小米 AX3000T 高通版 (RD03v2) 原厂固件 SSH 永久解锁工具
echo ======================================================================
echo.

:: 检查管理员权限状态并配置防火墙
net session >nul 2>&1
if %errorlevel%==0 (
    echo [安全保护] 已获得管理员授权，正在临时配置防火墙放行规则 (端口 8123)...
    netsh advfirewall firewall delete rule name="AX3000T_Unlock_Port" >nul 2>&1
    netsh advfirewall firewall add rule name="AX3000T_Unlock_Port" dir=in action=allow protocol=TCP localport=8123 >nul 2>&1
    echo [安全保护] 端口临时规则配置完毕，运行结束后将自动清理。
)
if %errorlevel% neq 0 (
    echo [运行模式] 当前以普通用户权限运行。
    echo 【重要提示】若运行中弹出 "Windows 安全警报"：
    echo 务必【勾选公用网络】并点击【允许访问】，否则路由器无法下载固化脚本！
)

echo.
echo 正在检查 Python 运行环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [错误] 未检测到 Python 运行环境！
    echo 请打开 Win11 微软应用商店 (Microsoft Store) 搜索并安装 "Python 3.11" 或 "3.12"。
    echo 安装完成后重新运行本脚本即可。
    echo.
    pause
    exit /b
)

echo Python 环境就绪，正在启动解锁向导...
echo.
python unlock_ax3000t.py
echo.

:: 运行完毕后清理临时防火墙规则
net session >nul 2>&1
if %errorlevel%==0 (
    echo [安全保护] 正在清理临时防火墙规则...
    netsh advfirewall firewall delete rule name="AX3000T_Unlock_Port" >nul 2>&1
    echo [安全保护] 临时规则清理完成，系统网络已恢复原状。
)

pause
#>
