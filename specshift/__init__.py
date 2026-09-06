"""
specshift - a CLI tool that detects, classifies, and (optionally)
summarizes changes in OpenAPI and Swagger contracts using AI.
"""

from specshift.changelog import build_changelog, relevant_tags
from specshift.differ import diff_specs
from specshift.graphql_differ import diff_graphql, load_sdl as load_graphql_sdl
from specshift.models import Change, Severity, ChangeType, DiffResult
from specshift.protobuf_differ import diff_protos, load_proto
from specshift.spec_loader import load_spec

__version__ = "1.3.0"

__all__ = [
    "diff_specs",
    "diff_graphql",
    "diff_protos",
    "build_changelog",
    "relevant_tags",
    "load_spec",
    "load_graphql_sdl",
    "load_proto",
    "Change",
    "Severity",
    "ChangeType",
    "DiffResult",
    "__version__",
]
