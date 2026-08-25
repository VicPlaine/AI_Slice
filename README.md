# AI Slice

AI Slice 是一个面向直播回放、播客访谈和课程讲座的本地视频切片工作台。浏览器先从原视频提取轻量音频，后端调用语音识别和大语言模型生成切片方案，用户审核标题、发布文案和剪辑思路后，再从原视频批量导出 MP4 切片与 ZIP。

当前默认 AI 组合是：

- ASR：阿里云百炼千问录音文件识别
- LLM：阿里云百炼千问，通过 OpenAI 兼容接口调用
- 可选 ASR：Groq Whisper，仅在 `ASR_PROVIDER=groq` 时使用

`LLM_*` 变量是供应商无关的命名。以后切换其他 OpenAI 兼容模型时，只需更换接口地址、API Key 和模型名，无需修改业务代码。

## 三种分析模式

| 模式   | 标识           | 选择重点                 | Prompt 目标时长 |
| ---- | ------------ | -------------------- | ----------: |
| 直播回放 | `livestream` | 高能、互动、金句、干货、带货亮点     |   30 秒～3 分钟 |
| 播客访谈 | `podcast`    | 观点、人物故事、争议讨论、经验、情绪共鸣 |      1～4 分钟 |
| 课程讲座 | `lecture`    | 独立知识点、案例、总结、课堂问答     |     5～10 分钟 |

模型输出仍会经过后端时长上限、转录边界对齐和重叠去重，表中时长是 Prompt 目标，不是强制保证。

## 已实现能力

- 三种分析模式：直播回放、播客访谈、课程讲座
- 浏览器端 FFmpeg.wasm 抽取音频，分析阶段不上传完整视频
- 千问 ASR 句级时间戳转录，转录阶段显示估算进度
- 千问 LLM 分批分析、时间轴对齐、候选去重与打分
- 后台任务队列、SSE 实时进度、任务取消、重试、重命名和删除
- 每条切片生成标题、摘要、分类、传播力评分和推荐发布文案
- 标题建议换一批并替换主标题
- 发布文案换一批并替换当前文案
- 结构化剪辑思路生成
- 双导出链路：小文件浏览器导出，大文件本机原生 FFmpeg 导出
- 任务时间统一按东八区展示

## 系统架构

```text
浏览器（React + TypeScript）
  ├─ FFmpeg.wasm 提取 MP3
  ├─ 上传音频、创建任务、订阅 SSE
  ├─ 展示并编辑切片方案
  └─ 小文件：FFmpeg.wasm 逐片输出并流式写入 ZIP
           │ HTTP / SSE
           ▼
FastAPI
  ├─ REST API 与本地文件接收
  ├─ 数据库任务 Runner（并发数由 WORKER_CONCURRENCY 控制）
  ├─ 千问 ASR / OpenAI 兼容 LLM 编排
  ├─ PostgreSQL 持久化 Task / Clip
  └─ 大文件：接收用户重新选择的原视频，调用本机 FFmpeg 后打包 ZIP
           │ HTTPS
           ▼
阿里云百炼（ASR + LLM）
```

分析阶段上传的是提取后的音频。大文件导出时完整视频会传给运行在 `localhost` 的 FastAPI，仅用于本机原生 FFmpeg 切片；它不会被发送到云端 AI。部署到远程服务器前应重新评估该链路的隐私、流量和存储策略。

## 技术栈

| 层    | 主要技术                                                    |
| ---- | ------------------------------------------------------- |
| 前端   | React 19、TypeScript、Vite、Axios、FFmpeg.wasm、fflate       |
| 后端   | Python 3.11+、FastAPI、SQLAlchemy async、Pydantic Settings |
| 数据库  | PostgreSQL 16、Alembic                                   |
| AI   | DashScope Qwen ASR、OpenAI 兼容 Chat Completions           |
| 媒体处理 | 浏览器 FFmpeg.wasm、本机原生 FFmpeg/ffprobe                     |

## 快速启动（Windows）

前置环境：Docker Desktop、Python 3.11+、`uv`、Node.js 20.19+ 或 22.12+、npm，以及可用的百炼 API Key。大文件本机导出还需要原生 FFmpeg/ffprobe。

### 1. 启动 PostgreSQL

推荐使用项目内的 Docker Compose。宿主机端口为 `5433`：

```powershell
cd D:\Workspace\Work\AI_Slice\ai-slice
docker compose up -d postgres
docker compose ps
```

### 2. 配置后端

```powershell
cd D:\Workspace\Work\AI_Slice\ai-slice\backend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

编辑 `backend/.env`，至少填写：

```dotenv
DATABASE_URL=postgresql+asyncpg://slice:slice_dev@localhost:5433/ai_slice

LLM_API_KEY=在这里填写你的百炼_API_Key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

ASR_PROVIDER=dashscope
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1
DASHSCOPE_ASR_MODEL=qwen-audio-3.0-asr-flash-filetrans

FFMPEG_BIN_DIR=D:/tools/ffmpeg/bin
```

`DASHSCOPE_API_KEY` 留空时自动复用 `LLM_API_KEY`。如果使用百炼业务空间专属地址，可将 `LLM_BASE_URL` 和 `DASHSCOPE_BASE_URL` 换成该空间提供的对应地址。

API Key 只应存在于本机 `backend/.env`，不要填写进 `.env.example`、Markdown、前端代码或提交记录。

### 3. 初始化并启动后端

```powershell
cd D:\Workspace\Work\AI_Slice\ai-slice\backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8001
```

验证：打开 <http://localhost:8001/api/health>，应返回 `status: ok`。

### 4. 初始化并启动前端

新开 PowerShell：

```powershell
cd D:\Workspace\Work\AI_Slice\ai-slice\frontend
npm install
npm run dev
```

本机打开 <http://127.0.0.1:5173>；当前公司网段内可通过 <http://192.168.110.221:5173> 访问。Vite 会把 `/api` 代理到只在本机监听的 `http://localhost:8001`，并发送 FFmpeg.wasm 所需的 COOP/COEP 响应头。

### 5. 后续一键启动

依赖、`.env` 和数据库迁移完成后，可在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1
```

脚本会检查 PostgreSQL `5433`、停止由脚本管理的旧进程、释放 `8001/5173`，然后在后台启动前后端并把日志写入 `logs/`。它不会安装依赖、启动数据库或执行 Alembic 迁移；代码包含新迁移时仍需先运行 `uv run alembic upgrade head`。

前端监听 `0.0.0.0:5173` 以支持内网访问；后端仍只监听 `127.0.0.1:8001`。Windows 防火墙规则应只向公司网段开放 5173，不要开放 8001。

首次配置时，以管理员身份打开 PowerShell，仅向当前公司子网 `192.168.108.0/22` 放行前端端口：

```powershell
New-NetFirewallRule -Name "AI-Slice-LAN-5173" -DisplayName "AI Slice LAN 5173" -Direction Inbound -Action Allow -Protocol TCP -LocalAddress 192.168.110.221 -LocalPort 5173 -RemoteAddress 192.168.108.0/22 -Profile Any
```

该命令不开放后端 `8001`、PostgreSQL `5433`，也不允许公司子网之外的来源访问。

停止脚本管理的服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1 -StopOnly
```

更完整的首次安装与排错见 [项目启动文档.md](./项目启动文档.md)。

## 环境变量

| 变量                                    |          必需 | 默认/示例                     | 说明                                  |
| ------------------------------------- | ----------: | ------------------------- | ----------------------------------- |
| `DATABASE_URL`                        |           是 | PostgreSQL 5433           | asyncpg 连接串                         |
| `LLM_API_KEY`                         |           是 | 空                         | OpenAI 兼容 LLM 凭证；也可供千问 ASR 复用       |
| `LLM_BASE_URL`                        |           是 | DashScope compatible-mode | OpenAI 兼容接口根地址                      |
| `LLM_MODEL`                           |           是 | `qwen-plus`               | 模型 ID                               |
| `ASR_PROVIDER`                        |           是 | `dashscope`               | `dashscope` 或 `groq`                |
| `DASHSCOPE_API_KEY`                   |           否 | 空                         | 留空复用 `LLM_API_KEY`                  |
| `DASHSCOPE_BASE_URL`                  | DashScope 时 | DashScope API             | 原生 ASR 接口根地址                        |
| `DASHSCOPE_ASR_MODEL`                 | DashScope 时 | 文件转写模型                    | 必须拥有模型访问权限                          |
| `DASHSCOPE_ASR_POLL_INTERVAL_SECONDS` |           否 | `3`                       | ASR 查询间隔                            |
| `DASHSCOPE_ASR_TIMEOUT_SECONDS`       |           否 | `7200`                    | ASR 最大等待时间                          |
| `GROQ_API_KEY`                        |      Groq 时 | 空                         | Groq 凭证                             |
| `GROQ_ASR_MODEL`                      |      Groq 时 | `whisper-large-v3-turbo`  | Groq ASR 模型                         |
| `GROQ_ASR_CHUNK_MINUTES`              |           否 | `25`                      | Groq 长音频分段长度                        |
| `TEMP_DIR`                            |           否 | `./tmp`                   | Pipeline 临时目录                       |
| `STORAGE_DIR`                         |           否 | `./storage`               | 音频和本地导出临时文件目录                       |
| `WORKER_CONCURRENCY`                  |           否 | `10`                      | 单个后端进程中的分析 Worker 数量                |
| `FFMPEG_BIN_DIR`                      |      大文件导出时 | 空                         | `ffmpeg`/`ffprobe` 所在目录；PATH 可用时可留空 |

修改 `.env` 后必须重启后端进程，因为配置在 Python 模块导入时加载。

## 核心流程

1. 用户选择场景与视频。
2. 浏览器用 FFmpeg.wasm 抽取单声道 MP3，并记录视频时长与 PTS 起始偏移。
3. 前端上传音频至 `/api/upload/audio`，然后用返回的本地路径创建任务。
4. 后台 Runner 领取 `pending` 任务。
5. ASR 生成带时间戳的转录段，任务总进度由 15% 推进至 60%。
6. LLM 按场景 Prompt 分析候选片段，总进度由 60% 推进至 90%。
7. 后端将 Clip 元数据写入 PostgreSQL，任务到达 100%。
8. 用户可替换标题/文案、生成剪辑思路，并重新选择同一原视频执行导出。

详细数据边界见 [端到端数据流转.md](./端到端数据流转.md)，接口时序见 [前后端交互逻辑.md](./前后端交互逻辑.md)。

## 导出策略

前端会按预计输出体积选择导出实现：

- 浏览器导出：预计全部切片小于 256 MB，且最大单片小于 128 MB；若缺少时长元数据，则原文件小于 512 MB。
- 本机原生导出：达到上述任一阈值。视频以流式 multipart 方式传给本机后端，FFmpeg 逐片生成文件，Python `zipfile` 以 ZIP64 打包，下载后清理临时目录。

浏览器导出在失败或取消时会终止当前 FFmpeg.wasm 实例，下次导出重新创建；切片文件读出后立即写入 ZIP 并从虚拟文件系统删除，避免同时保留全部视频数组。

## 主要 API

| 方法       | 路径                                     | 用途                       |
| -------- | -------------------------------------- | ------------------------ |
| `GET`    | `/api/health`                          | 健康检查                     |
| `POST`   | `/api/upload/audio`                    | 上传分析音频                   |
| `POST`   | `/api/upload/video`                    | 完整视频上传兼容入口；当前上传页不调用      |
| `POST`   | `/api/tasks`                           | 创建任务                     |
| `GET`    | `/api/tasks`                           | 任务列表                     |
| `GET`    | `/api/tasks/{id}`                      | 任务和切片详情                  |
| `GET`    | `/api/tasks/{id}/progress`             | SSE 进度                   |
| `POST`   | `/api/tasks/{id}/cancel`               | 取消分析任务                   |
| `POST`   | `/api/tasks/{id}/retry`                | 清理旧结果并重试                 |
| `PATCH`  | `/api/tasks/{id}/rename`               | 重命名任务                    |
| `DELETE` | `/api/tasks/{id}`                      | 删除任务及本地数据                |
| `GET`    | `/api/tasks/{id}/clips`                | 单独查询任务切片列表               |
| `GET`    | `/api/clips/{id}/download`             | 下载存在 `file_key` 的历史服务端切片 |
| `POST`   | `/api/clips/{id}/viral-titles`         | 生成 5 个标题建议               |
| `PATCH`  | `/api/clips/{id}/title`                | 替换主标题                    |
| `POST`   | `/api/clips/{id}/caption-suggestions`  | 生成 3 个发布文案候选             |
| `PATCH`  | `/api/clips/{id}/caption`              | 替换当前发布文案                 |
| `POST`   | `/api/clips/{id}/editing-guide`        | 生成并保存剪辑思路                |
| `POST`   | `/api/local-exports/tasks/{id}`        | 创建大文件本机导出任务              |
| `GET`    | `/api/local-exports/{job_id}`          | 查询导出进度                   |
| `GET`    | `/api/local-exports/{job_id}/download` | 下载 ZIP 并清理               |
| `DELETE` | `/api/local-exports/{job_id}`          | 取消本机导出                   |

交互式 API 文档：<http://localhost:8001/docs>。

## 测试与构建

```powershell
cd D:\Workspace\Work\AI_Slice\ai-slice\backend
uv run pytest

cd D:\Workspace\Work\AI_Slice\ai-slice\frontend
node --test tests/*.test.ts
npm run build
```

## 常见问题

- `Model.AccessDenied`：API Key 有效，但当前业务空间未开通所选 ASR/LLM 模型；在百炼控制台确认模型权限与免费额度。
- `ASR_RESPONSE_HAVE_NO_WORDS`：音轨中没有可识别人声，或浏览器提取的音频为空/静音。
- `Array buffer allocation failed`：浏览器 WASM 内存不足；当前版本会对大输出自动改用本机原生 FFmpeg。确认后端已重启且 `FFMPEG_BIN_DIR` 可用。
- 页面时间少 8 小时：当前前端会把后端无时区 UTC 时间按 `Asia/Shanghai` 格式化；若仍异常，先硬刷新并确认使用最新前端构建。
- `.env` 改了但没生效：停止并重新启动 Uvicorn。

## 文档导航

- [项目启动文档.md](./项目启动文档.md)：安装、配置、启动和排错
- [端到端数据流转.md](./端到端数据流转.md)：数据在浏览器、后端、数据库和云 AI 之间如何流动
- [前后端交互逻辑.md](./前后端交互逻辑.md)：接口、页面状态和异常处理
- [项目架构解读.md](./项目架构解读.md)：模块边界和关键设计取舍
- [直播切片自动剪辑 Agent 技术方案.md](./直播切片自动剪辑%20Agent%20技术方案.md)：现行技术方案、风险与演进计划

