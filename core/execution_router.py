"""Model failover routing for agent execution."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core.docker_controller import ContainerRunResult, DockerController

logger = logging.getLogger(__name__)

FALLBACK_CHAIN: tuple[str, ...] = (
    "claude-4.6-sonnet",
    "composer-2.5",
    "auto",
)

ModelSwitchCallback = Callable[[dict[str, str]], None]


@dataclass
class AgentRunOutcome:
    """Result of an agent invocation, including any model failovers."""

    result: ContainerRunResult
    model_used: str
    models_tried: list[str] = field(default_factory=list)
    model_switches: list[dict[str, str]] = field(default_factory=list)


def resolve_model_chain(initial_model: str) -> list[str]:
    """Return ordered models to try, starting from *initial_model*."""
    normalized = initial_model.strip() or FALLBACK_CHAIN[0]
    if normalized in FALLBACK_CHAIN:
        idx = FALLBACK_CHAIN.index(normalized)
        return list(FALLBACK_CHAIN[idx:])
    return [normalized, *FALLBACK_CHAIN]


def log_model_switch(
    *,
    from_model: str,
    to_model: str,
    reason: str,
    json_logs: bool = False,
) -> dict[str, str]:
    """Emit a structured model-switch event to logs."""
    event = {
        "event": "model_switch",
        "from_model": from_model,
        "to_model": to_model,
        "reason": reason,
    }
    if json_logs:
        logger.info(json.dumps(event, ensure_ascii=False))
    else:
        logger.warning(
            "Model failover: %s → %s (reason=%s)",
            from_model,
            to_model,
            reason,
        )
    return event


class ExecutionRouter:
    """Runs agents with preset model failover on non-success outcomes."""

    def __init__(
        self,
        docker: DockerController,
        *,
        json_logs: bool = False,
        on_model_switch: ModelSwitchCallback | None = None,
    ) -> None:
        self.docker = docker
        self.json_logs = json_logs
        self.on_model_switch = on_model_switch

    def run_agent(
        self,
        project_root: Path,
        prompt: str,
        *,
        model: str,
        yolo: bool = False,
        max_failover_steps: int | None = None,
    ) -> AgentRunOutcome:
        """Run the agent, failing over to the next model in the chain on failure."""
        chain = resolve_model_chain(model)
        if max_failover_steps is not None:
            chain = chain[: max(1, max_failover_steps)]

        models_tried: list[str] = []
        switches: list[dict[str, str]] = []
        last_result: ContainerRunResult | None = None
        model_used = chain[0]

        for index, current_model in enumerate(chain):
            if index > 0:
                switch = log_model_switch(
                    from_model=models_tried[-1],
                    to_model=current_model,
                    reason="agent_failure",
                    json_logs=self.json_logs,
                )
                switches.append(switch)
                if self.on_model_switch is not None:
                    self.on_model_switch(switch)

            models_tried.append(current_model)
            model_used = current_model
            last_result = self.docker.run_agent(
                project_root,
                prompt,
                model=current_model,
                yolo=yolo,
            )
            if last_result.success:
                break

        assert last_result is not None
        return AgentRunOutcome(
            result=last_result,
            model_used=model_used,
            models_tried=models_tried,
            model_switches=switches,
        )
