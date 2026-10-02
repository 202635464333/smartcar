# smartcar

华工智能车队一轮考核仓库。


## 环境搭建
- Windows 11 + WSL2 + Ubuntu 22.04 LTS + ROS2 Humble（桌面版）
- 原本想直接装双系统，性能更好，结果安装过程实在过于繁琐，且后续使用过程比较苛刻，便先使用 WSL 学习，后续需要真实硬件时再考虑双系统

## 安装过程

1. 检查并关闭 BitLocker 设备加密，用 `manage-bde -status` 验证完全解密
2. `wsl --install -d Ubuntu-22.04` 安装 WSL 与 Ubuntu，重启后完成用户初始化
3. 使用鱼香ROS一键脚本安装 ROS2 Humble（自动换源：清华系统源 + 中科大 ROS 源）
4. talker/listener demo 验证节点通信正常

## 踩坑记录

- 一开始在 Windows PowerShell 里跑 `ros2` 命令报错——后来明白 WSL 的 Ubuntu 命令必须先进 Ubuntu 环境（`wsl -d Ubuntu-22.04`）再执行
-上传记录到GitHub时不能直接输入，有一定的格式要求
## AI 使用说明

- 环境安装和报错排查在 AI 助手指导下完成，并将某些指令保存至记事本。

- [ ] M0-1 环境搭建（进行中）

## M0-1 环境验收

使用题目提供的 check_env.sh 自查，结果 PASS=25 / FAIL=0 / WARN=2。
- 补装：python3-pip、uv 0.12.22、VS Code 1.140 + Python/C-C++/Remote-SSH/Remote-WSL 插件、SSH ed25519 密钥
- 踩坑：VS Code 插件命令行安装不走代理频繁超时，改用图形界面安装解决；remote-wsl 插件离线 vsix 手动安装到 WSL 侧
- 剩余 WARN：known_hosts 为空（待与队友互登或连开发板后消除）、虚拟环境未激活（M0-4 做题时用 uv venv 激活）
