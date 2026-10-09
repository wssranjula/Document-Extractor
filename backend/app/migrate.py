import os
import time

from alembic import command
from alembic.config import Config

from app.config import BACKEND_ROOT


def upgrade_db() -> None:
    if os.environ.get("SKIP_MIGRATIONS") == "1":
        return
    last_error: Exception | None = None
    for _ in range(10):
        try:
            config = Config(str(BACKEND_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
            command.upgrade(config, "head")
            return
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    if last_error is not None:
        raise last_error
