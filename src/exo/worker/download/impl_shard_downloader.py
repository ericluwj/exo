import asyncio
from pathlib import Path
from typing import AsyncIterator, Callable, Dict, List, Optional

from exo.shared.models.model_cards import MODEL_CARDS
from exo.shared.models.model_meta import get_model_meta
from exo.shared.types.worker.shards import (
    PartitionStrategy,
    PipelineShardMetadata,
    ShardMetadata,
)
from exo.worker.download.download_utils import RepoDownloadProgress, download_shard
from exo.worker.download.shard_downloader import ShardDownloader


def exo_shard_downloader(max_parallel_downloads: int = 8) -> ShardDownloader:
    return SingletonShardDownloader(
        CachedShardDownloader(ResumableShardDownloader(max_parallel_downloads))
    )


async def build_base_shard(model_id: str) -> Optional[ShardMetadata]:
    model_meta = await get_model_meta(model_id)
    # print(f"build_base_shard {model_id=} {model_meta=}")
    return PipelineShardMetadata(
        model_meta=model_meta,
        partition_strategy=PartitionStrategy.pipeline,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=model_meta.n_layers,
        n_layers=model_meta.n_layers,
    )


async def build_full_shard(model_id: str) -> Optional[PipelineShardMetadata]:
    base_shard = await build_base_shard(model_id)
    if base_shard is None:
        return None
    return PipelineShardMetadata(
        model_meta=base_shard.model_meta,
        partition_strategy=base_shard.partition_strategy,
        device_rank=base_shard.device_rank,
        world_size=base_shard.world_size,
        start_layer=base_shard.start_layer,
        end_layer=base_shard.n_layers,
        n_layers=base_shard.n_layers,
    )


class SingletonShardDownloader(ShardDownloader):
    def __init__(self, shard_downloader: ShardDownloader):
        self.shard_downloader = shard_downloader
        self.active_downloads: Dict[ShardMetadata, asyncio.Task[Path]] = {}

    def on_progress(
        self, callback: Callable[[ShardMetadata, RepoDownloadProgress], None]
    ) -> None:
        self.shard_downloader.on_progress(callback)

    async def ensure_shard(
        self, shard: ShardMetadata, config_only: bool = False
    ) -> Path:
        if shard not in self.active_downloads:
            self.active_downloads[shard] = asyncio.create_task(
                self.shard_downloader.ensure_shard(shard, config_only)
            )
        try:
            return await self.active_downloads[shard]
        finally:
            if shard in self.active_downloads and self.active_downloads[shard].done():
                del self.active_downloads[shard]

    async def get_shard_download_status(
        self,
    ) -> AsyncIterator[tuple[Path, RepoDownloadProgress]]:
        async for path, status in self.shard_downloader.get_shard_download_status():
            yield path, status

    async def get_shard_download_status_for_shard(
        self, shard: ShardMetadata
    ) -> RepoDownloadProgress:
        return await self.shard_downloader.get_shard_download_status_for_shard(shard)


class CachedShardDownloader(ShardDownloader):
    def __init__(self, shard_downloader: ShardDownloader):
        self.shard_downloader = shard_downloader
        self.cache: Dict[tuple[str, ShardMetadata], Path] = {}

    def on_progress(
        self, callback: Callable[[ShardMetadata, RepoDownloadProgress], None]
    ) -> None:
        self.shard_downloader.on_progress(callback)

    async def ensure_shard(
        self, shard: ShardMetadata, config_only: bool = False
    ) -> Path:
        if (shard.model_meta.model_id, shard) in self.cache:
            # print(f"ensure_shard cache hit {shard=}")
            return self.cache[(shard.model_meta.model_id, shard)]

        # print(f"ensure_shard cache miss {shard=}")
        target_dir = await self.shard_downloader.ensure_shard(shard, config_only)
        self.cache[(shard.model_meta.model_id, shard)] = target_dir
        return target_dir

    async def get_shard_download_status(
        self,
    ) -> AsyncIterator[tuple[Path, RepoDownloadProgress]]:
        async for path, status in self.shard_downloader.get_shard_download_status():
            yield path, status

    async def get_shard_download_status_for_shard(
        self, shard: ShardMetadata
    ) -> RepoDownloadProgress:
        return await self.shard_downloader.get_shard_download_status_for_shard(shard)


class ResumableShardDownloader(ShardDownloader):
    def __init__(self, max_parallel_downloads: int = 8):
        self.max_parallel_downloads = max_parallel_downloads
        self.on_progress_callbacks: List[
            Callable[[ShardMetadata, RepoDownloadProgress], None]
        ] = []

    def on_progress_wrapper(
        self, shard: ShardMetadata, progress: RepoDownloadProgress
    ) -> None:
        for callback in self.on_progress_callbacks:
            callback(shard, progress)

    def on_progress(
        self, callback: Callable[[ShardMetadata, RepoDownloadProgress], None]
    ) -> None:
        self.on_progress_callbacks.append(callback)

    async def ensure_shard(
        self, shard: ShardMetadata, config_only: bool = False
    ) -> Path:
        allow_patterns = ["config.json"] if config_only else None

        # print(f"ensure_shard {shard=} {config_only=} {allow_patterns=}")
        target_dir, _ = await download_shard(
            shard,
            self.on_progress_wrapper,
            max_parallel_downloads=self.max_parallel_downloads,
            allow_patterns=allow_patterns,
        )
        return target_dir

    async def get_shard_download_status(
        self,
    ) -> AsyncIterator[tuple[Path, RepoDownloadProgress]]:
        # print("get_shard_download_status")
        async def _status_for_model(
            model_id: str,
        ) -> Optional[tuple[Path, RepoDownloadProgress]]:
            """Helper coroutine that builds the shard for a model and gets its download status."""
            shard = await build_full_shard(model_id)
            if shard is None:
                return None
            return await download_shard(
                shard, self.on_progress_wrapper, skip_download=True
            )

        # Kick off download status coroutines concurrently
        tasks = [
            asyncio.create_task(_status_for_model(model_card.model_id))
            for model_card in MODEL_CARDS.values()
        ]

        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result is None:
                    continue
                path, progress = result
                yield (path, progress)
            except Exception as e:
                print("Error downloading shard:", e)

    async def get_shard_download_status_for_shard(
        self, shard: ShardMetadata
    ) -> RepoDownloadProgress:
        _, progress = await download_shard(
            shard, self.on_progress_wrapper, skip_download=True
        )
        return progress
