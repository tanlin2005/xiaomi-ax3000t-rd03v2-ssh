#!/usr/bin/env python3
"""
小米 / 红米路由器出厂默认 SSH (root) 密码计算器
适用机型: AX3000T (RD03), AX6000, AX3200, AX6S, AX9000 等几乎全系列小米/红米路由器

算法说明:
  1. SN 含有 '/' (现代绝大多数机型):
     Salt = '6d2df50a-250f-4a30-a5e6-d44fb0960aa0'
  2. SN 不含 '/' (早期 R1D 等机型):
     Salt = 'A2E371B0-B34B-48A5-8C40-A7133F3B5D88'
  3. password = MD5(SN + Salt)[:8]
"""

import sys
import hashlib

SALT_R1D = "A2E371B0-B34B-48A5-8C40-A7133F3B5D88"
SALT_OTHERS = "-".join(reversed("d44fb0960aa0-a5e6-4a30-250f-6d2df50a".split("-")))


def calc_mi_ssh_pwd(sn: str) -> str:
    """根据小米路由器 SN 码计算默认 root 密码"""
    sn = sn.strip()
    if not sn:
        return ""
    salt = SALT_OTHERS if "/" in sn else SALT_R1D
    return hashlib.md5((sn + salt).encode("utf-8")).hexdigest()[:8]


def main():
    if len(sys.argv) > 1:
        # 命令行参数模式
        sn = sys.argv[1].strip()
        pwd = calc_mi_ssh_pwd(sn)
        print(f"\n[+] S/N: {sn}")
        print(f"[+] 默认 root 密码: {pwd}\n")
        return

    # 交互模式
    print("=" * 48)
    print(" 小米 / 红米路由器 出厂默认 SSH (root) 密码计算器")
    print("=" * 48)
    print("提示: SN (序列号) 可在路由器机身背部标签或后台管理页面查得。\n")

    while True:
        try:
            sn = input("请输入路由器 S/N (输入 q 退出): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出。")
            break

        if not sn:
            continue
        if sn.lower() in ("q", "quit", "exit"):
            break

        pwd = calc_mi_ssh_pwd(sn)
        print("-" * 48)
        print(f"  S/N: {sn}")
        print(f"  出厂 root 密码: {pwd}")
        print("-" * 48 + "\n")


if __name__ == "__main__":
    main()
