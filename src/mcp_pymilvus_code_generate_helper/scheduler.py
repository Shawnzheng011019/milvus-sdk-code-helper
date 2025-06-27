#!/usr/bin/env python3
"""scheduler.py

Light-weight weekly scheduler that runs the documentation refresh pipeline in a
background daemon thread. Uses only the Python stdlib (threading + time) to
avoid external dependencies.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from doc_updater import update_documents

logger = logging.getLogger(__name__)

_ONE_WEEK_SECONDS = 7 * 24 * 60 * 60  # 604800


def _loop(milvus_uri: str, milvus_token: str, interval_seconds: int) -> None:
    """Internal worker function executed in a daemon thread."""
    logger.info("Weekly document refresh thread started (interval=%d s)", interval_seconds)
    while True:
        try:
            logger.info("Triggering scheduled documentation refresh …")
            update_documents(milvus_uri, milvus_token)
            logger.info("Scheduled documentation refresh finished successfully")
        except Exception as exc:
            logger.error("Scheduled documentation refresh failed: %s", exc, exc_info=True)

        time.sleep(interval_seconds)


def start_weekly_scheduler(
    milvus_uri: str,
    milvus_token: str,
    interval_seconds: Optional[int] = None,
) -> None:
    """Start a background thread that refreshes docs every `interval_seconds`.

    If *interval_seconds* is None, defaults to one week.
    """

    seconds = interval_seconds or _ONE_WEEK_SECONDS
    t = threading.Thread(
        target=_loop, args=(milvus_uri, milvus_token, seconds), daemon=True
    )
    t.start()
    logger.info("Weekly scheduler thread started (daemon=%s)", t.daemon) 