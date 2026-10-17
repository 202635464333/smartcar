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
6. 安装 `openssh-server` 并完成 SSH 免密登录（`ssh localhost` 不再询问密码），详见下方「坑 6 / 坑 7」与「远端登录验证实录」

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

### 坑 6：装完 openssh-server 却连不上

安装完 `openssh-server` 直接 `ssh localhost` 会被拒绝，因为 **WSL 里安装不会自动拉起常驻服务**，这一点和物理机不同。

定位方法两条命令：

```
pgrep -x sshd                 # 无输出 = 服务没起来
ss -lntp | grep :22           # 无输出 = 22 端口没人监听
```

解决：`sudo service ssh start` 手动启动。本次安装过程中由 `sshd.socket` 自动拉起了监听进程，`ss` 已能看到 `0.0.0.0:22` 处于 LISTEN 状态。

顺带记一句安装器打印的 `rescue-ssh.target is a disabled or a static unit` —— 它**不是报错**，只是说明 WSL 不用这个 rescue target 来管 ssh，忽略即可。

### 坑 7：`ssh-keygen` 提示 Overwrite —— 差点把 GitHub 的钥匙作废

执行 `ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519` 时出现：

```
/home/lenovo/.ssh/id_ed25519 already exists.
Overwrite (y/n)?
```

**必须选 `n`。** 这把密钥的公钥此前已经添加到 GitHub 账号里，本仓库的全部推送都靠它完成；一旦覆盖重新生成，远端存的是旧公钥，`git push` 会直接被拒（报 `Permission denied (publickey)`）。

正确做法：密钥已存在就**跳过这一步**，直接 `ssh-copy-id` 把现有公钥分发给目标主机。一把私钥可以同时用于 GitHub 登录和 SSH 远程登录，互不影响 ——这就是公钥密码学的设计目的。

## 远端登录验证实录

以下为本机实测（用 localhost 当"远端"，完整验证 ssh / scp / rsync 三条链路）：

```
$ ssh localhost 'echo 免密登录成功; whoami; hostname'
免密登录成功
lenovo
LAPTOP-1BV9TIK6

$ scp ~/smartcar/M0/M0-1/README.md localhost:/tmp/m01_readme.md
README.md                    100% 5052     3.3MB/s   00:00

$ rsync -av ~/smartcar/M0/M0-1/ localhost:/tmp/m01_test/
sending incremental file list
sent 81 bytes  received 12 bytes  186.00 bytes/sec
total size is 5,052  speedup is 54.32

$ ssh localhost 'ls -la /tmp/m01_readme.md /tmp/m01_test/'
-rw-r--r-- 1 lenovo lenovo 5052 Oct 17 21:48 /tmp/m01_readme.md
-rw-r--r-- 1 lenovo lenovo 5052 Oct  2 20:54 /tmp/m01_test/README.md
```

三条链路全程**未询问密码**，退出码均为 0。

**权限核对**（这一项错了，sshd 会拒绝使用公钥，回退到密码登录甚至直接拒绝）：

```
$ stat -c "%a %n" ~/.ssh ~/.ssh/authorized_keys
700 /home/lenovo/.ssh
600 /home/lenovo/.ssh/authorized_keys
```

`700` 表示只有本人能进入该目录，`600` 表示只有本人能读写这个密钥列表 —— 两者都符合 sshd 的硬性要求。

**三个容易误判的现象：**

- `ssh localhost '命令'` 执行完**立刻断开**回到本地提示符，这**不是异常**。SSH 的正常行为就是远程命令跑完会话即结束；要维持交互连接就去掉后面的命令，或加 `-t` 参数。
- 首次连接询问 `Are you sure you want to continue connecting (yes/no)?`，要打完整的 **`yes`**（不是缩写 `y`），主机指纹才会写进 `~/.ssh/known_hosts` —— 这也是 `check_env.sh` 的一个检查点。
- 输入密码时屏幕上**什么都不显示**，这是终端的安全设计，不是键盘坏了，照常打完回车即可。

补充：`ssh-copy-id` 的作用是把**公钥**追加进目标主机的 `~/.ssh/authorized_keys`；私钥 `id_ed25519` 从头到尾没有离开本机，所以即使目标被别人拿到也安全。

### 其他小坑

- nano 保存是 `Ctrl+O`（字母 O），一开始按成了数字 0
- Markdown 语法：标题要 `#`、列表要 `-`、命令用反引号包裹，符号后要空格
- 压缩卷腾空间后中途改方案，用磁盘管理"扩展卷"把 200GB 还给了 D 盘

## 环境验收

使用题目提供的 `check_env.sh` 自查：**PASS=31 / FAIL=0 / WARN=1**（在 `~/smartcar` 目录下、交互式终端中运行）

- 已消除的 WARN：`known_hosts` 为空 —— 完成 ssh / scp / rsync 三条链路实测后，该文件已有 4 条记录，此项转为 PASS（见上方「远端登录验证实录」）
- 剩余 WARN 1：运行脚本时未激活虚拟环境 —— 激活后即消除（`source .venv/bin/activate`，激活后脚本打印 `[PASS] 当前处于虚拟环境: ...`）

> 坑：`uv` 装在 `~/.local/bin/uv`，只有**登录/交互式 shell** 才会把它加进 `PATH`。用 `bash -c` 这类非交互方式运行 `check_env.sh` 会因找不到 `uv` 而误报一条 FAIL（实测非交互跑为 PASS=30/FAIL=1）。现场在终端里直接运行不会出现。

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
