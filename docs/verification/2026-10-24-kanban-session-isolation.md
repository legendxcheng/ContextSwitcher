# Kanban Codex 会话归属与命令行恢复验收

日期：2026-10-24。来源：[Issue #17](https://github.com/legendxcheng/ContextSwitcher/issues/17)。

## 实现与确认边界

- 新建执行 `codex --no-daemon -C <目录>`；恢复执行 `codex --no-daemon resume <保存的 UUID> -C <目录>`。Herdr 只负责窗口及启动命令，不执行对话恢复。
- 保留模型、权限及工作目录规则，不修改全局 Codex/Herdr 配置，不停止共享 app-server。
- 本机 Codex 0.164.0 的 SessionStart 在恢复后首次收到新消息时才执行。用户进一步确认：恢复后不发消息也必须能再次完成关闭，且恢复必须通过 `codex resume`。
- 优先采用精确绑定窗口的 Herdr 会话报告；报告缺失时，仅对 interactive_ready 的 Codex 检查该 pane 的真实前台进程。shell PID、前台进程组和进程 PID 必须一致，argv 必须完整匹配本应用的 `codex --no-daemon resume <UUID> -C <目录>`，UUID 合法，随后再次核验完整目标身份。新建、共享模式、未知 argv 或身份不明均不能通过这个恢复分支。
- 此分支不从旧数据库 ID 直接推断成功，不查找其他窗口或最近会话，不发送模型探测消息，不写回 Herdr 的会话报告。已有钩子报告继续优先。
- 没有迁移或自动修复个人旧异常任务；原来的缺 ID、身份替换、未知派发及关闭失败保护保留。

## 故障复现及修复验证

原始个人环境只读证据：任务 pane 缺少 agent_session，另一个 pane 上出现了该任务的真实 UUID；共享 app-server 与任务客户端继承了不同的 HERDR_PANE_ID。

真实回归通过任务生命周期服务、真实 SQLite 和真实 Herdr CLI 执行两任务启动、完成、数据库关闭重开、精确 resume 及再次完成。它不是参数字符串测试。测试使用隔离 Codex 数据目录和专用 workspace。

- 前两次测试被隔离目录的钩子信任提示挡住，不计为原缺陷复现。
- 补齐隔离配置后，未修复版本在 resume 阶段出现 `flow.session_mismatch`；只增加 `--no-daemon` 后仍在同一位置失败。
- 隔离钩子观测确认：resume 不发消息时没有 SessionStart 上报；首次新消息之后才上报。该观测中的测试消息只发送给本次专用 pane。
- 补充当前进程 argv 核验后，新增 live 生命周期测试显式通过，约 32 秒；两次 resume 均不发送任何新输入即可完成关闭。
- 测试保留一个不同工作目录的空 shell，避免关闭最后一个 pane 导致 Herdr 自动删除整个 workspace。关闭最后 pane 后 workspace 消失的现有清理边界不属于本次修复，不能将该场景报告为已通过。

## 真实 Windows Tauri / WebView2 验收

使用专用 Herdr workspace、独立 SQLite 和 WebView2 用户目录，操作真实看板；Tauri IPC、Rust、Herdr 与 Codex 均未替换为 mock。

| 场景 | 观察结果 |
| --- | --- |
| UI 新建 A/B 并拖入开发中 | 后台启动完成，两个独占 pane 分别获得不同且真实的 Codex UUID |
| 首次任务执行 | A/B 分别回复本次唯一标识，没有执行命令或修改文件 |
| A 拖入完成、B 点击完成按钮 | 保存各自 UUID；对应 pane 消失；A 完成不关闭 B；清理标志清除 |
| 退出并重新打开隔离看板 | 保存记录仍在；从完成列拖回开发中触发真实命令行 resume |
| resume 身份 | 从 Herdr process-info 读出的 argv 包含 `--no-daemon resume` 与各自原 UUID，工作目录保持一致 |
| 恢复后不输入消息即完成 | Herdr agent_session 此时为空，当前进程命令行核验通过；两张任务均正常关闭，没有恢复错误 |
| 无历史提示词重发 | 独立读取两段真实 Codex 对话记录，每段只有一条原始用户任务消息及对应唯一回复；没有恢复探测或重复任务消息 |
| 归档 | 已清理完成的 B 归档成功，从看板移除 |

调试与验收脚本、快照和截图保存在 `.scratch/session-isolation/`，不提交包含本机凭据或运行数据的隔离目录。恢复验收不依赖钩子诊断包装器，使用正常的已安装 Herdr 集成。

## 自动化结果与限制

- `cargo test --offline --locked`：63 项通过，4 项 live 默认跳过；新增会话隔离 live 测试另外显式运行通过，其余 3 项本轮未运行。
- 前端：70 项测试通过；TypeScript 检查和生产构建通过，保留既有大 chunk 提示。
- 原生 debug 构建通过；用户正在运行的原开发应用未被停止或替换，未构建或安装新版安装包。
- 现有服务测试继续覆盖缺 ID 保留窗口、关闭失败重试、替换进程拒绝关闭、并发独占、不确定派发不重发等异常；这些是自动化故障注入结果，不代表本轮逐项制造了真实外部故障。
- 本次代码不处理历史异常卡片，也不声称覆盖不同 Codex/Herdr 版本、Linux/macOS、系统 DPI、干净机器或共享服务重启。
