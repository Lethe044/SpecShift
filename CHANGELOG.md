# Changelog

This project follows [Semantic Versioning](https://semver.org/).

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
