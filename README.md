# 小米 AX3000T 高通版 (RD03v2) 原厂固件 SSH 永久解锁与撤销工具箱

<p align="center">
  <b>针对小米路由器 AX3000T 高通芯片版（RD03v2）定制开发的原厂固件免拆机 Root / 开启 SSH 及持久化管理利器</b><br>
  <sub>全面适配 Windows 11 / Windows 10 · 纯标准库 0 外部依赖 · 单文件全闭环 · 原厂双模固化 · 完全可逆还原</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Hardware-RD03v2%20(Qualcomm%20IPQ5018)-blue?style=flat-square" alt="Hardware">
  <img src="https://img.shields.io/badge/Firmware-MiWiFi%202.0.12%20%7C%202.0.28-brightgreen?style=flat-square" alt="Firmware">
  <img src="https://img.shields.io/badge/Platform-Windows%2011%20%7C%20Windows%2010-informational?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/Dependencies-Python%20Standard%20Library%20Only-orange?style=flat-square" alt="Dependencies">
  <img src="https://img.shields.io/badge/License-GPL--2.0-lightgrey?style=flat-square" alt="License">
</p>

---

## 🌟 项目亮点与核心优势

不同于市面上常见的联发科版刷机教程或繁重的 Linux 虚拟机方案，本项目针对**高通芯片新版 AX3000T** 进行了全链路重构，具备以下特点：

- ⚡ **零第三方依赖 (Pure Python)**  
  全脚本严格采用 Python 3 原生标准库，**无需执行 `pip install` 安装任何依赖包**，环境纯净开箱即用。
- 📦 **单文件自包含 (Self-contained)**  
  Mesh 认证握手、凭据提取、漏洞注入与临时 HTTP 载荷托管**全闭环内置在单文件脚本中**，无需外部源码仓库。
- 🛡️ **免拆机、不伤保修 (No UART / Solderless)**  
  利用原厂底层协议漏洞空中提权，**无需螺丝刀拆壳，无需焊接串口排针**，不破坏硬件与售后保修。
- 🔄 **双向可逆、无痕还原 (Bidirectional & Clean Revert)**  
  不仅支持开启并永久固化 SSH，还提供一键完整撤销功能，擦除自启与持久化文件，锁定 root 密码无痕恢复出厂状态。
- 📶 **路由 / 中继双模深度兼容 (Dual-mode Adaptation)**  
  针对小米系统切换“中继模式 (AP / 桥接)”时重写防火墙的痛点，采用**“防火墙挂载 + Cron 巡视互锁自愈”**机制，无论当主路由还是 AP，SSH 均稳固常驻。
- 🪟 **全面适配 Windows 11 与 Windows 10**  
  提供原生 PowerShell（`.ps1`）与传统批处理（`.bat`）双入口，透明告知 UAC 提权用途，自动放行并清理临时入站规则，彻底解决网络拦截痛点。

---

## 🛠️ 文件结构

```text
xiaomi-ax3000t-rd03v2-ssh/
├── 一键开启SSH与固化.ps1  # Windows 11 / 10 PowerShell 原生入口 (推荐，无字符集乱码，支持管理员自提)
├── 一键开启SSH与固化.bat  # Windows 11 / 10 传统 CMD 双击入口 (带 UTF-8 BOM 修复)
├── unlock_ax3000t.py      # 核心 Python 脚本 (全功能工具箱：解锁、固化、撤销与还原)
├── calc_sn_pwd.py         # 路由器出厂默认 root 密码计算工具 (输入 SN 即可算出默认密码)
└── README.md              # 项目详细说明文档
```

---

## 📋 适用机型与运行环境

| 维度 | 适用范围说明 |
| :--- | :--- |
| **设备型号** | 小米路由器 AX3000T (**高通版 / V3 / RD03v2**)<br>*(机身标签标注型号通常为 RD03 或 RD03v2)* |
| **硬件架构** | CPU: **Qualcomm IPQ5018** (集成 2.4G Wi-Fi 6) + 5G: **QCN6122** + 交换机: **AN8855** |
| **验证固件** | MiWiFi 官方稳定版 **`2.0.12`**、**`2.0.28`** *(出厂默认固件即在此区间)* |
| **操作端系统** | **Windows 11** (所有版本) / **Windows 10** (1809 及以上版本推荐，系统自带 OpenSSH)<br>*(Linux / macOS 平台亦可直接以终端命令运行 `python3 unlock_ax3000t.py`)* |
| **Python 版本** | **Python 3.8 ~ 3.12+** (仅依赖系统原生标准库，无需安装任何 pip 第三方模块) |
| **冲突警示** | 早期联发科芯片版 (MT7981B) 硬件架构完全不同，请使用原版已成熟的 openwrt / xmir-patcher 方案，**切勿将本工具混用！** |

---

## 🚀 Windows 11 / 10 极速使用指南

### 第一步：准备工作
1. 确保电脑已安装 Python 3（可打开 Win11 / Win10 微软应用商店 Microsoft Store 搜索并一键安装 `Python 3.11` 或 `3.12`）。
2. 将 AX3000T 恢复出厂设置（路由器通电开机后，**长按背部 Reset 键约 8 秒**至指示灯变为黄色闪烁后松开）。
3. 路由器重启完成后，**切勿打开浏览器做任何配置向导**，保持出厂未配置状态。
4. 使用网线将电脑网口与路由器的**任意网口直连**。

### 第二步：运行一键工具
在 Win11 / Win10 下支持两种运行方式（任选其一，推荐 **PowerShell** 原生运行）：

- **方式 A（强烈推荐，针对 PowerShell 终端）：**
  在终端中输入：
  ```powershell
  .\一键开启SSH与固化.ps1
  ```
  *(注：如果首次运行提示脚本受限，输入 `Set-ExecutionPolicy -Scope Process Bypass` 即可)*
- **方式 B（传统双击运行）：**
  直接双击 **`一键开启SSH与固化.bat`** 启动。

1. **授权确认**：批处理会展示清晰的权限说明，直接按回车调起 Windows 授权弹窗（点击【是】以自动放行临时通信端口）。
2. **功能菜单**：
   ```text
   ====================================================================
         小米 AX3000T 高通版 (RD03v2) 原厂固件 SSH 管理工具箱
            (纯 Python 原生标准库实现 · 免装模块 · 免克隆代码)
   ====================================================================
   [*] 识别到网卡 IP: 192.168.31.xxx
   [*] 目标路由器默认 IP: 192.168.31.1

   请选择您要执行的操作：
     [1] 开启 SSH 并永久固化 (获取 Root 权限，自动双模适配常驻)
     [2] 撤销 Root 权限并彻底关闭 SSH (清理固化与自启，无痕恢复出厂)
   ```
3. **根据向导执行**：
   - **选择 `1` (开启并固化)**：
     - **运行前提**：路由器刚恢复出厂设置且未走网页向导时使用；
     - 自定义输入您想设置的 root 密码（直接按回车默认使用 `admin`）；
     - 脚本全自动完成 Mesh 初始化、凭据抓取、载荷投递与底层固化。
   - **选择 `2` (撤销与恢复)**：
     - **运行前提**：路由器正常开机联网运行中，电脑连入其网络即可（无需恢复出厂）；
     - **IP 支持**：提示输入路由器当前 IP（普通路由模式直接回车默认 `192.168.31.1`；中继模式输入主路由分配给它的新 IP）；
     - 输入 `YES` 确认后，系统调起 SSH 客户端验证密码并下发清理指令，一键清空 `/data/auto_ssh`、还原 NVRAM 与防火墙自启，并锁定 root 密码无痕恢复出厂。

### 第三步：验证与后续配置
* **WiFi 临时密码**：提权完成后，路由器 WiFi 临时连接密码为 **`meshpoc12345`**。
* **修改 WiFi 与管理密码**：打开浏览器访问 `http://192.168.31.1`：
  - 若提示全新向导：直接按照向导设置您自己的宽带、WiFi 与私人管理员密码；
  - 若显示密码登录页：说明处于初始化过渡态，输入密码 `admin` 即可登入后台完成后续设置；
  - *(后台已固化的 Root / SSH 权限永久常驻，不受网页修改任何影响)*
* **登录 SSH**：打开系统终端（PowerShell 或 CMD），随时畅享 Root 权限：
  ```powershell
  ssh root@192.168.31.1
  # 密码输入你在脚本中设置的密码 (默认: admin)
  ```

---

## 📌 致谢与引用说明 (Credits & References)

本项目基于开源安全社区与多位安全研究员对小米路由器固件的研究成果整理并重构实现，在此对相关开源项目及作者表示由衷感谢：

1. **漏洞披露与 PoC 原始来源**：
   - 漏洞披露仓库：[ADCDS/xiaomi-ax3000t-cabmeshd-disclosure](https://github.com/ADCDS/xiaomi-ax3000t-cabmeshd-disclosure)
   - 核心机制基于安全研究团队披露的 Xiaomi AX3000T (RD03v2) `/usr/sbin/cab_meshd` 守护进程硬编码密钥认证缺陷 (V1) 以及 `mimesh_init.sh` 中的未授权 root 命令注入漏洞 (V2)。

2. **自动化安装器与相关工具**：
   - [ADCDS/xiaomi-openwrt-install](https://github.com/ADCDS/xiaomi-openwrt-install)：官方固件环境探测与自动化工具链。
   - [ADCDS/openwrt-xiaomi-ax3000t-rd03v2](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2)：高通版 AX3000T 的 OpenWrt 适配及硬件外设支持。

3. **小米路由器持久化方案与社区实践**：
   - 借鉴了社区（[lemoeo/AX6S](https://github.com/lemoeo/AX6S)、恩山无线论坛等）在小米/红米 Wi-Fi 6 系列路由器上关于 `/data/auto_ssh` 与 UCI 防火墙持久化挂载的成熟方案。

---

## ⚠️ 免责声明

本工具仅供网络设备所有者在自有设备上进行个人技术学习、研究与网络管理测试使用。使用前请仔细阅读相关说明，操作过程中请保持供电稳定。因不当操作或固件版本差异造成的任何潜在风险由使用者自行承担。
