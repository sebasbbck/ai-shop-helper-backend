from ai_shop_helper_backend.models.agent_runs import RunnerType
from ai_shop_helper_backend.runners.base import AgentRunner
from ai_shop_helper_backend.runners.n8n import N8nRunner

_registry: dict[RunnerType, AgentRunner] = {
    RunnerType.n8n: N8nRunner(),
}


def get_runner(runner_type: RunnerType) -> AgentRunner:
    runner = _registry.get(runner_type)
    if runner is None:
        raise ValueError(f"No runner registered for type: {runner_type!r}")
    return runner
