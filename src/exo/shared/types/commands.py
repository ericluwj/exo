from enum import Enum

from pydantic import Field

from exo.shared.types.api import ChatCompletionTaskParams
from exo.shared.types.common import CommandId, NodeId
from exo.shared.types.models import ModelMetadata
from exo.shared.types.worker.common import InstanceId
from exo.utils.pydantic_ext import CamelCaseModel, TaggedModel


# TODO: We need to have a distinction between create instance and spin up instance.
class CommandType(str, Enum):
    ChatCompletion = "ChatCompletion"
    CreateInstance = "CreateInstance"
    SpinUpInstance = "SpinUpInstance"
    DeleteInstance = "DeleteInstance"
    TaskFinished = "TaskFinished"
    RequestEventLog = "RequestEventLog"


class BaseCommand(TaggedModel):
    command_id: CommandId = Field(default_factory=CommandId)


class ChatCompletion(BaseCommand):
    request_params: ChatCompletionTaskParams


class CreateInstance(BaseCommand):
    model_meta: ModelMetadata


class SpinUpInstance(BaseCommand):
    instance_id: InstanceId


class DeleteInstance(BaseCommand):
    instance_id: InstanceId


class TaskFinished(BaseCommand):
    finished_command_id: CommandId


class RequestEventLog(BaseCommand):
    since_idx: int


Command = (
    RequestEventLog
    | ChatCompletion
    | CreateInstance
    | SpinUpInstance
    | DeleteInstance
    | TaskFinished
)


class ForwarderCommand(CamelCaseModel):
    origin: NodeId
    command: Command
