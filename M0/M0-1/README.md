# M0-1 ｜ 从零搭建开发环境

> 难度 ★ ｜ 考察：Linux 基础 + 包管理 + WSL2 + Git 基础 + 技术写作

## 环境方案（三选一：WSL2）

- Windows 11 + WSL2 + Ubuntu 22.04 LTS (22.04.5) + ROS2 Humble（桌面版）
- 选择理由：原本计划装双系统（性能更好），但安装过程繁琐（BitLocker 解密、磁盘分区、启动盘制作），且学习阶段以仿真为主，先用 WSL 快速上手，后续需要真实硬件时再考虑双系统/物理机

## 环境清单

| 组件 | 状态 |
| :-- | :-- |
| Ubuntu 22.04 (WSL2) | ✅ `lsb_release -a` 验证 |
| ROS2 Humble 桌面版 | ✅ talker/listener 验证节点通信 |
| Python 3.10 + pip | ✅ 系统自带 + `apt install python3-pip` |
| uv 0.12.22 | ✅ `uv venv` 可创建并激活虚拟环境 |
| gcc / g++ / make / cmake | ✅ build-essential |
| VS Code 1.140 + Python / C-C++ / Remote-SSH / Remote-WSL 插件 | ✅ |
| Git（user.name / user.email 已配置） | ✅ |
| SSH ed25519 密钥 | ✅ 已生成 |

## 安装过程

1. 检查并关闭 BitLocker 设备加密，用 `manage-bde -status` 验证两个盘"已完全解密、保护关闭"
2. `wsl --install -d Ubuntu-22.04` 安装 WSL2 与 Ubuntu，重启后完成用户初始化
3. 使用鱼香ROS一键脚本安装 ROS2 Humble（自动换源：清华系统源 + 中科大 ROS 源），并自动写入 `~/.bashrc`
4. `ros2 run demo_nodes_cpp talker` + `ros2 run demo_nodes_py listener` 双终端验证，listener 持续收到 "Hello World" 消息
5. 补装：`python3-pip`、uv、VS Code 及四个插件、SSH 密钥

## 踩坑实录

### 坑 1：在 Windows PowerShell 里跑 ros2 命令

报错原文：`ros2 : 无法将"ros2"项识别为 cmdlet、函数、脚本文件或可运行程序的名称`

定位过程：看到提示符是 `PS C:\...>` 才意识到 ros2 是 Ubuntu 里的命令，Windows 不认识。

解决：先 `wsl -d Ubuntu-22.04` 进入 Ubuntu（提示符变成 `lenovo@xxx:~$`）再执行。

### 坑 2：GitHub 克隆/推送连不上

报错原文：`gnutls_handshake() failed` / 卡在 `Cloning into 'smartcar'...` 不动

定位过程：WSL 提示"检测到 localhost 代理配置"，查资料得知 WSL 默认 NAT 模式下无法直接使用 Windows 上的代理（localhost:7897 指向的是 WSL 自己）。

解决：把 git 代理指向 Windows 宿主机 IP（WSL 里用 `ip route show default` 拿到网关 IP）：

```bash
git config --global http.proxy http://$(ip route show default | awk '{print $3}'):7897
git config --global https.proxy http://$(ip route show default | awk '{print $3}'):7897
```

同时在 Clash Verge 打开"局域网连接"允许局域网设备访问代理。

### 坑 3：VS Code 插件命令行安装超时

报错原文：`connect ETIMEDOUT` / `decryption failed or bad record mac`

定位过程：`code --install-extension xxx` 不走系统代理，直连微软市场国内不稳定。

解决：改用 VS Code 图形界面（Ctrl+Shift+X）安装（GUI 走 Windows 网络，代理生效）；remote-wsl 插件 GUI 只装到 Windows 侧，最终从 marketplace 下载离线 `.vsix` 用 `code --install-extension xxx.vsix` 装入 WSL 侧。

### 坑 4：push 时密码被拒

报错原文：`support for password authentication was removed on August 13, 2021`

解决：GitHub 不再接受账号密码，改用 Personal Access Token（Settings → Developer settings → Tokens (classic)，勾选 repo），配合 `git config --global credential.helper store` 记住凭据。

### 坑 5：空目录没有提交到 GitHub

现象：本地建了 M0/ M1/ 目录，但 GitHub 网页上看不到。

原因：Git 不跟踪空目录。解决：每个目录放 README 占位文件后再提交。

### 其他小坑

- nano 保存是 `Ctrl+O`（字母 O），一开始按成了数字 0
- Markdown 语法：标题要 `#`、列表要 `-`、命令用反引号包裹，符号后要空格
- 压缩卷腾空间后中途改方案，用磁盘管理"扩展卷"把 200GB 还给了 D 盘

## 环境验收

使用题目提供的 `check_env.sh` 自查：**PASS=25 / FAIL=0 / WARN=2**

- 剩余 WARN 1：known_hosts 为空——需要实际 SSH 登录一次远程机器后消除（计划与队友互登完成）
- 剩余 WARN 2：运行脚本时未激活虚拟环境——已验证 `uv venv && source .venv/bin/activate` 可正常创建并激活，做题时使用

## 参考资料

- ROS2 Humble 官方文档（英文）：https://docs.ros.org/en/humble/
- ROS2 Humble 官方文档（中文翻译）：https://fishros.org.cn/
- 鱼香ROS 一键安装脚本及社区：https://fishros.org.cn/forum/
- WSL 官方文档：https://learn.microsoft.com/zh-cn/windows/wsl/
- Ubuntu 22.04 清华镜像：https://mirrors.tuna.tsinghua.edu.cn/ubuntu-releases/22.04/
- VS Code 下载：https://code.visualstudio.com/

## AI 使用说明

- 本题（环境搭建）在 AI 助手指导下完成：方案选择、命令讲解、报错排查均由 AI 协助，所有命令本人亲手执行并验证
- README 由本人撰写，AI 提供了格式建议和结构参考
