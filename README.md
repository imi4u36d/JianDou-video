# JianDou-video

全栈视频生成平台，基于 MLX 的 LTX 2.3 模型在 Apple Silicon 上进行 AI 视频生成。

## 系统要求

- macOS 14+ (Apple Silicon M1/M2/M3/M4/M5)
- 16GB+ RAM (推荐 64GB+)
- Python 3.11+
- Node.js 20+

## 快速开始

```bash
# 克隆仓库（含子模块）
git clone --recurse-submodules <repo-url>
cd JianDou-video

# 安装后端依赖
cd backend && uv sync

# 安装前端依赖
cd frontend && npm install && npm run build

# 启动 API 服务
cd ../backend && uv run jiandou serve start

# 或直接命令行生成
uv run jiandou generate t2v "a beautiful sunset"
```

## 项目结构

```
JianDou-video/
├── backend/              # Python 后端 (FastAPI + Typer + Rich)
│   ├── jiandou/
│   │   ├── engine/       # 推理引擎封装 (session/resident/batch)
│   │   ├── manager/      # 模型管理 (download/registry/versions)
│   │   ├── pipeline/     # 任务流水线 (task/queue/runner/progress/presets)
│   │   ├── post/         # 后处理 (upscale/enhance/compose)
│   │   ├── hardware/     # 硬件感知 (detect/tier)
│   │   ├── api/          # REST API + WebSocket
│   │   ├── cli/          # 命令行工具
│   │   └── storage/      # SQLite 持久化
│   └── tests/
├── frontend/             # Vue 3 SPA
│   └── src/
│       ├── views/        # 6 个页面
│       ├── components/   # UI 组件
│       ├── stores/       # Pinia 状态管理
│       ├── api/          # HTTP + WebSocket 客户端
│       └── types/        # TypeScript 类型
├── config/               # YAML 配置
│   ├── default.yaml
│   └── presets/          # fast/balanced/quality
└── lib/                  # Git submodules
    └── LTX-2-MLX/        # 推理引擎
```

## CLI 命令

```bash
jiandou generate t2v "prompt"    # 文本到视频
jiandou generate i2v image.jpg   # 图片到视频
jiandou download list            # 列出可下载模型
jiandou download pull Lightricks/LTX-2  # 下载模型
jiandou serve start              # 启动 API 服务
jiandou info system              # 系统硬件信息
jiandou queue list               # 查看任务队列
```

## API 端点

```
POST   /api/v1/generate              # 创建生成任务
GET    /api/v1/tasks                 # 任务列表（分页/过滤）
GET    /api/v1/tasks/{id}            # 任务详情
DELETE /api/v1/tasks/{id}            # 取消/删除
POST   /api/v1/tasks/{id}/retry     # 重试失败任务
GET    /api/v1/tasks/{id}/output    # 下载输出视频

GET    /api/v1/models                # 已下载模型
POST   /api/v1/models/download      # 触发下载
GET    /api/v1/models/available      # 远端可用文件

GET    /api/v1/system/info           # 硬件信息
GET    /api/v1/system/config         # 当前配置
PATCH  /api/v1/system/config         # 更新配置

POST   /api/v1/prompt/enhance        # 提示词增强

WS     /ws/queue                     # 全局队列事件
WS     /ws/tasks/{id}                # 单任务进度推送
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 推理引擎 | [LTX-2-MLX](https://github.com/Acelogic/LTX-2-MLX) (MLX) |
| 后端 | FastAPI + WebSocket + Typer + Rich |
| 任务队列 | asyncio.PriorityQueue + SQLite |
| 前端 | Vue 3 + Vite + Pinia + TypeScript |
| 配置 | YAML + pydantic-settings |
| 超分辨率 | PiperSR + 模型内置 Upscaler |

## License

MIT
