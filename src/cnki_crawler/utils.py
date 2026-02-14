from __future__ import annotations

import logging
import random
import time

logger = logging.getLogger("cnki_crawler")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")


def random_delay(min_sec: float = 3.0, max_sec: float = 6.0) -> None:
    delay = random.uniform(min_sec, max_sec)
    logger.debug("等待 %.1f 秒...", delay)
    time.sleep(delay)
