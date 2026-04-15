from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    agent_name: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PipelineContext:
    user_task: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mission: dict[str, Any] = field(default_factory=dict)
    progress: dict[str, Any] = field(default_factory=dict)
    findings: dict[str, Any] = field(default_factory=dict)
    reports: dict[str, Any] = field(default_factory=dict)
    handoffs: list[dict[str, Any]] = field(default_factory=list)
    history: list[AgentResult] = field(default_factory=list)

    def add_result(self, result: AgentResult) -> None:
        """Registra o resultado de um agente sem sobrescrever dados anteriores."""
        self.history.append(result)
        self.reports[result.agent_name] = result.data

    def handoff(self, source: str, target: str, payload: dict[str, Any]) -> None:
        """Registra a passagem de contexto entre agentes com rastreabilidade completa."""
        self.handoffs.append({
            "execution_id": self.execution_id,
            "from": source,
            "to": target,
            "payload": payload,
        })


class BaseAgent(ABC):
    name: str = "base_agent"

    @abstractmethod
    def run(self, ctx: PipelineContext) -> AgentResult:
        raise NotImplementedError
