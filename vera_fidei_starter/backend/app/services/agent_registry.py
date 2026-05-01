from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.planner import PlannerAgent
from app.agents.search_agent import SearchAgent
from app.agents.source_finder import SourceFinderAgent
from app.agents.language_agent import LanguageAgent
from app.agents.edition_agent import EditionAgent
from app.agents.citation_verifier import CitationVerifierAgent
from app.agents.translation_agent import TranslationAgent
from app.agents.context_agent import ContextAgent
from app.agents.consistency_agent import ConsistencyAgent
from app.agents.safety_agent import SafetyAgent
from app.agents.pdf_ingestion_agent import PdfIngestionAgent
from app.agents.ingestion_validation_agent import IngestionValidationAgent


def get_agent_registry() -> dict[str, BaseAgent]:
    return {
        "orchestrator": OrchestratorAgent(),
        "planner": PlannerAgent(),
        "search_agent": SearchAgent(),
        "source_finder": SourceFinderAgent(),
        "language_agent": LanguageAgent(),
        "edition_agent": EditionAgent(),
        "citation_verifier": CitationVerifierAgent(),
        "translation_agent": TranslationAgent(),
        "context_agent": ContextAgent(),
        "consistency_agent": ConsistencyAgent(),
        "safety_agent": SafetyAgent(),
        "pdf_ingestion_agent": PdfIngestionAgent(),
        "ingestion_validation_agent": IngestionValidationAgent(),
    }
