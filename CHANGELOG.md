# Changelog

This project follows [Semantic Versioning](https://semver.org/).

## [1.4.0] - 2026-09-08

### Added
- `specshift lint <spec>`: a new command that reviews a single OpenAPI/
  Swagger document for spec-validity problems and best-practice gaps,
  independent of comparing it to any other version. It reuses the exact
  same severity model and report formats (console, Markdown, JSON, HTML,
  SARIF) as the diff commands. Checks include:
  - Path template parameters that aren't declared, or path parameters
    declared without `required: true` (both invalid per the OpenAPI spec)
  - Responses missing a `description` (required by the OpenAPI spec)
  - Security requirements referencing an undefined security scheme
  - Duplicate `operationId` values across the document
  - Missing `summary`/`description`, missing `operationId`, and missing
    documented error (4xx/5xx) responses on non-safe operations
  - Inconsistent path segment naming conventions (mixing kebab-case,
    snake_case, and camelCase)
  - Schemas defined under `components.schemas` that don't appear to be
    referenced anywhere in the document
- The AI summary feature and all text-based report formats now adapt
  their wording to whether they're describing a diff between two
  versions or a single-document lint pass (e.g. "issues found" and
  "should be fixed for spec validity" instead of diff-oriented phrasing).
- Single-version reports (like lint results) now show a clean `Title :
  version` header instead of an empty version arrow.

## [1.3.0] - 2026-09-06

### Added
- `specshift changelog <spec-path>`: walks a spec file's history across git
  tags and generates a single Markdown changelog document, diffing each
  consecutive pair of tagged versions (plus an optional "Unreleased"
  section comparing the latest tag to the current working tree). Works
  with OpenAPI, GraphQL, and Protobuf files, auto-detected by extension.
  Supports `--tag-pattern` to filter tags (e.g. `v*`) and `--output` to
  write the result to a file.
- `--format sarif`: renders results as SARIF 2.1.0, the format GitHub
  Code Scanning expects, so breaking changes can show up as code scanning
  alerts instead of only a build log line or PR comment. The official
  GitHub Action gained a new `upload-sarif` input that generates and
  uploads this report automatically via `github/codeql-action/upload-sarif`
  (requires `security-events: write` permission in the calling workflow).
- Protobuf `reserved` statement awareness: `specshift diff-proto` now
  parses `reserved` number ranges and quoted names. A field or enum value
  that is removed and properly reserved is now reported as informational
  rather than a warning, and a new field or enum value that reuses a
  number the same file marks as `reserved` is now flagged as breaking
  (such a schema would fail to compile with `protoc`).

## [1.2.0] - 2026-09-06

### Added
- Protobuf/gRPC schema diffing via the new `specshift diff-proto` command,
  using a dependency-free `.proto` parser (proto2 and proto3, including
  fields declared inside `oneof` blocks). Severity is based on protobuf's
  own documented wire-compatibility rules rather than JSON shape:
  - Adding a field or rpc method is always info-level, since protobuf's
    wire format safely ignores anything it doesn't recognize.
  - Changing a field's number is always breaking (the number, not the
    name, is what the wire format keys on).
  - Field type changes are compared by wire type category (varint,
    64-bit, 32-bit, length-delimited); crossing categories is breaking,
    changing within the same category (e.g. int32 -> int64, string ->
    bytes) is a warning since it can be lossy. `sint32`/`sint64` use
    zigzag encoding and are treated as incompatible with the other
    varint types even though they share a wire type, matching the
    official protobuf documentation.
  - Reusing a removed field's number for a differently-typed field is
    breaking; removing a field or enum value without reuse is a warning.
  - Cardinality changes (singular <-> repeated) and rpc streaming mode
    changes are breaking; rpc request/response type changes are breaking.
- A local, dependency-free web dashboard via `specshift serve`: opens a
  browser tab where you can drag in or paste two OpenAPI, GraphQL, or
  Protobuf files, auto-detects the contract type, and renders the same
  styled HTML report as the CLI, with a short in-session comparison
  history. Built entirely on Python's standard library (`http.server`),
  so it needs no extra dependency and binds to localhost only.
- New example Protobuf schemas (`examples/old_service.proto`,
  `examples/new_service.proto`) demonstrating the new command.

## [1.1.0] - 2026-09-03

### Added
- GraphQL SDL schema diffing via the new `specshift diff-graphql` command,
  using a lightweight, dependency-free SDL parser. Detects removed/added
  types, fields, arguments, and enum values, type and nullability changes,
  interface and union membership changes, and `@deprecated` markers, all
  classified with the same context-aware breaking/warning/info rules used
  for OpenAPI (input types behave like requests, object types behave like
  responses).
- New `--format html` output producing a standalone, self-contained HTML
  report with severity filtering and a search box, usable as a downloadable
  CI artifact or a shareable file with no server required.
- An official composite GitHub Action (`action.yml` at the repository root)
  that runs a contract check, posts (and keeps updated) a Markdown report
  as a pull request comment, and fails the workflow based on a configurable
  severity threshold. Usable as `Lethe044/SpecShift@v1` from any repository.
- Additional OpenAPI diff rules: content-type additions/removals,
  `additionalProperties` tightening, `readOnly`/`writeOnly` flag changes,
  numeric and string constraint tightening (`minimum`, `maximum`,
  `minLength`, `maxLength`, `pattern`, and friends), default value changes,
  and `oneOf`/`anyOf` variant count changes.
- New example GraphQL schemas (`examples/old_schema.graphql`,
  `examples/new_schema.graphql`) demonstrating the new command.

## [1.0.0] - 2026-08-31

### Added
- Support for loading OpenAPI 3.x and Swagger 2.0 specifications from a
  file, a URL, or a git reference.
- A comprehensive structural diff engine covering paths, operations,
  parameters, request bodies, responses, and schemas.
- Context-aware classification of changes into breaking, warning, and info
  (the same change is weighted differently in a request versus a response).
- `$ref` resolution and `allOf` merging support.
- Detection of enum, format, nullable, required-field, and security scheme
  changes.
- Console (with optional rich-powered colored table), Markdown, and JSON
  report formats.
- Optional AI-powered natural-language summary (Groq, Gemini, or any
  OpenAI-compatible endpoint), with a rule-based fallback summary that
  works without any API key.
- Slack and Discord webhook notifications.
- The `specshift check` command for CI/CD integration: compares the
  current specification against a git reference (branch, tag, commit) and
  fails the build if a breaking change is found.
- The `specshift watch` command for periodically monitoring a live API
  specification and automatically notifying on changes.
- `.specshift.yml` configuration file support and the `specshift init`
  command.
- GitHub Actions workflows for CI and PyPI publishing.
- A comprehensive test suite and two example OpenAPI specifications.
