from __future__ import annotations

import logging
import sys

from app.core.settings import Settings


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.setLevel(settings.logging.level)
    root.handlers = [handler]

    logging.getLogger("uvicorn.access").setLevel(settings.logging.uvicorn_access_level)
