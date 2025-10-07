from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import AsyncIterator, Callable

from exo.shared.types.memory import Memory
from exo.shared.types.models import ModelId, ModelMetadata
from exo.shared.types.worker.shards import (
    PartitionStrategy,
    PipelineShardMetadata,
    ShardMetadata,
)
from exo.worker.download.download_utils import RepoDownloadProgress


# TODO: the PipelineShardMetadata getting reinstantiated is a bit messy. Shoudl this be a classmethod?
class ShardDownloader(ABC):
    @abstractmethod
    async def ensure_shard(
        self, shard: ShardMetadata, config_only: bool = False
    ) -> Path:
        """
        Ensures that the shard is downloaded.
        Does not allow multiple overlapping downloads at once.
        If you try to download a Shard which overlaps a Shard that is already being downloaded,
        the download will be cancelled and a new download will start.

        Args:
            shard (Shard): The shard to download.
            inference_engine_name (str): The inference engine used on the node hosting the shard
        """

    @abstractmethod
    def on_progress(
        self, callback: Callable[[ShardMetadata, RepoDownloadProgress], None]
    ) -> None:
        pass

    @abstractmethod
    async def get_shard_download_status(
        self,
    ) -> AsyncIterator[tuple[Path, RepoDownloadProgress]]:
        """Get the download status of shards.

        Yields:
            tuple[Path, RepoDownloadProgress]: The path and progress of a shard download.
        """
        yield (
            Path("/tmp/noop_shard"),
            RepoDownloadProgress(
                repo_id="noop",
                repo_revision="noop",
                shard=PipelineShardMetadata(
                    model_meta=ModelMetadata(
                        model_id=ModelId("noop"),
                        pretty_name="noope",
                        storage_size=Memory.from_bytes(0),
                        n_layers=1,
                    ),
                    partition_strategy=PartitionStrategy.pipeline,
                    device_rank=0,
                    world_size=1,
                    start_layer=0,
                    end_layer=1,
                    n_layers=1,
                ),
                completed_files=0,
                total_files=0,
                downloaded_bytes=0,
                downloaded_bytes_this_session=0,
                total_bytes=0,
                overall_speed=0,
                overall_eta=timedelta(seconds=0),
                status="complete",
            ),
        )

    @abstractmethod
    async def get_shard_download_status_for_shard(
        self, shard: ShardMetadata
    ) -> RepoDownloadProgress: ...


class NoopShardDownloader(ShardDownloader):
    async def ensure_shard(
        self, shard: ShardMetadata, config_only: bool = False
    ) -> Path:
        return Path("/tmp/noop_shard")

    def on_progress(
        self, callback: Callable[[ShardMetadata, RepoDownloadProgress], None]
    ) -> None:
        pass

    async def get_shard_download_status(
        self,
    ) -> AsyncIterator[tuple[Path, RepoDownloadProgress]]:
        yield (
            Path("/tmp/noop_shard"),
            RepoDownloadProgress(
                repo_id="noop",
                repo_revision="noop",
                shard=PipelineShardMetadata(
                    model_meta=ModelMetadata(
                        model_id=ModelId("noop"),
                        pretty_name="noope",
                        storage_size=Memory.from_bytes(0),
                        n_layers=1,
                    ),
                    partition_strategy=PartitionStrategy.pipeline,
                    device_rank=0,
                    world_size=1,
                    start_layer=0,
                    end_layer=1,
                    n_layers=1,
                ),
                completed_files=0,
                total_files=0,
                downloaded_bytes=0,
                downloaded_bytes_this_session=0,
                total_bytes=0,
                overall_speed=0,
                overall_eta=timedelta(seconds=0),
                status="complete",
            ),
        )

    async def get_shard_download_status_for_shard(
        self, shard: ShardMetadata
    ) -> RepoDownloadProgress:
        return RepoDownloadProgress(
            repo_id="noop",
            repo_revision="noop",
            shard=shard,
            completed_files=0,
            total_files=0,
            downloaded_bytes=0,
            downloaded_bytes_this_session=0,
            total_bytes=0,
            overall_speed=0,
            overall_eta=timedelta(seconds=0),
            status="complete",
        )
