from dataclasses import dataclass, field


@dataclass
class Mission:
    task: str
    objective: str
    scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    done_definition: list[str] = field(default_factory=list)
