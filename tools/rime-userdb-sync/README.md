# Rime 用户词库同步工具使用说明

> 面向 `tools/rime-userdb-sync` 当前实现的详细中文使用文档。

## 1. 工具用途

这个工具用于在多台设备之间同步 **Rime 用户输入产生的词库快照**，目标是：

- 只同步 `*.userdb.txt`
- 不同步 `.yaml`、`.schema.yaml`、`.dict.yaml`、`.custom.yaml` 等配置文件
- 不同步 `.userdb/` 目录
- 不把整个 Rime 用户目录直接挂到云盘同步
- 避免多设备写同一个远端文件

它实现的核心流程是：

1. 从远端读取所有设备的用户词库快照
2. 调用本机 Rime 的同步命令，在本地完成 merge
3. 只把当前设备自己的快照上传回远端

也就是固定的：

```text
pull-all -> merge-local -> push-own-only
```

---

## 2. 当前实现状态

当前仓库已经包含：

- CLI 入口
- 核心同步引擎
- `installation.yaml` 修复逻辑
- 平台路径解析
- 过滤规则
- 调度器示例
- 文档
- 单元测试与 fixtures

但仍需你在真实环境里继续做：

- 真正的 `rclone` 联通验证
- 真正的 Rime 同步命令联动验证
- 多平台端到端验收

---

## 3. 目录结构

### 核心代码

- `tools/rime-userdb-sync/cli.py`
- `tools/rime-userdb-sync/engine.py`
- `tools/rime-userdb-sync/filtering.py`
- `tools/rime-userdb-sync/installation.py`
- `tools/rime-userdb-sync/platforms.py`
- `tools/rime-userdb-sync/__init__.py`

### 配置示例

- `tools/rime-userdb-sync/config.example.json`

### 调度器示例

- `tools/rime-userdb-sync/examples/macos/com.rime-userdb-sync.plist`
- `tools/rime-userdb-sync/examples/linux/rime-userdb-sync.service`
- `tools/rime-userdb-sync/examples/linux/rime-userdb-sync.timer`
- `tools/rime-userdb-sync/examples/windows/RimeUserdbSync.xml`
- `tools/rime-userdb-sync/examples/windows/rime-userdb-sync-task.ps1`

### 测试

- `tests/rime_userdb_sync/test_filtering.py`
- `tests/rime_userdb_sync/test_identity.py`
- `tests/rime_userdb_sync/test_installation_yaml.py`
- `tests/rime_userdb_sync/test_one_shot_flow.py`
- `tests/rime_userdb_sync/fixtures/`

---

## 4. 支持的平台

当前实现按下列平台名工作：

- `darwin`
- `windows`
- `linux`
- `android`

默认 Rime 用户目录：

- macOS：`~/Library/Rime`
- Windows：`%APPDATA%\\Rime`
- Linux：`~/.local/share/fcitx5/rime`
- Android：`/storage/emulated/0/Android/data/org.fcitx.fcitx5.android/files/data/rime`

如果实际路径不同，可以通过配置文件或 CLI 参数覆盖。

---

## 5. 前置条件

使用前请确保：

### 5.1 Python

本工具当前实现基于 Python 3 运行。

建议：

```bash
python3 --version
```

### 5.2 rclone

需要系统里已安装并可直接调用 `rclone`：

```bash
rclone version
```

### 5.3 已配置好 WebDAV / 坚果云 remote

本工具**不会**帮你自动创建 rclone remote，也不会管理账号密码。

你需要先手动完成：

```bash
rclone config
```

并确保远端名可用，比如：

```text
nutstore-rime:
```

### 5.4 本机 Rime 同步命令

非 Android 平台必须提供本机可执行的 Rime 同步命令。

常见示例：

#### macOS 鼠须管

```bash
/Library/Input\ Methods/Squirrel.app/Contents/MacOS/Squirrel --sync
```

#### Windows 小狼毫

```powershell
WeaselDeployer.exe /sync
```

#### Linux Fcitx5 Rime

优先：

```bash
rime_dict_manager --sync
```

备选：

```bash
rime_dict_manager -s
```

#### Android

Android 默认不要求自动 merge 命令。它按半自动流程工作。

---

## 6. 配置文件

配置文件格式为 **JSON**。

示例文件：

- `tools/rime-userdb-sync/config.example.json`

### 6.1 当前实现支持的配置键

| 键名 | 说明 |
|---|---|
| `remote_root` | 远端根目录，例如 `nutstore-rime:RimeUserDBSync` |
| `device_id` | 当前设备要使用的 `installation_id` |
| `rime_user_dir` | 本机 Rime 用户目录 |
| `local_sync_dir` | 本地 `.sync` 目录；不填时默认 `rime_user_dir/.sync` |
| `rime_sync_command` | 本机 Rime merge 命令，可写成字符串或字符串数组 |
| `rclone_binary` | `rclone` 可执行文件名或绝对路径 |
| `include_patterns` | 默认只需要 `["*.userdb.txt"]` |
| `platform_override` | 手动指定平台：`darwin/windows/linux/android` |
| `interval_minutes` | 当前实现会读取，但是否实际被调度器使用取决于你的外部调度方式 |
| `android_allow_push` | Android 场景下是否允许显式 push |

### 6.2 推荐配置示例

```json
{
  "remote_root": "nutstore-rime:RimeUserDBSync",
  "device_id": "mac-squirrel",
  "rime_user_dir": "~/Library/Rime",
  "local_sync_dir": "~/Library/Rime/.sync",
  "rime_sync_command": [
    "/Library/Input Methods/Squirrel.app/Contents/MacOS/Squirrel",
    "--sync"
  ],
  "rclone_binary": "rclone",
  "include_patterns": [
    "*.userdb.txt"
  ],
  "interval_minutes": 60,
  "android_allow_push": false
}
```

---

## 7. installation.yaml 约束

这个工具会把 `installation.yaml` 当作 **Rime 运行时状态文件** 使用，而不是主配置文件。

### 7.1 正常 sync 的行为

正常 `sync` 会先校验：

- `installation.yaml` 是否存在
- `installation.yaml.sync_dir` 是否等于本地 `.sync`

如果不满足，会 **fail-closed**，直接报错，不会继续同步。

### 7.2 repair-installation 的行为

只有 `repair-installation` 允许修改 `installation.yaml`：

- 先生成备份
- 再改写 `sync_dir`
- 缺失 `installation.yaml` 时可创建最小文件

当前最小必需字段：

- `installation_id`
- `sync_dir`
- `update_time`

---

## 8. CLI 用法

当前 CLI 入口是：

```bash
python3 tools/rime-userdb-sync/cli.py
```

### 8.1 查看帮助

```bash
python3 tools/rime-userdb-sync/cli.py --help
```

### 8.2 可用子命令

当前实现支持：

- `sync`
- `push`
- `repair-installation`

---

## 9. sync：标准同步流程

### 9.1 命令形式

```bash
python3 tools/rime-userdb-sync/cli.py sync \
  --config tools/rime-userdb-sync/config.example.json
```

也可以完全用 CLI 参数传入：

```bash
python3 tools/rime-userdb-sync/cli.py sync \
  --remote-root nutstore-rime:RimeUserDBSync \
  --device-id mac-squirrel \
  --rime-user-dir ~/Library/Rime \
  --rime-sync-command "/Library/Input Methods/Squirrel.app/Contents/MacOS/Squirrel --sync"
```

### 9.2 实际执行步骤

`sync` 会做这些事：

1. 解析平台和路径
2. 校验 `installation.yaml`
3. 获取本地锁
4. 从远端列出所有允许的 `*.userdb.txt`
5. 拉取所有设备快照到本地 `.sync`
6. 调用本机 Rime 同步命令
7. 本地 merge 成功后，上传当前设备的快照
8. 释放锁

### 9.3 重要限制

- 非 Android 平台如果没有 `rime_sync_command`，会直接报错
- 如果 merge 命令失败，不会执行上传
- 如果远端列举或下载失败，整个流程中止

---

## 10. push：手动 merge 后只上传

这个命令适合：

- 你已经手动完成本地 merge
- 想单独执行“只上传当前设备快照”

### 10.1 命令形式

```bash
python3 tools/rime-userdb-sync/cli.py push \
  --config /path/to/config.json
```

### 10.2 行为

- 不执行 pull
- 不执行本地 Rime merge
- 只扫描 `local_sync_dir/<installation_id>/`
- 只上传允许的 `*.userdb.txt`

---

## 11. repair-installation：修复 installation.yaml

### 11.1 dry-run

先预览：

```bash
python3 tools/rime-userdb-sync/cli.py repair-installation \
  --dry-run \
  --rime-user-dir ~/Library/Rime \
  --device-id mac-squirrel
```

### 11.2 实际修复

```bash
python3 tools/rime-userdb-sync/cli.py repair-installation \
  --rime-user-dir ~/Library/Rime \
  --device-id mac-squirrel
```

### 11.3 输出内容

当前会返回 JSON，包含：

- `installation_path`
- `backup_path`
- `installation_id`
- `sync_dir`
- `created`
- `dry_run`

---

## 12. dry-run 用法

### 12.1 sync dry-run

```bash
python3 tools/rime-userdb-sync/cli.py sync \
  --config /path/to/config.json \
  --dry-run
```

### 12.2 push dry-run

```bash
python3 tools/rime-userdb-sync/cli.py push \
  --config /path/to/config.json \
  --dry-run
```

### 12.3 dry-run 的作用

它会展示：

- lock 阶段
- pull 阶段
- merge 阶段
- push 阶段

但不会真正：

- 写 installation.yaml
- 创建锁文件
- 下载/上传远端文件
- 执行本地 merge

---

## 13. Android 半自动流程

Android 不支持桌面端那种完整自动化。

当前建议流程：

### 13.1 第一步：前台 pull / validate / dry-run

```bash
python3 tools/rime-userdb-sync/cli.py sync \
  --config /path/to/android-config.json \
  --platform android \
  --dry-run
```

### 13.2 第二步：用户手动完成本地 merge

由用户在 Android 端自己确认 Rime merge 已完成。

### 13.3 第三步：显式 push

```bash
python3 tools/rime-userdb-sync/cli.py push \
  --config /path/to/android-config.json \
  --platform android
```

注意：

- Android 不提供 scheduler 示例
- Android 不提供后台静默自动同步

---

## 14. 锁文件与日志

### 14.1 锁文件

当前实现会在：

```text
<local_sync_dir>/locks/rime-userdb-sync.lock.json
```

创建锁文件。

### 14.2 stale lock

如果发现旧锁，可以显式允许清理：

```bash
python3 tools/rime-userdb-sync/cli.py sync \
  --config /path/to/config.json \
  --cleanup-stale-lock
```

### 14.3 日志

正常非 dry-run 时，日志会写到：

```text
<local_sync_dir>/logs/rime-userdb-sync.log
```

同时标准输出也会打印 JSON 日志行。

日志字段至少包括：

- `timestamp`
- `installation_id`
- `phase`
- `action`
- `result`

---

## 15. 远端目录约定

远端必须是共享根目录，例如：

```text
nutstore-rime:RimeUserDBSync
```

远端实际结构：

```text
RimeUserDBSync/
  mac-squirrel/
    mint.userdb.txt
  win-weasel/
    mint.userdb.txt
  linux-fcitx5/
    mint.userdb.txt
```

注意：

- `remote_root` 应该是共享根目录
- 不应该把它写成某个设备自己的子目录

---

## 16. 调度器示例

调度器示例放在：

- `tools/rime-userdb-sync/examples/macos/`
- `tools/rime-userdb-sync/examples/linux/`
- `tools/rime-userdb-sync/examples/windows/`

这些都只是模板，需要先替换占位符后再使用。

更多说明见：

- `tools/rime-userdb-sync/examples/README.md`

### 16.1 macOS LaunchAgent 注意事项

macOS 上不建议让 LaunchAgent 直接从 `~/Desktop`、`~/Documents` 或这些目录下的仓库路径执行同步脚本。原因是 launchd 启动的后台进程可能没有对应目录的隐私权限，常见报错是：

```text
Operation not permitted
```

推荐做法：

1. 把工具脚本和本机配置复制到用户库目录：

```bash
mkdir -p "$HOME/Library/Application Support/rime-userdb-sync"
mkdir -p "$HOME/Library/Logs/rime-userdb-sync"
cp tools/rime-userdb-sync/*.py "$HOME/Library/Application Support/rime-userdb-sync/"
cp /path/to/config.json "$HOME/Library/Application Support/rime-userdb-sync/config.json"
```

2. 让 plist 执行这个目录里的入口：

```text
~/Library/Application Support/rime-userdb-sync/cli.py
```

3. 在 macOS LaunchAgent 场景下，`PATH` 通常只有：

```text
/usr/bin:/bin:/usr/sbin:/sbin
```

所以配置里的 `rclone_binary` 推荐写绝对路径，例如：

```json
{
  "rclone_binary": "/opt/homebrew/bin/rclone"
}
```

4. 如果 `~/Library/Rime` 本身是指向 `~/Desktop/...` 的符号链接，LaunchAgent 读取 `installation.yaml` 时仍可能被 macOS 隐私权限拦截。遇到这种情况时，可选处理方式是：

- 使用已经具备访问权限的 Python 解释器，例如用户自己的 Python 环境
- 给对应 Python/终端授予 Full Disk Access
- 或者把 Rime 目录迁出 Desktop / Documents 等受保护目录

手动触发并检查：

```bash
launchctl kickstart -k gui/$(id -u)/com.rime-userdb-sync
launchctl print gui/$(id -u)/com.rime-userdb-sync | grep -E 'state =|runs =|last exit code ='
tail -120 "$HOME/Library/Logs/rime-userdb-sync/stdout.log"
tail -120 "$HOME/Library/Logs/rime-userdb-sync/stderr.log"
```

一次成功的 one-shot 同步通常会显示：

```text
state = not running
last exit code = 0
```

`state = not running` 对 one-shot 定时任务是正常的；关键是 `last exit code = 0`，以及 stdout 日志里能看到 `pull`、`merge`、`push`、`sync complete`。

---

## 17. 当前实现与文档的已知差异

为了避免误解，这里明确两点：

1. 当前实际 CLI 入口是：

```bash
python3 tools/rime-userdb-sync/cli.py
```

2. 任何仍引用旧入口或旧配置键的文档/示例，都应以当前 README 与 `cli.py` / `engine.py` 为准。

---

## 18. 推荐使用顺序

建议按这个顺序使用：

### 第一步：准备配置文件

复制并修改：

```text
tools/rime-userdb-sync/config.example.json
```

### 第二步：先修 installation.yaml

```bash
python3 tools/rime-userdb-sync/cli.py repair-installation \
  --config /path/to/config.json \
  --dry-run
```

确认无误后再正式执行。

### 第三步：做一次 sync dry-run

```bash
python3 tools/rime-userdb-sync/cli.py sync \
  --config /path/to/config.json \
  --dry-run
```

### 第四步：执行真实 sync

```bash
python3 tools/rime-userdb-sync/cli.py sync \
  --config /path/to/config.json
```

### 第五步：再接入调度器

在确认单次同步没问题后，再使用 `examples/` 里的模板接入系统调度。

---

## 19. 常见问题

### Q1：为什么 `sync` 一开始就报错要求先 repair-installation？

因为工具默认要求：

- `installation.yaml` 必须存在
- `sync_dir` 必须是本地 `.sync`

如果你当前还是把 `sync_dir` 指向坚果云目录，工具会故意 fail-closed。

### Q2：为什么没有自动创建 rclone remote？

这是刻意设计的。工具只做同步，不接管凭据配置。

### Q3：为什么 Android 没有定时器示例？

因为当前设计明确规定 Android 只支持半自动流程。

### Q4：为什么 tests 通过了，但还不能说完全可用了？

因为当前通过的是：

- 合同级测试
- 夹具测试
- CLI smoke

还没有完成真实：

- WebDAV / rclone
- 真 Rime merge 命令
- 多设备联调

---

## 20. 下一步建议

如果你准备继续落地，建议下一步做：

1. 用你自己的 `config.json` 跑一次 `repair-installation --dry-run`
2. 跑一次 `sync --dry-run`
3. 在本机做一次真实 `sync`
4. 再接坚果云 WebDAV 做真实远端联调
