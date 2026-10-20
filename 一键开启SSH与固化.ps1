# -*- coding: utf-8 -*-
# 小米 AX3000T (RD03v2) 一键 SSH 解锁入口

Param()

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Set-Location -Path $PSScriptRoot

# 检查是否为管理员身份
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Clear-Host
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "               【安全提示与权限申请说明】" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "本脚本即将请求 Windows 管理员权限 (UAC 盾牌弹窗)。"
    Write-Host ""
    Write-Host "★ 提权用途公开说明（请放心授权）：" -ForegroundColor Yellow
    Write-Host "  1. 本脚本绝不会修改任何系统核心文件或注册表。"
    Write-Host "  2. 申请权限【仅且只用于】在 Win11 本地防火墙临时放行 8123 端口，"
    Write-Host "     确保路由器在出厂未联网状态下，能顺畅连接本机完成脚本传输。"
    Write-Host "  3. 解锁完成后，脚本会自动注销并删除该规则，不留任何安全残留。"
    Write-Host ""
    Write-Host "★ 您可以自主选择：" -ForegroundColor Yellow
    Write-Host "  - 直接按回车：弹出授权窗口，点击【是】（推荐，全自动免配置）"
    Write-Host "  - 输入 N 回车：不给管理员权限，以普通权限继续（需手动点击防火墙允许）"
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    
    $choice = Read-Host "请选择 [按回车继续授权 / 输入 N 放弃]"
    if ($choice -ne "N" -and $choice -ne "n") {
        Write-Host "`n正在调起 Windows 授权弹窗，请在随后的窗口中点击【是】..." -ForegroundColor Green
        Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
        exit
    }
}

Clear-Host
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   小米 AX3000T 高通版 (RD03v2) 原厂固件 SSH 永久解锁工具" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$ruleAdded = $false
if ($isAdmin) {
    Write-Host "[安全保护] 已获得管理员授权，正在临时配置防火墙放行规则 (端口 8123)..." -ForegroundColor Green
    netsh advfirewall firewall delete rule name="AX3000T_Unlock_Port" >$null 2>&1
    netsh advfirewall firewall add rule name="AX3000T_Unlock_Port" dir=in action=allow protocol=TCP localport=8123 >$null 2>&1
    Write-Host "[安全保护] 端口临时规则配置完毕，运行结束后将自动清理。" -ForegroundColor Green
    $ruleAdded = $true
} else {
    Write-Host "[运行模式] 当前以普通用户权限运行。" -ForegroundColor Yellow
    Write-Host "【重要提示】若运行中弹出 `"Windows 安全警报`"：" -ForegroundColor Yellow
    Write-Host "务必【勾选公用网络】并点击【允许访问】，否则路由器无法下载固化脚本！" -ForegroundColor Yellow
}

Write-Host "`n正在检查 Python 运行环境..."
$pyCheck = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCheck) {
    Write-Host "`n[错误] 未检测到 Python 运行环境！" -ForegroundColor Red
    Write-Host "请打开 Win11 微软应用商店 (Microsoft Store) 搜索并安装 `"Python 3.11`" 或 `"3.12`"。"
    Write-Host "安装完成后重新运行本脚本即可。`n"
    Read-Host "按回车键退出..."
    exit
}

Write-Host "Python 环境就绪，正在启动解锁向导...`n" -ForegroundColor Green

# 运行主程序
python unlock_ax3000t.py

# 清理防火墙临时规则
if ($ruleAdded) {
    Write-Host "`n[安全保护] 正在清理临时防火墙规则..." -ForegroundColor Green
    netsh advfirewall firewall delete rule name="AX3000T_Unlock_Port" >$null 2>&1
    Write-Host "[安全保护] 临时规则清理完成，系统网络已恢复原状。" -ForegroundColor Green
}

Write-Host ""
Read-Host "全部操作已结束，按回车键退出..."
