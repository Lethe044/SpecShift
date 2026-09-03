"""
specshift - a CLI tool that detects, classifies, and (optionally)
summarizes changes in OpenAPI and Swagger contracts using AI.
"""

from specshift.differ import diff_specs
from specshift.graphql_differ import diff_graphql, load_sdl as load_graphql_sdl
from specshift.models import Change, Severity, ChangeType, DiffResult
from specshift.spec_loader import load_spec

__version__ = "1.1.0"

__all__ = [
    "diff_specs",
    "diff_graphql",
    "load_spec",
    "load_graphql_sdl",
    "Change",
    "Severity",
    "ChangeType",
    "DiffResult",
    "__version__",
]
