# Kanban 代码结构与关键流程分析

分析日期：2026-10-23。范围：当前工作区 `kanban/` 的前端、Rust 后端、数据库及构建配置；同时核对主项目的 ContextSwitcher 任务序列化格式。结论以代码实现为依据，现有 `CLAUDE.md` 仅作为背景。本文记录当前实现，不代表后续改进已经完成。

## 1. 项目定位与架构边界

Kanban 是同一仓库中的独立桌面应用，使用 React + TypeScript 构建界面，以 Tauri/Rust 提供 SQLite、文件系统、原生目录选择和 Herdr CLI 调用能力。它不是 Python/PySide6 主程序中的一个页面，也没有直接调用主程序的 TaskManager 或 WindowManager。

业务中心是“为本地项目维护任务卡片，编辑带文件/技能引用的提示词，再发送给已有 Herdr Agent”。当前已形成项目管理、三列看板、提示词编辑、引用搜索和派发的基本闭环。

必须区分三个概念：

| 概念 | 当前职责 | 关系的实际约束 |
| --- | --- | --- |
| ContextSwitcher Task | Python 主应用管理的窗口上下文及任务 | Kanban 只读取其摘要，不写回、不切换窗口 |
| Kanban Project | 看板容器，保存本地根目录、Herdr workspace 名称和可选 CS task ID | 一个项目有多张卡片；CS 关联可为空，且没有唯一约束 |
| Kanban Task | 项目中的单张卡片，含状态、提示词及最近一次派发信息 | 不等同于主应用 Task，也不映射主应用的 `todo_items` |

`CLAUDE.md` 中“一个 CS Task = 一个 Workspace = 一个 Project”是设计意图。代码没有强制一对一关系；workspace 也是文本标签，不是稳定 workspace ID。

```mermaid
flowchart LR
    UI[React 组件与局部状态] --> API[api.ts：17 个 invoke 封装]
    API --> CMD[Tauri commands.rs]
    CMD --> DB[(SQLite kanban.db)]
    CMD --> FILE[项目文件与 ~/.claude 技能]
    CMD --> CS[ContextSwitcher/tasks.json：只读]
    CMD --> CLI[Herdr CLI 子进程]
    CLI --> AGENT[已有 Agent pane]
    CMD --> PICK[rfd 原生目录选择器]
```

没有 HTTP 服务、任务队列、后台调度器、前后端事件订阅或 Agent 完成回调。数据通过 `invoke → Promise` 请求/响应传递；界面主要依靠操作后重新查询刷新。

## 2. 目录与入口

```text
kanban/
├─ package.json / package-lock.json  前端依赖与 npm 脚本
├─ vite.config.ts                   Vite、开发端口、HMR
├─ tsconfig*.json                   TypeScript 编译约束
├─ index.html                      WebView 页面入口
├─ src/
│  ├─ main.tsx                     React 挂载，启用 StrictMode
│  ├─ App.tsx                      项目列表、项目选择及顶层布局
│  ├─ App.css                      全局主题、布局、组件样式与动画
│  ├─ Icon.tsx                     本地 SVG 线性图标
│  ├─ types.ts                     前端数据结构
│  ├─ api.ts                       Tauri IPC 适配层
│  ├─ ProjectSidebar.tsx           项目列表和管理入口
│  ├─ ProjectFormDialog.tsx        项目表单、目录选择、CS 任务关联
│  ├─ KanbanBoard.tsx              卡片加载、三列、拖拽及弹层协调
│  ├─ TaskCard.tsx                 卡片展示、派发/完成/删除入口
│  ├─ TaskEditPanel.tsx            名称和提示词编辑侧栏
│  ├─ PromptEditor.tsx             Tiptap 初始化与 JSON 输出
│  ├─ MentionNode.ts              自定义原子行内 mention 节点
│  ├─ MentionPopover.tsx           @/$ 搜索、键盘选择和节点插入
│  ├─ DispatchDialog.tsx           Agent 选择、预览和派发
│  ├─ dispatchUtils.ts             引用展开为最终提示词文本
│  └─ Toast.tsx                    全局通知函数与展示容器
├─ src-tauri/
│  ├─ Cargo.toml / Cargo.lock      Rust 依赖
│  ├─ build.rs                     tauri_build::build()
│  ├─ tauri.conf.json              窗口、构建、资源、安全配置
│  ├─ capabilities/default.json    主窗口权限配置
│  └─ src/
│     ├─ main.rs                   调用 kanban_lib::run()
│     ├─ lib.rs                    初始化数据库、插件与命令注册
│     ├─ db.rs                     数据路径、建表、轻量迁移
│     ├─ models.rs                 Rust 模型及状态转换
│     └─ commands.rs               全部 IPC 命令及外部集成
├─ public/、src/assets/、src-tauri/icons/  静态资源和图标
└─ dist/、node_modules/、src-tauri/target/ 构建产物与依赖目录
```

### 2.1 桌面启动顺序

1. [main.rs](kanban/src-tauri/src/main.rs) 调用 `kanban_lib::run()`；release 模式设置 Windows GUI subsystem。
2. [lib.rs](kanban/src-tauri/src/lib.rs) 调用 `db_path()`，创建数据目录、打开 SQLite、执行 `db::init()`。
3. 连接包装为 `DbState(Mutex<Connection>)`，交给 Tauri 托管。
4. 注册 opener、shell 插件和 17 个业务命令，再启动 Tauri 窗口。
5. [main.tsx](kanban/src/main.tsx) 挂载 `App`；`App` 加载项目，自动选择列表中的第一个有效项目。
6. `KanbanBoard` 按项目 ID 加载卡片，按 workspace 名称查询 Agent。

数据库初始化发生在窗口启动前。创建目录、连接和建表失败使用 `expect` 终止，没有恢复界面。数据库命令通过一把 Mutex 串行访问同一连接。

### 2.2 构建与平台

前端声明使用 React 19、Tiptap 3、TypeScript 6、Vite 8；Rust 使用 Tauri 2、rusqlite 0.32（bundled SQLite）、serde、uuid、chrono、walkdir 和 rfd。声明范围与实际锁定版本应分别查看 `package.json` 和 lockfile。

`tauri.conf.json` 配置窗口为 1280×800，最小 900×600，标题为 Herdr Kanban。`dragDropEnabled: false` 配合当前 HTML 拖放实现，不能误当成“应用不支持拖拽”。Vite 固定端口 1420，设置 `TAURI_DEV_HOST` 时另用 1421 提供 HMR。

虽然保留 Tauri 模板的 mobile 入口属性，CS 数据路径依赖 `APPDATA`，外部执行依赖本机 `herdr`；现阶段应按 Windows 桌面工作流理解，不能据此宣称跨平台验收完成。

## 3. 前端组件与状态归属

```mermaid
flowchart TD
    App --> ToastContainer
    App --> ProjectSidebar
    ProjectSidebar --> ProjectFormDialog
    App --> KanbanBoard
    KanbanBoard --> TaskCard
    KanbanBoard --> TaskEditPanel
    KanbanBoard --> DispatchDialog
    TaskEditPanel --> PromptEditor
    PromptEditor --> MentionPopover
    PromptEditor --> MentionNode
    DispatchDialog --> resolveMentions
```

| 模块 | 拥有的状态/职责 | 与外部的交互 |
| --- | --- | --- |
| [App.tsx](kanban/src/App.tsx) | `projects`、`selectedId`；从列表派生当前项目 | `listProjects`；把刷新函数下传侧栏 |
| [ProjectSidebar.tsx](kanban/src/ProjectSidebar.tsx) | 新建弹窗开关、编辑目标 | 删除前确认；完成 CRUD 后通知 App 重载 |
| [ProjectFormDialog.tsx](kanban/src/ProjectFormDialog.tsx) | 名称、根目录、workspace、CS task ID、保存状态和错误 | 创建/更新项目、选择目录、读取 CS 任务 |
| [KanbanBoard.tsx](kanban/src/KanbanBoard.tsx) | 卡片列表、加载、新建输入、拖拽状态、Agent 列表、编辑 ID、待派发对象 | 加载/创建/变更状态；协调编辑与派发弹层 |
| [TaskCard.tsx](kanban/src/TaskCard.tsx) | 展示卡片名称、状态和最近派发信息 | 编辑/派发回调；直接调用完成和删除 API |
| [TaskEditPanel.tsx](kanban/src/TaskEditPanel.tsx) | 名称与提示词草稿、saving | 显式保存；取消、遮罩、Esc 直接关闭 |
| [PromptEditor.tsx](kanban/src/PromptEditor.tsx) | Tiptap Editor 实例 | 接收 JSON 字符串；每次编辑输出序列化 JSON |
| [MentionPopover.tsx](kanban/src/MentionPopover.tsx) | 搜索词、引用种类、候选项、选择下标、展开状态 | 查询文件/技能；写入编辑器 transaction |
| [DispatchDialog.tsx](kanban/src/DispatchDialog.tsx) | Agent 列表、选中 pane、loading、错误、预览文本 | 重新查 Agent、展开引用、派发 |
| [Toast.tsx](kanban/src/Toast.tsx) | 通知数组及自增 ID | 模块级 `_notify` 指向容器回调，3 秒后删除通知 |

没有 Redux、Zustand 或查询缓存层。`onChanged`、`onSaved` 等回调负责向上通知，父组件重新查询数据。`load()` 会把整个看板切换为 loading 分支，并非局部乐观更新。

表单草稿只存在内存里。任务编辑没有自动保存或未保存提醒；“保存提示词”和“派发提示词”是两个独立动作，派发读取卡片中已保存的 `prompt_json`。

### 3.1 样式与交互实现

[App.css](kanban/src/App.css) 集中定义深色中性色阶、语义色、间距、圆角以及组件样式。2026-10-24 界面调整借鉴 [Supabase 官网](https://supabase.com/) 的中性色、绿色强调、细边框和留白，在现有深色界面上实现：炭灰背景、`#3ecf8e` 主色、6/8px 圆角；根字号为 16px，任务标题、列标题与编辑正文为 16px，操作按钮和辅助文字为 14px，紧凑状态标签为 12px；侧栏宽度 248px，窄窗口收为 216px。看板仍为三列 grid，每列至少 240px，不足时仅看板横向滚动；编辑侧栏宽 520px，保留 `max-width` 限制。动画包括侧栏滑入、遮罩淡入、Toast 滑入和加载旋转，并响应系统减少动效设置。

`App` 增加工作空间面包屑和项目目录层级；`ProjectSidebar` 增加品牌区、项目数量与明确的新建入口，项目选择使用原生按钮；`KanbanBoard` 增加任务总数、完成数量及聚焦底部输入框的新建按钮。Agent 派发区取消整体低透明度。`Icon.tsx` 提供本地 SVG 线性图标，替换看板空态与项目操作的字符图标，不加载远程字体或样式。任务卡片、项目表单、编辑侧栏、派发对话框、引用候选与通知使用同一套主题。

本次验证：`npm run build` 成功，现有 16 项拖放/派发测试通过；Edge 浏览器使用隔离的内存 IPC 样例检查 1280×800 和 900×600 布局，以及新任务聚焦、创建任务、编辑保存、编辑器内输入 N、派发预览与取消、项目表单和空看板。浏览器检查不代表 Tauri/WebView2、真实 SQLite 或真实 Herdr 派发已经验收。

看板使用原生 `draggable`、`dataTransfer` 与 React 拖放事件，没有使用已经安装的 `@dnd-kit/*`。`draggingIdRef` 是拖放时的首选任务 ID 来源，代码注释说明这是对 WebView2 中 `getData()` 可能为空的兼容措施。

`@tiptap/extension-mention` 也没有用于当前引用链路；项目采用自定义 `MentionNode` 与 `MentionPopover`。前端 opener 包和 Rust opener/shell 插件存在，但业务调用 Herdr 用的是 Rust `std::process::Command`，不是 shell 插件 API。

## 4. 数据模型与持久化

源码入口：[types.ts](kanban/src/types.ts)、[models.rs](kanban/src-tauri/src/models.rs)、[db.rs](kanban/src-tauri/src/db.rs)。前后端模型手工维护，没有生成共享契约。

### 4.1 Project

| 字段 | 作用 |
| --- | --- |
| `id` | Rust 生成 UUID v4 字符串，主键 |
| `name` | 项目展示名称 |
| `root_path` | 文件搜索根目录；不是派发进程的工作目录 |
| `herdr_workspace` | Agent 列表筛选文本，同时进入派发目标记录 |
| `cs_task_id` | 可空的 CS 任务 ID，仅作为关联信息 |
| `created_at` | UTC RFC3339 字符串；项目列表按其排序 |

表单要求名称、根目录、workspace 非空，但 Rust CRUD 没有重复实施该校验，也没有验证目录存在、workspace 存在或 CS ID 有效。

### 4.2 Task

| 字段组 | 作用 |
| --- | --- |
| `id`、`project_id` | 卡片主键及所属项目；SQL 声明项目外键 |
| `name`、`status` | 名称与 `todo / in_progress / done` 三态 |
| `prompt_json` | Tiptap 文档的 JSON 字符串；新卡默认 `"{}"` |
| `prompt_snapshot` | 最近一次成功派发时实际发送的展开文本，可为空 |
| `dispatched_at`、`dispatched_to` | 最近一次派发时间与 `workspace/pane_id`，可为空 |
| `created_at`、`updated_at` | 创建及最后修改时间；任务列表按创建时间排序 |

SQL 只有 `projects` 和 `tasks` 两张表，索引为 `tasks(project_id)` 和 `tasks(status)`。没有列内排序字段、派发历史表、附件表、同步日志或执行结果表。

`DispatchRecord` 是命令返回值，不是数据库实体。再次派发会覆盖 Task 上的旧快照和目标，无法从当前库结构恢复完整派发历史。后续修改任务正文不会同步修改旧快照；手动改状态也不会清除派发字段。

### 4.3 数据路径、迁移与约束

默认数据库为 `%APPDATA%\herdr-kanban\kanban.db`。如果没有 `APPDATA`，代码回退到当前目录下 `herdr-kanban/kanban.db`。它与 `%APPDATA%\ContextSwitcher\tasks.json` 是两个独立数据源。

初始化先执行 `CREATE TABLE/INDEX IF NOT EXISTS`，然后尝试 `ALTER TABLE projects ADD COLUMN cs_task_id TEXT` 并忽略结果。这能容忍重复添加列，但也会隐藏其他迁移错误；没有 schema version 或有序迁移记录。

任务外键声明 `ON DELETE CASCADE`，项目删除命令只执行一条项目 DELETE。应用没有显式设置 `PRAGMA foreign_keys`；本次核对本机锁定依赖 `libsqlite3-sys 0.30.1` 的 bundled 构建源码，默认编译参数包含 `SQLITE_DEFAULT_FOREIGN_KEYS=1`。因此不能仅凭缺少 PRAGMA 就断言当前构建不会级联删除。若切换 SQLite 构建方式，应显式初始化并验证这一约束；本次没有操作真实数据库做删除验收。

`status` 没有 SQL CHECK 约束。Rust 更新命令接收任意字符串，而读取时 `TaskStatus::from_str()` 将未知值映射为 `todo`，可能掩盖库内异常状态。UPDATE/DELETE 也未检查受影响行数，ID 不存在时可能返回成功。

## 5. IPC 命令契约

[api.ts](kanban/src/api.ts) 是唯一的前端 invoke 入口；[lib.rs](kanban/src-tauri/src/lib.rs) 注册命令；[commands.rs](kanban/src-tauri/src/commands.rs) 实现全部业务。

参数在 TypeScript invoke 对象中使用 camelCase，例如 `rootPath`、`projectId`；Rust 函数参数和返回结构字段使用 snake_case。Rust 的 `Result<T, String>` 对应前端成功值或 Promise rejection，错误没有结构化分类。

| 命令 | 主要输入 | 返回/副作用 |
| --- | --- | --- |
| `list_projects` | 无 | `Project[]`，按创建时间排序 |
| `create_project` | name、rootPath、herdrWorkspace、csTaskId | 插入并返回 Project |
| `update_project` | id + 项目字段 | 更新项目，返回空 |
| `delete_project` | id | 删除项目；卡片清理由外键级联负责 |
| `list_tasks` | projectId | 项目内 Task[]，按创建时间排序 |
| `create_task` | projectId、name | 创建 todo 卡片并返回 Task |
| `update_task` | id、name、promptJson | 更新正文及 updated_at |
| `update_task_status` | id、status | 更新状态及 updated_at |
| `delete_task` | id | 删除卡片 |
| `search_files` | rootPath、query | 最多 50 个 FileEntry |
| `search_skills` | query | 最多 30 个 SkillEntry |
| `read_file_content` | absPath | UTF-8 文件全文 |
| `read_skill_content` | skillMdPath | UTF-8 SKILL.md 全文 |
| `herdr_list_agents` | workspace | 根据标签/目录名筛选的 HerdrAgent[] |
| `dispatch_to_herdr` | taskId、agentName、workspace、promptText | 执行 CLI 后更新卡片，返回 DispatchRecord |
| `pick_folder` | 无 | 原生目录选择结果；取消返回 null |
| `read_cs_tasks` | 无 | CS 任务摘要 CsTask[] |

`dispatch_to_herdr` 的 `agentName` 实际传入 `pane_id`，不是 `HerdrAgent.name`。`name` 是 Agent 类型，`title` 用于展示，`pane_id` 才是发送目标。

## 6. 关键业务调用链

### 6.1 创建项目及关联 ContextSwitcher

`ProjectSidebar → ProjectFormDialog → readCsTasks/pickFolder → createProject/updateProject → Rust SQL → App.loadProjects()`。

表单每次挂载读取一次 CS 任务。选择一个 CS 任务时，仅在项目名称/workspace 当前为空的情况下自动填充，不会自动填根目录，也不会建立后续同步。CS 任务被删除或重命名后，现存 Project 不会自动修正。

`read_cs_tasks()` 读取固定 JSON 文件中的 `tasks` 数组，提取 `id`、`name`、`status`、`herdr_binding.label`；缺少 ID/名称的条目被跳过，文件不存在返回空列表。前端把读取/解析失败也转换为空列表，因此界面无法区分“没有任务”和“读取失败”。

主项目 [Task.to_dict()](core/task_manager.py) 确实输出 `herdr_binding: { workspace_id, label }`，[DataStorage.save_tasks()](utils/data_storage.py) 输出包含版本、时间和 `tasks` 的对象。Kanban 只取 label，不利用主程序已保存的稳定 workspace ID；也不执行主项目的旧格式迁移逻辑。

CS 的完成状态为 `completed`，Kanban 为 `done`。二者分别使用各自的模型，目前没有转换或状态联动。

### 6.2 创建、编辑和移动卡片

1. Todo 列输入名称，`handleAddTask()` 调用 `create_task`。
2. Rust 插入默认 todo 卡片，前端重新加载并用新 ID 打开 `TaskEditPanel`。
3. Tiptap 编辑内容经 `getJSON()` 序列化到面板草稿。
4. 显式保存调用 `update_task`，成功后关闭侧栏、刷新看板。
5. 卡片拖到“开发中”时打开 `DispatchDialog`，选择 Agent 并确认派发；确认前、取消或派发失败均保留原状态。派发成功后由 `dispatch_to_herdr` 更新状态和派发记录，前端重新查询后移动卡片。拖到“未开发”或“完成”时调用 `update_task_status`，成功后重新查询；拖到原列不执行更新。

列之间允许迁移，包括 done 回 todo；从 todo 或 done 进入 in_progress 必须经过派发确认。同一列内部没有手动排序，也没有顺序持久化。“标记完成”按钮只出现在 in_progress 卡片；拖放可以把任意状态卡片直接移到 done。

看板快捷键是无 Ctrl/Meta/Alt 修饰的小写 `n`，聚焦新增输入框；输入框 Enter 新建，Escape 清空并失焦。全局快捷键仅排除了 input/textarea，未排除 Tiptap 的 contenteditable，存在编辑器输入 `n` 被抢焦点的代码路径。

### 6.3 @ 文件与 $ 技能引用

`PromptEditor → MentionPopover → searchFiles/searchSkills → 选择候选 → 插入 MentionNode → prompt_json`。

节点保存的是引用位置，不是引用正文：

```json
{
  "type": "mention",
  "attrs": {
    "kind": "file",
    "label": "src/App.tsx",
    "ref": "E:/MyProject/src/App.tsx"
  }
}
```

`kind` 为 `file` 或 `skill`，`label` 展示名称，`ref` 保存搜索返回的路径。自定义节点为 inline + atom，渲染为不可编辑的 chip。

候选触发正则为 `/([@$])([\w./_-]*)$/`，支持拉丁字母、数字、下划线和部分路径字符，不支持中文查询词、空格、反斜杠或盘符冒号。候选列表支持上下方向键、Enter/Tab、鼠标选择；Escape 关闭。弹层是相对编辑器的绝对定位，未计算光标坐标。

| 搜索能力 | 当前实现与限制 |
| --- | --- |
| 文件搜索 | WalkDir 递归、不跟随符号链接；按文件名做大小写不敏感 contains，非全文、非完整相对路径匹配 |
| 文件排除 | 过滤包含 node_modules、.git、target、__pycache__、.venv、dist、build 的路径；不读取 .gitignore |
| 文件结果 | 先取遍历中的前 50 条，再按相对路径排序；不是全量排序后取前 50 条 |
| 技能搜索 | 扫描 USERPROFILE/HOME 下整个 `.claude`，寻找 SKILL.md；不扫描 `.codex/skills`、`.agents/skills` 或项目技能目录 |
| 技能元数据 | 手工从 frontmatter 读取单行 name/description，非完整 YAML 解析；无 name 时使用父目录名 |
| 技能结果 | 名称或描述 contains 匹配，最多 30 条；无显式排序/去重 |

文件排除使用迭代后的 `filter`，没有 `filter_entry` 目录剪枝，排除目录仍可能被遍历。查询没有 debounce 或缓存。候选 effect 的 cancelled 标记防止过期结果写回，但不会停止已经发起的 Rust 扫描。

### 6.4 派发到 Herdr

存在三个入口：卡片“派发/再派发”按钮、把其他列的卡片拖到“开发中”，或把卡片拖到顶部 Agent chip。拖到“开发中”打开未预选目标的派发对话框；拖到 Agent chip 打开预选该目标的对话框。两种拖放均不会立即发送或提前修改任务状态。done 卡片没有派发按钮，但仍可拖到“开发中”或 Agent 重新派发。

```mermaid
sequenceDiagram
    participant UI as DispatchDialog
    participant R as Rust commands
    participant H as Herdr CLI
    participant DB as SQLite
    UI->>R: herdr_list_agents(workspace)
    R->>H: herdr agent list
    R->>H: herdr workspace list
    R-->>UI: 筛选后的 Agent 列表
    Note over UI: 用户选择 pane 并确认派发
    UI->>R: 逐个 read_file_content/read_skill_content
    R-->>UI: 引用当前文件正文
    UI->>R: dispatch_to_herdr(taskId, paneId, workspace, text)
    R->>H: herdr agent prompt paneId text
    H-->>R: 进程退出状态
    R->>DB: 更新为 in_progress，写入快照与目标
    R-->>UI: DispatchRecord
    Note over UI: 关闭对话框并重新加载卡片
```

**Agent 发现。** 后端解析 `herdr agent list` 的 `result.agents`，再读取 `herdr workspace list` 建立 workspace_id → label 映射。非空 workspace 以大小写不敏感的子串匹配 label 或 Agent cwd 的末级目录；不是精确身份匹配。workspace map 读取失败时静默回退空映射，仍可能通过 cwd 命中。workspace 参数为空则不筛选。

顶部 Agent 栏只在 workspace 名称变化时查询，不定时刷新；派发对话框挂载时会再次查询。代码不依据 Agent 状态禁止发送，也不创建、唤醒或切换 workspace。

**预览。** `buildPreview()` 调用本地 `extractTextWithMentions()`，只展示普通文本与 `[@文件: ...]`、`[$技能: ...]` 占位符，没有读取引用正文。2026-10-24 将按钮文案改为“预览提示词”，避免暗示已展开引用；解析行为保持不变。

**实际展开。** [resolveMentions()](kanban/src/dispatchUtils.ts) 递归处理文档：普通文字直接追加；文件正文放入带路径的分隔标题和代码块；技能正文直接附在技能标题后。段落和标题补换行；并非完整 Markdown 序列化，粗体、列表、hardBreak 等结构没有对应的完整格式恢复。

引用读取按文档顺序逐个 await，无缓存和去重。每次派发读取当时的文件内容，可能与编写提示词时不同。单个引用读取失败会替换为“引用失败”文本并继续发送；参数 `_rootPath` 当前未使用，读取路径不会重新限制在项目根目录内。

**执行及落库。** 后端仅先检查最终文本非空，然后用参数数组执行 `herdr agent prompt <pane_id> <prompt_text>`；没有设置 `current_dir`，也没有通过 shell 拼接命令。workspace 参数不传给该 CLI，只用于数据库记录与返回值。

退出码成功后，后端更新任务为 in_progress 并保存快照、目标和时间。派发命令未解析成功 stdout，也没有等待 Agent 完成任务。故此处的“成功”只证明 CLI 返回成功且后续 SQL 未报错，不能等同于 Agent 已接受、开始或完成业务。

## 7. 当前实现的关键边界与维护风险

以下区分可直接确认的行为与需要运行时复现的风险，不把静态分析当成桌面验收。

| 优先级 | 代码位置与事实 | 影响/建议 |
| --- | --- | --- |
| 高 | `dispatch_to_herdr` 先执行外部发送，再更新 DB；无派发 ID、幂等记录或补偿 | 外部成功而落库失败时，UI 显示失败但 Agent 可能已收到；直接重试可能重复发送。需定义“发送结果不确定”状态及重试契约 |
| 高 | 派发前不检查任务是否存在，SQL 不检查更新行数 | 已删除或错误 task ID 仍可能发送并返回成功；应先校验目标及任务，再检查写入结果 |
| 高 | `KanbanBoard` 在项目切换时复用组件，任务/Agent 请求没有过期结果保护；`pendingDispatch` 未按项目清空 | 快速切换可能出现旧响应覆盖新看板；旧待派发 task 可能搭配新 Project 参数。需项目级请求身份和弹层生命周期隔离，并做交互复现 |
| 高 | `Command::output()` 无超时、取消或输出大小限制；关闭派发弹窗不取消后端工作 | CLI 卡住时请求无法及时结束，关闭后重开还可能再次提交；需有界执行与在途派发状态 |
| 中 | workspace 子串匹配，派发命令不复核 pane 所属 workspace | 同名片段、重命名或过期 pane 可导致目标混淆；适合使用稳定 workspace ID 并复核目标 |
| 中 | 展开函数使用引用路径直接读取全文；未限制大小、根目录、扩展名 | 根目录只是搜索起点，不是访问边界；大文件、二进制/非 UTF-8 文件或根外引用需明确处理规则 |
| 中 | 最终 prompt 全文作为进程命令行参数 | 大量文件展开可能触及平台命令行长度限制；需核对 Herdr 是否支持 stdin/文件输入，再选择传输方式 |
| 中 | 预览与发送使用两套文本转换逻辑，引用失败继续发送 | 用户看到的内容与实际收到的文本可能不同；宜共享解析结果并显式呈现失败引用 |
| 已修复（2026-10-24） | 全局 N 快捷键增加 `isContentEditable` 判断 | 编辑 Tiptap 正文时不会抢走输入焦点；已用浏览器验证 |
| 中 | 部分异步 CRUD 缺少 catch；读取 CS 任务失败被转换为空 | 错误反馈不一致；列表加载、拖放、完成、删除和目录选择需统一呈现错误 |
| 中 | ALTER 错误全部忽略，状态及外部关联缺少后端约束 | 后续数据库演进容易出现静默异常；适合引入版本迁移和命令输入校验 |
| 低 | PromptEditor 无显式 setContent 同步，面板只监听 task.id | 当前常规关闭重开可以重新初始化；若未来复用同一个编辑器切换任务/同步正文，需同步文档，避免旧内容残留 |
| 低 | Toast 在 render 中写模块级回调，定时器无卸载清理 | 当前单根容器简单可用；多根、卸载和测试隔离时宜改为明确订阅/清理 |

还有两项配置边界值得保留：`csp` 当前为 null；capabilities 声明 opener/shell 权限，但现有文件读取与进程执行走自定义 Rust 命令。不能把插件权限列表当作这些命令已经具备路径或目标校验的证据。

## 8. 代码组织评价与后续修改入口

当前结构的优点是入口清楚、组件职责容易定位、IPC 集中、模型较小；SQL、CLI 和文件访问都留在 Rust，React 不直接持有数据库连接。对于本地单用户看板，这种结构便于快速迭代。

主要复杂度集中在两个位置：`KanbanBoard` 同时协调列表、拖放、Agent 和弹层生命周期；`commands.rs` 同时承担数据访问、协议解析、目录遍历、进程执行与集成。扩展时应先围绕明确业务边界拆分，而不是单纯按文件长度拆文件。

| 要做的改动 | 首先阅读/修改 | 必须同步考虑 |
| --- | --- | --- |
| 新增任务状态或转换规则 | types.ts、models.rs、KanbanBoard、TaskCard、commands.rs | SQL 状态约束、旧数据迁移、颜色/按钮、派发强制 in_progress 的语义 |
| 新增项目/任务字段 | models.rs、types.ts、db.rs、commands.rs、api.ts | SELECT 列顺序与 row_to_task、表单、迁移、现有库兼容 |
| 修改提示词或引用格式 | PromptEditor、MentionNode、MentionPopover、dispatchUtils、DispatchDialog | 历史 prompt_json、预览一致性、失败引用、格式保留 |
| 接入更多技能目录 | commands.rs 的 search_skills | 发现路径配置、去重、排序、缓存、完整 frontmatter 解析 |
| 改 Herdr 协议或派发可靠性 | herdr_list_agents、fetch_workspace_label_map、dispatch_to_herdr | 稳定目标 ID、超时、结果解析、重复发送、落库失败 |
| 增加 Agent 自动完成同步 | 独立结果接收/查询模块，加任务状态服务 | 任务与执行实例映射、重复/乱序通知、用户手动状态冲突；当前没有此链路 |
| 加深 CS 集成 | read_cs_tasks、ProjectFormDialog、主项目序列化 | 稳定 workspace ID、completed/done 差异、单向/双向数据所有权 |
| 修改布局与主题 | App.css、对应组件 | WebView2 原生拖放、最小窗口尺寸、遮罩层级和输入焦点 |

可逐步抽出 `project_repository`、`task_repository`、`discovery`、`herdr_client`、`dispatch_service`：命令层只做输入/输出适配，Herdr client 管进程与协议，dispatch service 管任务校验及派发记录一致性。前端可将项目任务加载和弹层状态封装为项目范围的 hook，并将提示词解析变成预览/发送共用的一条链路。这些均为建议，当前代码尚未拆分。

## 9. 构建检查与验收边界

常用命令如下，前端命令在 `kanban/` 执行，Rust 检查在 `kanban/src-tauri/` 执行：

```powershell
# 前端静态检查
.\node_modules\.bin\tsc.cmd --noEmit

# 看板拖放与派发组件回归（模拟 Tauri IPC，不发送真实任务）
npm test

# 前端生产构建；包含 tsc
npm run build

# Rust 检查（本次采用本地缓存，不更新锁文件）
cargo check --offline --locked

# 桌面开发 / 完整桌面打包
npm run tauri dev
npm run tauri build
```

单独 `npm run dev` 或 `npm run preview` 只提供前端页面；当前没有浏览器 mock API，依赖 Tauri invoke 的功能需要桌面宿主。

本次实际结果：

| 检查 | 结果与范围 |
| --- | --- |
| TypeScript `tsc --noEmit` | 通过 |
| `npm run build` | 通过；Vite 输出主 JS 约 640.42 kB，gzip 约 201.70 kB，并提示超过 500 kB 的 chunk 警告 |
| `cargo check --offline --locked` | 通过；不等同于完整 release 打包或桌面运行 |
| 自动化业务测试 | 新增 `src/KanbanBoard.test.tsx` 与 `npm test`：16 项组件交互回归通过，覆盖开发中列弹窗、取消、等待成功、失败、无 Agent、两种拖放 ID 来源、已完成任务重新派发、同列无操作、其他列迁移及原有按钮/Agent 入口。运行真实组件与 API 封装，模拟 Tauri IPC；不代表 Rust/CLI 或桌面 WebView2 实测。现有仓库 CI 只运行 Python pytest |
| 桌面交互、真实数据库 CRUD、Herdr 派发 | 本次未执行；没有向真实 Agent 发送任务，也没有改动用户业务数据 |

后续最有价值的验证是：快速切项目时的响应隔离、Tiptap 中输入 n、缺失/超大引用、Herdr 超时、外部发送成功但 DB 写入失败，以及实际 bundled 数据库的删除级联。这些场景对应当前结构中的真实边界，比只验证组件能渲染更能说明可靠性。

## 10. 推荐阅读路线

初次接手时按以下顺序阅读，能先理解整体，再追踪关键风险：

1. `types.ts → models.rs → db.rs`：厘清 Project、Task、引用和派发快照。
2. `main.tsx → App.tsx → KanbanBoard.tsx`：理解页面和状态归属。
3. `api.ts → lib.rs → commands.rs`：对应每个动作的 IPC、SQL 与外部副作用。
4. `TaskEditPanel → PromptEditor → MentionNode/MentionPopover`：理解 prompt_json 如何产生。
5. `DispatchDialog → dispatchUtils → dispatch_to_herdr`：理解“草稿、预览、实际发送、快照”之间的差异。
6. `ProjectFormDialog → read_cs_tasks → 主项目 Task.to_dict()`：核对跨项目数据契约。

