from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

from exo.shared.topology import Topology, TopologySnapshot
from exo.shared.types.common import NodeId
from exo.shared.types.profiling import NodePerformanceProfile
from exo.shared.types.tasks import Task, TaskId
from exo.shared.types.worker.common import InstanceId, WorkerStatus
from exo.shared.types.worker.instances import Instance
from exo.shared.types.worker.runners import RunnerId, RunnerStatus


def _encode_topology(topo: "Topology") -> dict[str, Any]:  # noqa: D401
    """Serialise *topo* into a JSON-compatible dict."""

    return topo.to_snapshot().model_dump()


class State(BaseModel):
    """Global system state.

    The :class:`Topology` instance is encoded/decoded via an immutable
    :class:`~shared.topology.TopologySnapshot` to ensure compatibility with
    standard JSON serialisation.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={
            Topology: _encode_topology,
        },
    )
    node_status: Mapping[NodeId, WorkerStatus] = {}
    instances: Mapping[InstanceId, Instance] = {}
    runners: Mapping[RunnerId, RunnerStatus] = {}
    tasks: Mapping[TaskId, Task] = {}
    node_profiles: Mapping[NodeId, NodePerformanceProfile] = {}
    topology: Topology = Topology()
    history: Sequence[Topology] = []
    last_event_applied_idx: int = Field(default=-1, ge=-1)

    @field_validator("topology", mode="before")
    @classmethod
    def _deserialize_topology(cls, value: object) -> Topology:  # noqa: D401 – Pydantic validator signature
        """Convert an incoming *value* into a :class:`Topology` instance.

        Accepts either an already constructed :class:`Topology` or a mapping
        representing :class:`~shared.topology.TopologySnapshot`.
        """

        if isinstance(value, Topology):
            return value

        if isinstance(value, Mapping):  # likely a snapshot-dict coming from JSON
            snapshot = TopologySnapshot(**cast(dict[str, Any], value))  # type: ignore[arg-type]
            return Topology.from_snapshot(snapshot)

        raise TypeError("Invalid representation for Topology field in State")
