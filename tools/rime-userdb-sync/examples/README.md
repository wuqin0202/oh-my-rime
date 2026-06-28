# Rime 用户词库同步调度示例

这些示例用于给计划中的 `tools/rime-userdb-sync` CLI 提供桌面平台调度器骨架。
它们刻意保持为模板形式，正式使用前需要由操作者替换为本机实际路径和参数。

## 占位符说明

- `__PYTHON_BIN__` —— Python 3 解释器的绝对路径
- `__REPO_ROOT__` —— 当前仓库检出的绝对路径
- `__INSTALL_ROOT__` —— macOS LaunchAgent 推荐使用的长期安装目录，例如 `~/Library/Application Support/rime-userdb-sync`
- `__CONFIG_PATH__` —— 同步工具 JSON 配置文件的绝对路径
- `__LOG_ROOT__` —— 日志目录，例如 `~/Library/Logs/rime-userdb-sync`
- `__WORKING_DIR__` —— 进程运行时使用的工作目录绝对路径
- `__USER__` —— 在适用场景下用于调度器归属的本地用户名

## 预期命令形态

所有桌面平台示例都会调用同一个 one-shot 单次同步入口：

```text
__PYTHON_BIN__ <cli.py 的绝对路径> sync --config __CONFIG_PATH__
```

如果最终集成时 CLI 入口路径发生变化，请同步调整这里的命令路径。

## 平台说明

### macOS

推荐做法：

1. 先把同步工具和配置复制到用户库目录，不建议让 LaunchAgent 直接执行 Desktop / Documents 下的仓库脚本：

```bash
mkdir -p "$HOME/Library/Application Support/rime-userdb-sync"
mkdir -p "$HOME/Library/Logs/rime-userdb-sync"
cp tools/rime-userdb-sync/*.py "$HOME/Library/Application Support/rime-userdb-sync/"
cp /path/to/config.json "$HOME/Library/Application Support/rime-userdb-sync/config.json"
```

2. 修改复制后的配置文件。macOS LaunchAgent 默认 `PATH` 很短，推荐把 `rclone_binary` 写成绝对路径，例如：

```json
{
  "rclone_binary": "/opt/homebrew/bin/rclone"
}
```

3. 替换 plist 里的占位符。推荐值示例：

```text
__PYTHON_BIN__=/Users/<你>/miniforge3/bin/python3
__INSTALL_ROOT__=/Users/<你>/Library/Application Support/rime-userdb-sync
__CONFIG_PATH__=/Users/<你>/Library/Application Support/rime-userdb-sync/config.json
__LOG_ROOT__=/Users/<你>/Library/Logs/rime-userdb-sync
```

如果你的 `/usr/bin/python3` 可以正常访问 Rime 目录，也可以继续用 `/usr/bin/python3`；如果遇到 `Operation not permitted`，换成一个已有 Desktop / Library 访问权限的 Python，或给该 Python 授权。

4. 把文件复制到：

```text
~/Library/LaunchAgents/
```

例如：

```bash
cp tools/rime-userdb-sync/examples/macos/com.rime-userdb-sync.plist ~/Library/LaunchAgents/
```

5. 再执行加载：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rime-userdb-sync.plist
```

如果需要立即重载，可以先卸载再加载：

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.rime-userdb-sync.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rime-userdb-sync.plist
```

手动触发一次并查看结果：

```bash
launchctl kickstart -k gui/$(id -u)/com.rime-userdb-sync
launchctl print gui/$(id -u)/com.rime-userdb-sync | grep -E 'state =|runs =|last exit code ='
tail -120 "$HOME/Library/Logs/rime-userdb-sync/stdout.log"
tail -120 "$HOME/Library/Logs/rime-userdb-sync/stderr.log"
```

成功的一次 one-shot 任务通常表现为：

```text
state = not running
last exit code = 0
```

说明：

- `~/Library/LaunchAgents` 是当前用户级任务的推荐位置
- `~/Library/Application Support/rime-userdb-sync` 是脚本和配置的推荐长期存放位置
- `~/Library/Logs/rime-userdb-sync` 是日志推荐位置
- 这个方案适合用户登录后自动执行
- 如果 `~/Library/Rime` 是指向 `~/Desktop/...` 的符号链接，LaunchAgent 可能会因为 macOS 隐私权限限制而报 `Operation not permitted`
- 遇到权限错误时，优先避免从 Desktop 仓库路径直接执行脚本；把脚本和配置放到 `~/Library/Application Support/rime-userdb-sync`，并使用有权限的 Python 解释器
- 如果仍然被拦截，需要给对应 Python/终端授予 Full Disk Access，或者把 Rime 目录迁出 Desktop / Documents 等受保护目录

### Linux

当前提供了两个用户级 systemd 文件：

- `rime-userdb-sync.service`
- `rime-userdb-sync.timer`

这两个文件都要放到用户级 systemd 目录，一般是：

```text
~/.config/systemd/user/
```

推荐步骤：

```bash
mkdir -p ~/.config/systemd/user
cp tools/rime-userdb-sync/examples/linux/rime-userdb-sync.service ~/.config/systemd/user/
cp tools/rime-userdb-sync/examples/linux/rime-userdb-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rime-userdb-sync.timer
```

Linux/Fcitx5 注意事项：

- 默认 timer 只在每天 02:00 触发，不设置开机补跑，避免白天输入法使用高峰期
- 如果 `rime_sync_command` 直接写 `rime_dict_manager --sync`，运行中的 Fcitx5 可能持有 `*.userdb/LOCK`，导致 merge 失败
- 推荐把 Linux 配置中的 `rime_sync_command` 指向 `tools/rime-userdb-sync/examples/linux/fcitx5-rime-sync-wrapper.sh` 的绝对路径
- wrapper 会在 merge 前短暂请求 Fcitx5 退出，等待锁释放，merge 完成后自动恢复 Fcitx5

说明：

- `.service` 定义“执行什么命令”
- `.timer` 定义“什么时候执行”
- 如果只复制 `.service`，不会自动定时跑
- 一般启用的是 `.timer`，它会在触发时调用对应的 `.service`

常见检查命令：

```bash
systemctl --user status rime-userdb-sync.timer
systemctl --user list-timers | grep rime-userdb-sync
```

### Windows

当前目录下同时提供了两种 Windows 相关文件：

- `RimeUserdbSync.xml`
- `rime-userdb-sync-task.ps1`

推荐理解：

- `RimeUserdbSync.xml`：任务计划程序导入模板
- `rime-userdb-sync-task.ps1`：被任务调用时可参考/包装的 PowerShell 脚本模板

推荐步骤：

1. 先替换 XML 和 `.ps1` 里的占位符
2. 把 `.ps1` 放到你希望长期保存的位置
3. 在“任务计划程序”里导入 `RimeUserdbSync.xml`

如果你不想导入 XML，也可以手动新建任务，让任务执行类似：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\path\to\rime-userdb-sync-task.ps1"
```

说明：

- XML 更适合“一次导入完整任务定义”
- `.ps1` 更适合后续维护实际执行命令
- 如果只保留 XML、不保留脚本，也可以直接把实际 Python 命令写进 XML，但可维护性通常不如脚本方式

