"""导出接口：一键切片（浏览器端 FFmpeg）"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["export"])

# 一键切片功能在前端通过 FFmpeg.wasm 实现，无需后端路由
# 保留此文件以备后续扩展服务端导出能力
