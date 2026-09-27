"""A small, evidence-first harness for normal Office agent runs."""

__version__ = "0.1.0"

from .data import Task
from .harness import Harness

__all__ = ["Harness", "Task", "__version__"]

