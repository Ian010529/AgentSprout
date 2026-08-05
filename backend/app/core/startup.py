from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run_startup_maintenance() -> None:
    """Run infrastructure startup work before domain job recovery exists."""
    logger.info("Startup maintenance complete")
