from __future__ import annotations

from pathlib import Path

from app.adapters.llm import DisabledLLMProvider, LLMProvider, StaticLLMProvider
from app.adapters.object_storage import InMemoryObjectStorage, LocalFilesystemObjectStorage, ObjectStorage
from app.adapters.queue import InMemoryQueueAdapter, QueueAdapter, RocketMQQueueAdapter
from app.core.config import LLMSettings, ObjectStorageSettings, QueueSettings, get_settings


def build_object_storage(settings: ObjectStorageSettings | None = None) -> ObjectStorage:
    storage_settings = settings or get_settings().object_storage
    if storage_settings.provider == "memory":
        return InMemoryObjectStorage()
    if storage_settings.provider == "local":
        if storage_settings.local_root is None:
            raise ValueError("OBJECT_STORAGE_LOCAL_ROOT is required when provider is 'local'.")
        return LocalFilesystemObjectStorage(Path(storage_settings.local_root))
    raise ValueError(f"Unsupported object storage provider: {storage_settings.provider}")


def build_queue_adapter(settings: QueueSettings | None = None) -> QueueAdapter:
    queue_settings = settings or get_settings().queue
    if queue_settings.provider == "memory":
        return InMemoryQueueAdapter()
    if queue_settings.provider == "rocketmq":
        if not queue_settings.url:
            raise ValueError("QUEUE_URL is required when provider is 'rocketmq'.")
        return RocketMQQueueAdapter(queue_settings.url)
    raise ValueError(f"Unsupported queue provider: {queue_settings.provider}")


def build_llm_provider(settings: LLMSettings | None = None) -> LLMProvider:
    llm_settings = settings or get_settings().llm
    if llm_settings.provider in {"disabled", "none"}:
        return DisabledLLMProvider()
    if llm_settings.provider == "static":
        return StaticLLMProvider()
    raise ValueError(f"Unsupported LLM provider: {llm_settings.provider}")
