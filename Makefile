# ──────────────────────────────────────────────────
# AI Slice - 项目命令 Makefile (uv)
# ──────────────────────────────────────────────────
# 用法:
#   make dev                  # 启动 API 服务 (开发模式)
#   make db-upgrade           # 升级到最新版本
#   make db-create m="描述"   # 创建新迁移（自动检测模型变更）
#   make db-rollback          # 回滚 1 步
#   make db-current           # 查看当前版本
#   make db-history           # 查看迁移历史
#   make sync                 # 同步依赖
# ──────────────────────────────────────────────────

.PHONY: dev db-upgrade db-create db-rollback db-current db-history db-check sync

# 启动 API 开发服务器
dev:
	cd backend && uv run uvicorn app.main:app --reload --port 8001

# 同步依赖
sync:
	cd backend && uv sync

# 升级到最新版本
db-upgrade:
	cd backend && uv run alembic upgrade head

# 创建新迁移脚本（自动检测 ORM 模型变更）
# 用法: make db-create m="add_user_avatar_field"
db-create:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

# 回滚 1 步
db-rollback:
	cd backend && uv run alembic downgrade -1

# 查看当前数据库迁移版本
db-current:
	cd backend && uv run alembic current --verbose

# 查看迁移历史
db-history:
	cd backend && uv run alembic history --verbose

# 检查是否有未应用的迁移
db-check:
	cd backend && uv run alembic check
