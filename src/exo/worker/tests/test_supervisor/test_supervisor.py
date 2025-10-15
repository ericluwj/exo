import asyncio
from typing import Callable

import pytest

from exo.shared.openai_compat import FinishReason
from exo.shared.types.chunks import TokenChunk
from exo.shared.types.common import Host
from exo.shared.types.tasks import (
    ChatCompletionTask,
    ChatCompletionTaskParams,
    Task,
    TaskId,
)
from exo.shared.types.worker.common import InstanceId
from exo.shared.types.worker.shards import PipelineShardMetadata
from exo.worker.runner.runner_supervisor import RunnerSupervisor


@pytest.fixture
def user_message():
    """Override the default message to ask about France's capital"""
    return "What is the capital of France?"


@pytest.mark.asyncio
async def test_supervisor_single_node_response(
    pipeline_shard_meta: Callable[..., PipelineShardMetadata],
    hosts: Callable[..., list[Host]],
    chat_completion_task: Callable[[InstanceId, TaskId], Task],
):
    """Test that asking for the capital of France returns 'Paris' in the response"""
    model_shard_meta = pipeline_shard_meta(1, 0)
    instance_id = InstanceId()

    print(f"{model_shard_meta=}")

    supervisor = await RunnerSupervisor.create(
        model_shard_meta=model_shard_meta,
        hosts=hosts(1, offset=10),
    )

    try:
        full_response = ""
        stop_reason: FinishReason | None = None

        async for chunk in supervisor.stream_response(
            task=chat_completion_task(instance_id, TaskId())
        ):
            if isinstance(chunk, TokenChunk):
                full_response += chunk.text
                if chunk.finish_reason:
                    stop_reason = chunk.finish_reason

        # Case-insensitive check for Paris in the response
        assert "paris" in full_response.lower(), (
            f"Expected 'Paris' in response, but got: {full_response}"
        )
        assert stop_reason == "stop"

    finally:
        await supervisor.astop()


@pytest.mark.asyncio
async def test_supervisor_two_node_response(
    pipeline_shard_meta: Callable[..., PipelineShardMetadata],
    hosts: Callable[..., list[Host]],
    chat_completion_task: Callable[[InstanceId, TaskId], Task],
):
    """Test that asking for the capital of France returns 'Paris' in the response"""
    instance_id = InstanceId()

    async def create_supervisor(shard_idx: int) -> RunnerSupervisor:
        supervisor = await RunnerSupervisor.create(
            model_shard_meta=pipeline_shard_meta(2, shard_idx),
            hosts=hosts(2, offset=15),
        )
        return supervisor

    create_supervisor_0 = asyncio.create_task(create_supervisor(0))
    create_supervisor_1 = asyncio.create_task(create_supervisor(1))
    supervisor_0, supervisor_1 = await asyncio.gather(
        create_supervisor_0, create_supervisor_1
    )

    await asyncio.sleep(0.1)

    try:
        full_response_0 = ""
        full_response_1 = ""

        async def collect_response_0():
            nonlocal full_response_0
            async for chunk in supervisor_0.stream_response(
                task=chat_completion_task(instance_id, TaskId())
            ):
                if isinstance(chunk, TokenChunk):
                    full_response_0 += chunk.text

        async def collect_response_1():
            nonlocal full_response_1
            async for chunk in supervisor_1.stream_response(
                task=chat_completion_task(instance_id, TaskId())
            ):
                if isinstance(chunk, TokenChunk):
                    full_response_1 += chunk.text

        # Run both stream responses simultaneously
        _ = await asyncio.gather(collect_response_0(), collect_response_1())

        print(f"full_response_0: {full_response_0}")
        print(f"full_response_1: {full_response_1}")

        # Case-insensitive check for Paris in both responses
        assert "paris" in full_response_0.lower(), (
            f"Expected 'Paris' in response, but got: {full_response_0}"
        )
        assert "paris" in full_response_1.lower(), (
            f"Expected 'Paris' in response, but got: {full_response_1}"
        )

    finally:
        await supervisor_0.astop()
        await supervisor_1.astop()


@pytest.mark.asyncio
async def test_supervisor_early_stopping(
    pipeline_shard_meta: Callable[..., PipelineShardMetadata],
    hosts: Callable[..., list[Host]],
    chat_completion_task: Callable[[InstanceId, TaskId], Task],
):
    """Test that asking for the capital of France returns 'Paris' in the response"""
    model_shard_meta = pipeline_shard_meta(1, 0)
    instance_id = InstanceId()

    supervisor = await RunnerSupervisor.create(
        model_shard_meta=model_shard_meta,
        hosts=hosts(1, offset=10),
    )

    task = chat_completion_task(instance_id, TaskId())

    max_tokens = 50
    assert isinstance(task, ChatCompletionTask)
    print(f"chat_completion_task.task_params: {task.task_params}")
    assert isinstance(task.task_params, ChatCompletionTaskParams)
    task_params: ChatCompletionTaskParams = task.task_params

    try:
        task_params.max_tokens = max_tokens
        # Convert messages to a list to allow indexing, then update the first message's content
        messages = list(task_params.messages)
        messages[0].content = "Please count from 1 to 100"
        task_params.messages = messages

        full_response = ""
        count = 0
        stop_reason: FinishReason | None = None

        async for chunk in supervisor.stream_response(task=task):
            if isinstance(chunk, TokenChunk):
                full_response += chunk.text
                count += 1
                if chunk.finish_reason:
                    stop_reason = chunk.finish_reason

        print(f"full_response: {full_response}")

        assert count == max_tokens + 1
        assert "7" in full_response.lower()
        assert "99" not in full_response.lower()

        assert stop_reason == "length"

    finally:
        await supervisor.astop()


@pytest.mark.asyncio
async def test_supervisor_handles_terminated_runner(
    pipeline_shard_meta: Callable[..., PipelineShardMetadata],
    hosts: Callable[..., list[Host]],
):
    """Test that the supervisor handles a terminated runner"""
    model_shard_meta = pipeline_shard_meta(1, 0)

    supervisor = await RunnerSupervisor.create(
        model_shard_meta=model_shard_meta,
        hosts=hosts(1, offset=10),
    )

    # Terminate the runner
    supervisor.runner_process.terminate()
    await asyncio.sleep(0.1)

    assert not supervisor.runner_process.is_alive()

    del supervisor


@pytest.mark.asyncio
async def test_supervisor_handles_killed_runner(
    pipeline_shard_meta: Callable[..., PipelineShardMetadata],
    hosts: Callable[..., list[Host]],
):
    """Test that the supervisor handles a killed runner"""
    model_shard_meta = pipeline_shard_meta(1, 0)

    supervisor = await RunnerSupervisor.create(
        model_shard_meta=model_shard_meta,
        hosts=hosts(1, offset=10),
    )

    assert supervisor.runner_process.is_alive()

    # Forcibly kill the runner
    supervisor.runner_process.kill()
    await asyncio.sleep(0.1)

    assert not supervisor.runner_process.is_alive()

    del supervisor
