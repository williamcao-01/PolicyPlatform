from __future__ import annotations

import os
import signal
import time

from app.core.config import get_settings
from app.services.adapters import build_queue_adapter
from app.adapters.queue import QueueAdapter
from app.services.tasks import TaskService, task_service


class Worker:
    def __init__(
        self,
        *,
        poll_interval_seconds: float = 2.0,
        tasks: TaskService | None = None,
        queue: QueueAdapter | None = None,
    ) -> None:
        self.settings = get_settings()
        self.queue = queue or build_queue_adapter(self.settings.queue)
        self.topic = self.settings.queue.default_topic
        self.tasks = tasks or task_service
        self.poll_interval_seconds = poll_interval_seconds
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run_forever(self) -> None:
        while self._running:
            processed = self.drain_once()
            if not processed:
                time.sleep(self.poll_interval_seconds)

    def drain_once(self, *, max_messages: int = 5) -> int:
        messages = self.queue.consume(self.topic, max_messages=max_messages)
        for message in messages:
            task_id = str(message.payload.get("task_id") or "")
            if not task_id:
                self.queue.ack(message)
                continue
            try:
                self.tasks.mark_running(task_id)
                self.tasks.mark_succeeded(
                    task_id,
                    {
                        "task_id": task_id,
                        "status": "succeeded",
                        "summary": "Worker placeholder completed queue delivery. Skill execution wiring is the next step.",
                    },
                )
                self.queue.ack(message)
            except Exception as exc:
                self.tasks.mark_failed(task_id, str(exc))
        return len(messages)


def main() -> None:
    worker = Worker(poll_interval_seconds=float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2")))

    def stop_worker(*_: object) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)
    worker.run_forever()


if __name__ == "__main__":
    main()
