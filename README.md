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
