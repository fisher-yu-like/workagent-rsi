"""Simple names for the part that proposes a skill change."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .candidate_provider import CandidateProvider, DeterministicCandidateProvider
from .candidate_workspace import CandidateWorkspaceBuilder, CandidateWorkspaceManifest
from .diagnosis import FailureDiagnoser
from .rsi_contracts import CandidatePatch, FailureDiagnosis, ProviderRecord


class Learn:
    """Turn observed failures into a bounded candidate change."""

    def __init__(self, provider: CandidateProvider | None = None) -> None:
        self.provider = provider or DeterministicCandidateProvider()
        self.workspace = CandidateWorkspaceBuilder()
        self.diagnoser = FailureDiagnoser()

    def diagnose(self, results: list[dict]) -> list[FailureDiagnosis]:
        return self.diagnoser.diagnose(results)

    def export(
        self,
        source_root: str | Path,
        workspace_root: str | Path,
        allowed_files: list[str],
        context_files: dict[str, str] | None = None,
    ) -> CandidateWorkspaceManifest:
        """Create an isolated, allowlisted workspace for a candidate.

        Workspace construction stays separate from proposal generation so a
        provider never receives access to the source repository by accident.
        """

        return self.workspace.export(source_root, workspace_root, allowed_files, context_files or {})

    def propose(
        self,
        workspace: str | Path,
        diagnoses: Sequence[FailureDiagnosis],
        parent_version: str,
        output_root: str | Path,
        *,
        edit_budget: int = 1,
    ) -> tuple[CandidatePatch | None, ProviderRecord]:
        return self.provider.generate(workspace, diagnoses, parent_version, edit_budget, output_root)


Diagnose = FailureDiagnoser

__all__ = ["CandidateProvider", "Diagnose", "Learn"]
