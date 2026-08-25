from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.upload import router as upload_router
from app.api.tasks import router as tasks_router
from app.api.clips import router as clips_router
from app.api.export import router as export_router
from app.api.local_exports import router as local_exports_router
from app.services.task_runner import start_task_runner, stop_task_runner
from app.services.local_export import cleanup_stale_local_exports

app = FastAPI(
    title="AI Slice - 多场景视频切片工作台",
    description="上传直播、播客访谈或课程视频，AI 自动提取精彩片段并输出切片方案",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源（含局域网 IP）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload_router)
app.include_router(tasks_router)
app.include_router(clips_router)
app.include_router(export_router)
app.include_router(local_exports_router)


@app.on_event("startup")
async def startup_event():
    cleanup_stale_local_exports()
    await start_task_runner()


@app.on_event("shutdown")
async def shutdown_event():
    await stop_task_runner()


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ai-slice", "storage": "local"}
