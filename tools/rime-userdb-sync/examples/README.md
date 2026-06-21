# Rime 用户词库同步调度示例

这些示例用于给计划中的 `tools/rime-userdb-sync` CLI 提供桌面平台调度器骨架。
它们刻意保持为模板形式，正式使用前需要由操作者替换为本机实际路径和参数。

## 占位符说明

- `__PYTHON_BIN__` —— Python 3 解释器的绝对路径
- `__REPO_ROOT__` —— 当前仓库检出的绝对路径
- `__CONFIG_PATH__` —— 同步工具 JSON 配置文件的绝对路径
- `__WORKING_DIR__` —— 进程运行时使用的工作目录绝对路径
- `__USER__` —— 在适用场景下用于调度器归属的本地用户名

## 预期命令形态

所有桌面平台示例都会调用同一个 one-shot 单次同步入口：

```text
__PYTHON_BIN__ __REPO_ROOT__/tools/rime-userdb-sync/cli.py --config __CONFIG_PATH__ sync
```

如果最终集成时 CLI 入口路径发生变化，请同步调整这里的命令路径。

## 平台说明

### macOS

推荐做法：

1. 先替换 plist 里的占位符
2. 把文件复制到：

```text
~/Library/LaunchAgents/
```

例如：

```bash
cp tools/rime-userdb-sync/examples/macos/com.rime-userdb-sync.plist ~/Library/LaunchAgents/
```

3. 再执行加载：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rime-userdb-sync.plist
```

如果需要立即重载，可以先卸载再加载：

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.rime-userdb-sync.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rime-userdb-sync.plist
```

说明：

- `~/Library/LaunchAgents` 是当前用户级任务的推荐位置
- 这个方案适合用户登录后自动执行
- 如果你不想复制，也可以直接从仓库路径加载，但复制到 `~/Library/LaunchAgents` 更符合 macOS 的常见习惯

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

### Android

Android 按设计不提供调度器示例。

原因不是缺少平台支持，而是这个工具当前明确采用 **半自动模式**：

1. 用户显式发起前台运行
2. 工具执行 validate / pull / dry-run 等前半段动作
3. 用户自己确认本地 merge 已完成
4. 再执行第二步显式 push

也就是说，Android 侧当前不推荐：

- 后台常驻
- 静默定时
- 无感知自动 merge / 自动 push

如果以后你自己的 Android 运行环境具备更强权限（例如可控终端、Tasker、root、可访问目标目录等），可以再基于当前 CLI 自行扩展，但那不属于本仓库当前默认文档范围。
