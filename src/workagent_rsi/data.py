"""Small public names for the data that moves through the harness.

The implementation keeps the validated models in the compatibility modules so
existing callers continue to work. New code can use the shorter names here.
"""

from .contracts import ArtifactRef as Artifact
from .contracts import EvaluationReport as Report
from .contracts import SkillManifest as Skill
from .contracts import TaskSpec as Task
from .contracts import ToolCall
from .contracts import ToolResult
from .hashing import canonical_json_hash, sha256_bytes, sha256_file
from .rsi_contracts import AtomicEdit as Edit
from .rsi_contracts import CandidatePatch as Change
from .rsi_contracts import EvaluationContract as Contract
from .rsi_contracts import ExperimentResult as Experiment
from .rsi_contracts import FailureDiagnosis as Diagnosis
from .rsi_contracts import PromotionDecision as Decision
from .rsi_contracts import ProviderRecord as ProviderRun
from .rsi_contracts import SkillVersion as Version
from .rsi_contracts import VerificationReport as CheckReport

__all__ = [
    "Artifact",
    "Change",
    "CheckReport",
    "Contract",
    "Decision",
    "Diagnosis",
    "Edit",
    "Experiment",
    "ProviderRun",
    "Report",
    "Skill",
    "Task",
    "ToolCall",
    "ToolResult",
    "Version",
    "canonical_json_hash",
    "sha256_bytes",
    "sha256_file",
]
