"""Detects which diff/lint engine (OpenAPI, GraphQL, or Protobuf) applies to a given file."""

from __future__ import annotations

from pathlib import Path

_GRAPHQL_EXTENSIONS = {".graphql", ".gql"}
_PROTO_EXTENSIONS = {".proto"}


def detect_engine(spec_path: str) -> str:
    """Returns 'graphql', 'proto', or 'openapi' based on the file extension."""
    suffix = Path(spec_path).suffix.lower()
    if suffix in _GRAPHQL_EXTENSIONS:
        return "graphql"
    if suffix in _PROTO_EXTENSIONS:
        return "proto"
    return "openapi"
