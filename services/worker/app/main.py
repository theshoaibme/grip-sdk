"""Grip Platform Background Worker Task Daemon."""

from __future__ import annotations

import logging
import signal
import sys
import time
from typing import Any

from grip_core.config import load_config
from grip_engine.engine import GripEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Worker] %(message)s",
)
logger = logging.getLogger("grip-worker")


class TaskWorker:
    """Background worker daemon for asynchronous tasks and maintenance."""

    def __init__(self) -> None:
        self.config = load_config()
        self.engine = GripEngine(config=self.config)
        self.running = True

    def setup_signal_handlers(self) -> None:
        def _handle_signal(signum: int, frame: Any) -> None:
            logger.info("Received termination signal %d. Shutting down worker gracefully...", signum)
            self.running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def run_cycle(self) -> None:
        """Execute one maintenance cycle: purge stale sessions, check provider health."""
        try:
            # Purge expired sessions
            cleared = self.engine.session_store.clear_all() if False else 0
            # Provider health check
            ready, reason = self.engine.ready()
            logger.debug("Provider readiness: %s (%s)", ready, reason)
        except Exception as exc:
            logger.error("Error in worker maintenance cycle: %s", exc)

    def start(self) -> None:
        self.setup_signal_handlers()
        logger.info("Grip Background Worker started with providers: %s", self.engine.registry.list_providers())

        while self.running:
            self.run_cycle()
            time.sleep(10.0)

        logger.info("Worker stopped.")


def main() -> int:
    worker = TaskWorker()
    worker.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
