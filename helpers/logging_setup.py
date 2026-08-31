from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def configure_logging(*, verbose: bool = False, log_dir: str | Path = "logs") -> Path:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    log_file = path / f"tableau-bulk-add-{datetime.now():%Y%m%d-%H%M%S}.log"

    logger = logging.getLogger("tableau_bulk_add_users")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)
    return log_file
