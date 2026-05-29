# JianDou-video 实施计划

## 1. 项目概述

全栈视频生成平台，基于 MLX 的 LTX 2.3 模型在 Apple Silicon 上进行文本/图片到视频的生成。提供 API 服务、CLI 工具、Vue Web UI 三种交互方式。

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 推理引擎 | [LTX-2-MLX](https://github.com/Acelogic/LTX-2-MLX) | Git submodule，封装而非修改 |
| 后端框架 | FastAPI + WebSocket | REST API + 实时进度推送 |
| CLI | Typer + Rich | 类型安全，美观终端输出 |
| 前端 | Vue 3 + Vite + Pinia | SPA，通过 FastAPI 静态文件服务 |
| 任务队列 | asyncio.Queue + SQLite | 单机多任务并发调度 |
| 配置 | YAML + pydantic-settings | 分层配置，环境变量覆盖 |
| 模型权重 | HuggingFace Hub | 下载/校验/本地注册表 |
| 超分辨率 | PiperSR + 模型内置 Upscaler | Phosphene 同款方案 |

## 3. 目标特性

### 3.1 生成模式
- [ ] **T2V** — 文本到视频
- [ ] **I2V** — 图片到视频（含 cover-crop 预处理）
- [ ] **FFLF** — 首尾帧关键帧插值
- [ ] **Extend** — 视频延长
- [ ] **A2V** — 音频驱动视频（Phosphene 特性）
- [ ] **Joint Audio+Video** — 音视频联合生成

### 3.2 模型管理
- [ ] 权重下载（交互式 + 命令行）
- [ ] 本地模型注册表（已下载/版本/大小）
- [ ] 自动版本检测（LTX 2.0 vs 2.3）
- [ ] 多模型共存（distilled/dev/fp8/upcaler）
- [ ] 下载进度、断点续传（huggingface_hub 自带）

### 3.3 Pipeline 编排
- [ ] 统一 Task 数据模型
- [ ] 自适应 Pipeline 选择（根据分辨率/步数/资源自动选）
- [ ] 参数预设（fast / balanced / quality）
- [ ] 批量任务生成

### 3.4 后处理
- [ ] PiperSR 智能超分
- [ ] 模型内置 Spatial/Temporal Upscaler
- [ ] 视频增强（色彩、降噪）
- [ ] 音视频合成（ffmpeg）

### 3.5 硬件感知
- [ ] 检测芯片型号（M1/M2/M3/M4 / Pro/Max/Ultra）
- [ ] 检测可用 RAM
- [ ] 自动调整参数（分辨率/帧数/精度）
- [ ] 硬件层级预设（low/medium/high/ultra）

### 3.6 多任务并发
- [ ] 任务队列（asyncio.Queue）
- [ ] 可配置并发数（默认 1，最大由硬件决定）
- [ ] 权重共享加载（多个相同模型的 job 共享权重）
- [ ] 任务优先级
- [ ] 断点恢复（SQLite 持久化）

### 3.7 模型常驻模式（可选）
- [ ] 默认关闭：每次 job 加载→推理→卸载
- [ ] 可选开启：Warm Helper 子进程常驻模型
- [ ] 常驻模式下的 idle timeout 自动退出
- [ ] 常驻模式内存监控

## 4. 项目结构

```
JianDou-video/
├── backend/
│   ├── jiandou/
│   │   ├── __init__.py
│   │   │
│   │   ├── engine/                    # 核心推理层
│   │   │   ├── __init__.py
│   │   │   ├── session.py             # 推理会话（加载/卸载/推理）
│   │   │   ├── resident.py            # 常驻子进程管理（可选）
│   │   │   └── batch.py               # 批量推理（共享权重）
│   │   │
│   │   ├── manager/                   # 模型管理
│   │   │   ├── __init__.py
│   │   │   ├── download.py            # HuggingFace 下载
│   │   │   ├── registry.py            # 本地模型注册表
│   │   │   └── versions.py            # 权重文件版本检测
│   │   │
│   │   ├── pipeline/                  # 流水线调度
│   │   │   ├── __init__.py
│   │   │   ├── task.py                # Task/Job 数据模型
│   │   │   ├── runner.py              # 任务执行器
│   │   │   ├── queue.py               # 任务队列（SQLite + asyncio）
│   │   │   ├── progress.py            # 进度事件
│   │   │   └── presets.py             # 参数预设
│   │   │
│   │   ├── post/                      # 后处理
│   │   │   ├── __init__.py
│   │   │   ├── upscale.py             # 超分（PiperSR + 模型内置）
│   │   │   ├── enhance.py             # 视频增强
│   │   │   └── compose.py             # 音视频合成
│   │   │
│   │   ├── hardware/                  # 硬件感知
│   │   │   ├── __init__.py
│   │   │   ├── detect.py              # 芯片/RAM 检测
│   │   │   └── tier.py                # 层级 → 参数自动调整
│   │   │
│   │   ├── api/                       # REST API
│   │   │   ├── __init__.py
│   │   │   ├── app.py                 # FastAPI 应用入口
│   │   │   ├── deps.py                # 依赖注入
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── generate.py        # POST /api/v1/generate
│   │   │   │   ├── tasks.py           # GET/DELETE /api/v1/tasks/:id
│   │   │   │   ├── models.py          # GET /api/v1/models
│   │   │   │   ├── system.py          # GET /api/v1/system/info
│   │   │   │   └── ws.py              # WebSocket /ws/task/:id
│   │   │   ├── schemas.py             # Pydantic 请求/响应模型
│   │   │   └── middleware.py          # 限流、CORS、日志
│   │   │
│   │   ├── cli/                       # 命令行工具
│   │   │   ├── __init__.py
│   │   │   ├── main.py                # Typer app 入口
│   │   │   └── commands/
│   │   │       ├── generate.py        # jiandou generate "prompt"
│   │   │       ├── download.py        # jiandou download [--weights]
│   │   │       ├── serve.py           # jiandou serve [--port]
│   │   │       ├── queue.py           # jiandou queue [list|clear]
│   │   │       └── info.py            # jiandou info
│   │   │
│   │   ├── storage/                   # 持久化
│   │   │   ├── __init__.py
│   │   │   ├── job_store.py           # SQLite 任务记录
│   │   │   └── config.py              # 用户配置管理
│   │   │
│   │   └── utils/                     # 工具
│   │       ├── ffmpeg.py              # ffmpeg 调用封装
│   │       └── media.py               # 媒体文件工具
│   │
│   ├── tests/
│   ├── pyproject.toml
│   └── alembic/ (if needed)
│
├── frontend/                          # Vue 3 SPA
│   ├── public/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── stores/                    # Pinia
│   │   │   ├── generation.ts         # 生成任务状态
│   │   │   ├── models.ts             # 模型列表状态
│   │   │   └── system.ts             # 系统信息状态
│   │   ├── api/                       # API 客户端
│   │   │   ├── client.ts             # Axios 实例
│   │   │   ├── generate.ts
│   │   │   ├── tasks.ts
│   │   │   ├── models.ts
│   │   │   └── ws.ts                 # WebSocket 客户端
│   │   ├── views/
│   │   │   ├── HomeView.vue          # 首页 — 快速生成
│   │   │   ├── GenerateView.vue      # 高级生成面板
│   │   │   ├── QueueView.vue         # 任务队列管理
│   │   │   ├── ModelsView.vue        # 模型管理
│   │   │   ├── GalleryView.vue       # 历史作品画廊
│   │   │   └── SettingsView.vue      # 设置
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppHeader.vue
│   │   │   │   └── AppSidebar.vue
│   │   │   ├── generate/
│   │   │   │   ├── PromptInput.vue   # 提示词输入（含 Gemma 增强按钮）
│   │   │   │   ├── ModeSelector.vue  # T2V/I2V/FFLF/Extend/A2V
│   │   │   │   ├── ImageUpload.vue   # I2V 图片上传+裁剪
│   │   │   │   ├── ParamPanel.vue    # 参数面板（preset 快捷切换）
│   │   │   │   └── GenerateButton.vue
│   │   │   ├── queue/
│   │   │   │   ├── QueueList.vue     # 任务列表
│   │   │   │   ├── QueueCard.vue     # 单个任务卡片（进度/预览/操作）
│   │   │   │   └── ProgressBar.vue   # 进度条（step/total + 预览帧）
│   │   │   ├── gallery/
│   │   │   │   ├── VideoGrid.vue     # 视频网格
│   │   │   │   ├── VideoCard.vue     # 视频卡片（播放/下载/删除）
│   │   │   │   └── VideoPlayer.vue   # 视频播放器
│   │   │   ├── models/
│   │   │   │   ├── ModelList.vue     # 已下载模型列表
│   │   │   │   └── ModelDownload.vue # 模型下载对话框
│   │   │   └── common/
│   │   │       ├── SystemInfo.vue    # 硬件信息栏（RAM/芯片/tier）
│   │   │       └── Notification.vue  # 通知组件
│   │   └── types/                     # TypeScript 类型
│   │       ├── task.ts
│   │       ├── model.ts
│   │       └── system.ts
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── tailwind.config.js
│
├── config/
│   ├── default.yaml                   # 默认配置
│   └── presets/
│       ├── fast.yaml                  # 快速预览预设
│       ├── balanced.yaml              # 平衡质量预设
│       └── quality.yaml               # 高质量预设
│
├── plan.md                            # 本文件
├── README.md
└── .gitignore
```

## 5. 核心数据模型

### 5.1 Task（任务）

```python
@dataclass
class Task:
    id: str                          # UUID
    mode: TaskMode                   # t2v | i2v | fflf | extend | a2v
    status: TaskStatus               # pending | running | done | failed | cancelled
    priority: int = 0

    # 输入
    prompt: str
    negative_prompt: str = ""
    image_path: str | None = None    # i2v/fflf
    audio_path: str | None = None    # a2v
    keyframes: list[Keyframe] | None = None  # fflf

    # 参数
    duration: float = 5.0            # 秒
    width: int = 768
    height: int = 512
    fps: int = 24
    steps: int = 8
    cfg: float = 2.0
    seed: int = -1                   # -1 = 随机
    preset: str = "balanced"         # fast | balanced | quality

    # 引擎参数
    model_version: str = "2.3"       # 2.0 | 2.3
    pipeline: str = "auto"           # auto | distilled | one-stage | two-stage
    fp16: bool = True
    low_memory: bool = False

    # 后处理
    upscale: str = "none"            # none | piper | model | both
    upscale_factor: float = 2.0
    generate_audio: bool = False
    audio_prompt: str = ""

    # 输出
    output_path: str | None = None
    preview_path: str | None = None  # 首帧预览
    metadata: dict = {}

    # 时间戳
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: float = 0.0            # 0.0 - 1.0
    current_step: int = 0
    eta_seconds: float | None = None
    error_message: str | None = None
```

### 5.2 ModelEntry（模型注册表）

```python
@dataclass
class ModelEntry:
    name: str                        # "ltx-2.3-22b-distilled"
    repo: str                        # "Lightricks/LTX-2"
    filename: str                    # "ltx-2.3-22b-distilled.safetensors"
    local_path: str
    size_bytes: int
    version: str                     # "2.3"
    model_type: str                  # transformer | text_encoder | upscaler | vae
    downloaded: bool
    downloaded_at: datetime | None
    sha256: str | None
```

### 5.3 SystemInfo（硬件信息）

```python
@dataclass
class SystemInfo:
    chip: str                        # "Apple M4 Max"
    cpu_cores: int
    gpu_cores: int
    ram_gb: int
    ram_free_gb: int
    tier: str                        # low | medium | high | ultra
    max_resolution: tuple[int, int]
    max_frames: int
    supports_fp16: bool
    supports_audio: bool
    ffmpeg_available: bool
```

## 6. API 设计

### 6.1 REST Endpoints

```
POST   /api/v1/generate              # 创建生成任务
GET    /api/v1/tasks                  # 获取任务列表（分页、过滤）
GET    /api/v1/tasks/{id}             # 获取单个任务状态
DELETE /api/v1/tasks/{id}             # 取消/删除任务
POST   /api/v1/tasks/{id}/retry      # 重试失败任务
GET    /api/v1/tasks/{id}/output     # 下载输出视频

GET    /api/v1/models                 # 已下载模型列表
POST   /api/v1/models/download       # 触发模型下载
GET    /api/v1/models/download/{name}/progress  # 下载进度

GET    /api/v1/system/info           # 硬件信息
GET    /api/v1/system/config          # 当前配置
PATCH  /api/v1/system/config          # 更新配置

POST   /api/v1/prompt/enhance        # Gemma 提示词增强

WS     /ws/queue                     # 队列级别事件（全局）
WS     /ws/tasks/{id}                # 单个任务进度推送
```

### 6.2 WebSocket 事件

```json
{
  "type": "task.progress",
  "task_id": "uuid",
  "data": {
    "progress": 0.65,
    "current_step": 5,
    "total_steps": 8,
    "eta_seconds": 45.2,
    "preview_frame": "base64..."   // 可选的中间帧预览
  }
}
```

## 7. 多任务并发架构

```
                    ┌──────────────────────┐
                    │   asyncio.Queue       │
                    │   (priority queue)    │
                    └──────┬───────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼───┐   ┌───▼────┐   ┌───▼────┐
         │Worker 1│   │Worker 2│   │Worker 3│   (可配置 N 个)
         └────┬───┘   └───┬────┘   └───┬────┘
              │            │            │
    ┌─────────▼────────────▼────────────▼───────┐
    │          Weight Manager                    │
    │  ┌──────────────────────────────────┐     │
    │  │ refcount dict: path → count      │     │
    │  │ load if refcount==0              │     │
    │  │ unload when refcount drops to 0  │     │
    │  └──────────────────────────────────┘     │
    └──────────────────────────────────────────┘
```

- 每个 Worker 是一个 asyncio Task
- 相同模型版本的 Worker 通过 refcount 共享权重
- 非共享模型（如不同版本）各自加载
- 并发数受硬件限制：`max_workers = min(N, ram_gb // 30)`

### 权重生命周期

**默认模式（非常驻）**：
```
job 进入 → worker 获取 → load weights → inference → unload weights → job 完成
```

**常驻模式（可选开启）**：
```
启动 → resident helper 子进程启动 → 加载模型 → 常驻内存
job 进入 → 发给 helper stdin → 推理 → 返回结果
idle timeout → helper 自动退出
```

## 8. 前端路由

```
/                          # 首页 — 快速生成入口 + 系统状态概览
/generate                  # 高级生成面板（完整参数控制）
/generate/:taskId          # 单个任务详情 + 进度
/queue                     # 任务队列管理（批量操作）
/gallery                   # 历史作品画廊
/models                    # 模型下载/管理
/settings                  # 全局设置
```

## 9. 实施阶段

### Phase 1 — 骨架搭建（预计 2-3 天）
- [ ] 初始化项目结构（monorepo: backend + frontend）
- [ ] `pyproject.toml` + 依赖管理（uv）
- [ ] LTX-2-MLX 作为 git submodule
- [ ] Vue 3 + Vite 项目初始化
- [ ] 配置管理（YAML + pydantic-settings）
- [ ] CLI 入口框架（Typer）

### Phase 2 — 核心引擎封装（预计 3-4 天）
- [ ] `engine/session.py` — 推理会话封装
- [ ] `engine/resident.py` — 常驻子进程（可选）
- [ ] `engine/batch.py` — 批量推理
- [ ] `manager/download.py` — 权重下载
- [ ] `manager/registry.py` — 本地注册表
- [ ] `hardware/detect.py` + `tier.py` — 硬件检测

### Phase 3 — 任务系统（预计 2-3 天）
- [ ] `pipeline/task.py` — Task 数据模型
- [ ] `pipeline/queue.py` — 异步任务队列
- [ ] `pipeline/runner.py` — 任务执行器
- [ ] `pipeline/progress.py` — 进度事件
- [ ] `storage/job_store.py` — SQLite 持久化

### Phase 4 — API 服务（预计 2-3 天）
- [ ] FastAPI 应用骨架
- [ ] REST endpoints（生成、任务、模型、系统）
- [ ] WebSocket 进度推送
- [ ] Schemas + 自动文档（Swagger）
- [ ] 中间件（CORS、限流）

### Phase 5 — CLI 工具（预计 1-2 天）
- [ ] `jiandou generate` — 命令行生成
- [ ] `jiandou download` — 权重下载
- [ ] `jiandou serve` — 启动 API 服务
- [ ] `jiandou info` — 系统信息

### Phase 6 — Vue 前端（预计 4-5 天）
- [ ] 布局框架（Header + Sidebar + Router）
- [ ] 首页 — Dashboard 概览
- [ ] 生成面板 — 完整参数控制
- [ ] 任务队列视图 — 实时进度
- [ ] 作品画廊 — 历史视频浏览+播放
- [ ] 模型管理页 — 下载/查看
- [ ] WebSocket 实时更新集成
- [ ] 响应式适配

### Phase 7 — 后处理 + 高级特性（预计 2-3 天）
- [ ] `post/upscale.py` — PiperSR + 模型内置上采样
- [ ] `post/enhance.py` — 视频增强
- [ ] `post/compose.py` — ffmpeg 音视频合成
- [ ] 提示词增强（Gemma 润色）
- [ ] 参数预设系统

### Phase 8 — 测试 + 文档（预计 1-2 天）
- [ ] 后端单元测试
- [ ] API 集成测试
- [ ] CLI E2E 测试
- [ ] README + API 文档

## 10. 风险与注意事项

- **内存管理**: LTX 2.3 模型 ~46GB，Gemma ~25GB，需要严格的加载/卸载策略
- **MLX 版本锁定**: Phosphene 发现 MLX 0.31.2 有 vocoder 衰减 bug，需要锁定已验证版本
- **并发安全**: MLX 的 Metal 后端不支持真正的并行推理，并发通过时间分片实现
- **断点续传**: 大文件下载（46GB）需要可靠的断点续传，huggingface_hub 自带支持
- **macOS 限制**: 需要 macOS 14+，仅 Apple Silicon，无 Intel/NVIDIA 支持
