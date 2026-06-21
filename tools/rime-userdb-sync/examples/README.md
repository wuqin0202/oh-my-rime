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

- macOS：使用 `launchctl bootstrap gui/$(id -u) <plist-path>` 加载 plist。
- Linux：将 unit 文件复制到用户级 systemd 目录后，执行
  `systemctl --user daemon-reload` 和
  `systemctl --user enable --now rime-userdb-sync.timer`。
- Windows：替换占位符后，在任务计划程序中导入 XML。
- Android：按设计不提供调度器示例。Android 仍然保持半自动模式，
  只应通过显式前台操作运行该工具。
