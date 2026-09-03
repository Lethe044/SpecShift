# Changelog

This project follows [Semantic Versioning](https://semver.org/).

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
