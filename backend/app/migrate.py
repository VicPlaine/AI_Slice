"""数据库迁移管理工具

提供编程方式运行 Alembic 迁移的能力，可在应用启动时或 CLI 中使用。

用法:
    # 应用启动时自动迁移到最新版本
    python -m app.migrate

    # 或在代码中调用
    from app.migrate import run_migrations
    run_migrations()
"""

import logging
import os
import sys

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

# 项目根目录（backend/）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_alembic_config() -> Config:
    """构建 Alembic Config 对象，指向正确的 alembic.ini"""
    ini_path = os.path.join(BASE_DIR, "alembic.ini")
    config = Config(ini_path)
    # 确保 script_location 是绝对路径
    config.set_main_option(
        "script_location", os.path.join(BASE_DIR, "alembic")
    )
    return config


def run_migrations(revision: str = "head") -> None:
    """运行迁移到指定版本（默认最新）"""
    config = get_alembic_config()
    logger.info("正在运行数据库迁移 -> %s", revision)
    command.upgrade(config, revision)
    logger.info("数据库迁移完成")


def create_migration(message: str, autogenerate: bool = True) -> None:
    """创建新的迁移脚本

    Args:
        message: 迁移描述，如 'add_user_avatar_field'
        autogenerate: 是否自动检测 ORM 模型变更
    """
    config = get_alembic_config()
    command.revision(config, message=message, autogenerate=autogenerate)
    logger.info("已创建迁移脚本: %s", message)


def rollback(steps: int = 1) -> None:
    """回滚指定步数的迁移"""
    config = get_alembic_config()
    target = f"-{steps}"
    logger.warning("正在回滚 %d 步迁移", steps)
    command.downgrade(config, target)
    logger.info("迁移回滚完成")


def show_current() -> None:
    """显示当前数据库迁移版本"""
    config = get_alembic_config()
    command.current(config, verbose=True)


def show_history() -> None:
    """显示迁移历史"""
    config = get_alembic_config()
    command.history(config, verbose=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"

    if action == "upgrade":
        run_migrations()
    elif action == "current":
        show_current()
    elif action == "history":
        show_history()
    elif action == "rollback":
        steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        rollback(steps)
    elif action == "create":
        if len(sys.argv) < 3:
            print("用法: python -m app.migrate create <migration_message>")
            sys.exit(1)
        create_migration(sys.argv[2])
    else:
        print(f"未知操作: {action}")
        print("可用操作: upgrade, current, history, rollback, create")
        sys.exit(1)
