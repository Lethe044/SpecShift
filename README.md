# SpecShift

[![CI](https://github.com/Lethe044/specshift/actions/workflows/ci.yml/badge.svg)](https://github.com/Lethe044/specshift/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/specshift.svg)](https://pypi.org/project/specshift/)
[![Python versions](https://img.shields.io/pypi/pyversions/specshift.svg)](https://pypi.org/project/specshift/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SpecShift detects changes in OpenAPI and Swagger contracts, classifies each
one as breaking, warning, or info, and can optionally summarize them in
plain language.

When an API changes from one version to the next, the real question isn't
"what changed" but "will this break me". SpecShift is built to answer
exactly that: it takes two specifications, evaluates every difference
between them individually, and tells you which ones actually matter.

```
$ specshift diff examples/old_api.yaml examples/new_api.yaml

Bookstore API : 1.0.0 -> 2.0.0
13 breaking, 2 warning, 3 info changes found.

[BREAKING] DELETE /books/{bookId} :: HTTP method removed
[BREAKING] GET /books > parameter 'category' :: Parameter 'category' is now required
[BREAKING] GET /books > response 200 > field 'author' :: field removed from response
...

Result: 13 breaking change(s) make this update risky.
```

## Why SpecShift

Every team that keeps evolving its API eventually hits the same problem:
a field gets removed, a parameter becomes required, an enum value
disappears, and nobody notices until a client breaks in production.
Most existing diff tools just show you a raw JSON diff and leave it up to
you to figure out what actually matters.

SpecShift doesn't do that. It evaluates every change based on its context:

- Removing a field from a **response** is **breaking**, because clients
  may depend on it being there.
- Removing the same field from a **request body** is usually just a
  **warning**, because clients that send it are simply ignored, not broken.
- Adding a new required field to a request is **breaking**, but adding a
  new field to a response is just **informational**.

These context-aware rules are the core of SpecShift, and they work
completely free, with no API key required. The optional AI-powered
natural-language summary is an additional layer on top, never a
requirement.

## Features

- **Comprehensive structural diff**: deep comparison at the path, HTTP
  method, parameter, request body, response, and schema level.
- **GraphQL support**: diff GraphQL SDL schemas with `specshift diff-graphql`,
  covering types, fields, arguments, enum values, interfaces, unions, and
  deprecations, no external GraphQL library required.
- **Protobuf/gRPC support**: diff `.proto` files with `specshift diff-proto`,
  using protobuf's own documented wire-compatibility rules (field numbers,
  wire type categories, zigzag encoding) rather than generic JSON-shape
  heuristics, so severity reflects what will actually break on the wire.
- **Context-aware classification**: the same change is weighted
  differently depending on whether it occurs in a request or a response
  (or, for GraphQL, an input type versus an object type).
- **`$ref` resolution and `allOf` merging**: correctly follows the
  reference and composition patterns common in real-world specifications.
- **Detects enum, format, nullable, security scheme, content-type,
  `additionalProperties`, `readOnly`/`writeOnly`, validation constraint,
  default value, and `oneOf`/`anyOf` changes**.
- **Works entirely for free**: no API key or paid service is required.
- **Optional AI summary**: can generate a natural-language summary using
  Groq, the Gemini free tier, or any OpenAI-compatible endpoint. If no key
  is set, it automatically falls back to a rule-based summary and never
  stops working.
- **CI/CD integration**: the `specshift check` command compares the
  current specification against a branch and fails the build if a
  breaking change is found. An official GitHub Action is also available
  for one-line setup with automatic PR comments (see below).
- **Live monitoring**: the `specshift watch` command periodically checks
  a remote API's specification and sends a Slack or Discord notification
  when it changes.
- **Local web dashboard**: `specshift serve` opens a browser-based tool
  for comparing specs interactively (drag in files or paste text), with
  zero extra dependencies since it runs entirely on Python's standard
  library and stays on localhost.
- **Auto-generated changelog**: `specshift changelog` walks your spec
  file's history across git tags and produces a single Markdown document
  summarizing what changed (and whether it was breaking) between every
  release, plus an "Unreleased" section for the current working tree.
- **Five output formats**: a colored console table, a Markdown report
  (ideal for PR comments), JSON (for integrating with other tools), a
  standalone filterable HTML report, and SARIF 2.1.0 for GitHub Code
  Scanning.

## Installation

```bash
pip install specshift
```

For colored console output (optional, works fine without it too):

```bash
pip install "specshift[pretty]"
```

Installing from source:

```bash
git clone https://github.com/Lethe044/specshift.git
cd specshift
pip install -e .
```

## Quick start

Compare two specifications directly:

```bash
specshift diff old_openapi.yaml new_openapi.yaml
```

You can also compare specifications from URLs:

```bash
specshift diff https://api.example.com/v1/openapi.json https://api.example.com/v2/openapi.json
```

To use it in CI, create a configuration file in your repo:

```bash
specshift init
```

This produces a `.specshift.yml` file similar to:

```yaml
spec_path: openapi.yaml
base_ref: main
fail_on: breaking
```

Then, in your CI pipeline:

```bash
specshift check
```

This command compares the current `openapi.yaml` file against its version
on the `main` branch and returns exit code 1 if a breaking change is found.

## AI summary (optional)

SpecShift can use free-tier AI services to generate a natural-language
summary of the changes. This never requires any payment:

```bash
export GROQ_API_KEY="your-groq-api-key"
specshift diff old.yaml new.yaml --ai
```

You can also use Google Gemini's free tier instead of Groq:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
specshift diff old.yaml new.yaml --ai --ai-provider gemini
```

If you want to use a more powerful (paid) model, you can connect any
OpenAI-compatible endpoint:

```bash
export SPECSHIFT_API_KEY="your-api-key"
export SPECSHIFT_OPENAI_BASE_URL="https://api.openai.com/v1"
specshift diff old.yaml new.yaml --ai --ai-provider openai_compatible --ai-model gpt-4o-mini
```

If no key is configured, the `--ai` flag still works, it simply produces a
rule-based summary instead of waiting on a network call. AI support is an
optional enhancement, never a requirement.

## Commands

### `specshift diff <old> <new>`

Compares two specifications. `<old>` and `<new>` can be a file path, an
http(s) URL, or raw JSON/YAML text.

Useful options:

| Option | Description |
|---|---|
| `--format console\|markdown\|json\|html\|sarif` | Output format (default: console) |
| `--output <file>` | Writes the output to a file |
| `--ai` | Adds a natural-language summary |
| `--ai-provider groq\|gemini\|openai_compatible` | Chooses the AI provider |
| `--fail-on breaking\|warning\|none` | Determines at which level exit code 1 is returned |
| `--quiet` | Only prints the summary line |

### `specshift diff-graphql <old> <new>`

Compares two GraphQL SDL schemas. `<old>` and `<new>` can be a file path,
an http(s) URL, or raw SDL text. Supports the same `--format`, `--output`,
`--ai`, and `--fail-on` options as `diff`.

```bash
specshift diff-graphql old_schema.graphql new_schema.graphql
```

### `specshift diff-proto <old> <new>`

Compares two Protobuf/gRPC `.proto` schemas using protobuf's own
wire-compatibility rules (field numbers, wire type categories) rather
than generic JSON-shape heuristics. Supports the same `--format`,
`--output`, `--ai`, and `--fail-on` options as `diff`.

```bash
specshift diff-proto old_service.proto new_service.proto
```

### `specshift serve`

Starts a local, dependency-free web dashboard for comparing specs
interactively. Opens a browser tab where you can drag in or paste two
files (OpenAPI, GraphQL, or Protobuf, auto-detected), and view the same
styled HTML report the CLI produces, with a short history of past
comparisons in the current session.

```bash
specshift serve
# or: specshift serve --port 9000 --no-browser
```

Everything runs in-process on your machine; nothing is uploaded anywhere,
and the server binds to `127.0.0.1` by default.

### `specshift check`

Designed for CI/CD. Compares the current specification file against a git
reference (branch, tag, or commit) defined in `.specshift.yml`.

```bash
specshift check --spec openapi.yaml --base-ref origin/main
```

### `specshift watch <url>`

Periodically checks a remote specification, compares it against the
previous snapshot, and sends a notification if a difference is found.

```bash
specshift watch https://api.example.com/openapi.json \
  --interval 600 \
  --slack-webhook "$SLACK_WEBHOOK_URL"
```

### `specshift changelog <spec-path>`

Walks the given file's history across git tags and generates a single
Markdown changelog, diffing each consecutive pair of tagged versions. By
default it also appends an "Unreleased" section comparing the latest tag
to the current working tree, if they differ.

```bash
specshift changelog openapi.yaml --output CHANGELOG-API.md
```

Options: `--tag-pattern` (glob, default `*`, e.g. `v*` to only consider
tags starting with `v`), `--no-working-tree` to skip the "Unreleased"
section, and `--output` to write to a file instead of stdout.

### `specshift init`

Creates a sample `.specshift.yml` file.

## Using it with GitHub Actions

### Option 1: the official SpecShift action (recommended)

SpecShift ships its own composite GitHub Action that runs the contract
check and automatically posts (and keeps updated) a Markdown report as a
pull request comment:

```yaml
name: API Contract Check

on:
  pull_request:
    paths:
      - "openapi.yaml"

permissions:
  pull-requests: write

jobs:
  contract-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: Lethe044/SpecShift@v1
        with:
          spec-path: openapi.yaml
          fail-on: breaking
          # optional: ai-summary: 'true'
```

Available inputs: `spec-path`, `base-ref` (defaults to the PR base branch),
`fail-on` (`breaking` | `warning` | `none`), `ai-summary` (`true`/`false`),
`ai-provider`, `comment-on-pr` (`true`/`false`), `upload-sarif`
(`true`/`false`, see below), `github-token`, and `specshift-version` to
pin a specific release. Outputs: `has-breaking-changes`, `breaking-count`,
`warning-count`, `info-count`, `report-path`, and `sarif-path`.

To also surface results in GitHub's Code Scanning tab, enable
`upload-sarif` and grant the extra permission it needs:

```yaml
permissions:
  pull-requests: write
  security-events: write

jobs:
  contract-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: Lethe044/SpecShift@v1
        with:
          spec-path: openapi.yaml
          upload-sarif: 'true'
```

### Option 2: calling the CLI directly

If you'd rather not use the action (or want to combine it with other
tooling), the CLI works just as well on its own:

```yaml
name: API Contract Check

on:
  pull_request:
    paths:
      - "openapi.yaml"

jobs:
  contract-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install specshift

      - run: specshift check --base-ref origin/${{ github.base_ref }}
```

If you want to add AI-powered PR comments, you can generate a Markdown
report with `specshift check --ai --format markdown --output report.md`
and post it as a PR comment using an action like
`peter-evans/create-or-update-comment`.

## Configuration file (`.specshift.yml`)

```yaml
spec_path: openapi.yaml
base_ref: main
fail_on: breaking

# optional
ai_provider: groq
ai_model: llama-3.3-70b-versatile
slack_webhook: https://hooks.slack.com/services/...
discord_webhook: https://discord.com/api/webhooks/...
ignore_paths: []
```

## When SpecShift calls something breaking

The table below summarizes which severity level applies in the most
common scenarios:

| Change | In a request | In a response |
|---|---|---|
| Field removed | Warning | Breaking |
| New required field added | Breaking | Info |
| New optional field added | Info | Info |
| Field no longer required | Info | Breaking |
| Field became required | Breaking | Info |
| Data type changed | Breaking | Breaking |
| Enum value removed | Breaking | Breaking |
| Endpoint or method removed | Breaking | Breaking |

The same table applies to GraphQL: `input` types behave like requests,
`type`/`interface` fields behave like responses.

Protobuf/gRPC follows a different model, based on the wire format rather
than request/response direction: adding fields or rpc methods is always
safe, changing a field's number is always breaking, and type changes are
judged by wire type category (see the `diff-proto` section above).

## Comparison with other tools

| | SpecShift | Raw JSON/YAML diff | oasdiff / openapi-diff style tools |
|---|---|---|---|
| Context-aware classification | Yes | No | Partially |
| GraphQL support | Yes | No | Rarely |
| Protobuf/gRPC support (wire-aware) | Yes | No | Rarely |
| Natural-language summary | Yes (optional) | No | No |
| Standalone HTML report | Yes | No | Rarely |
| Local interactive dashboard | Yes | No | Rarely |
| Auto-generated changelog across git tags | Yes | No | Rarely |
| GitHub Code Scanning (SARIF) integration | Yes | No | Rarely |
| Free to use | Fully free | Free | Usually free |
| CI integration | Built-in (`check` + official Action) | Manual | Varies |
| Live URL monitoring | Built-in (`watch`) | No | Rarely |

## Roadmap

This project is under active development. Some planned areas:

- Path parameter pattern (regex) and discriminator-level rule refinements
- Deeper GraphQL support: directive-aware deprecation reasons, custom
  scalar compatibility hints, and federation-aware schema composition
- Optional shared/hosted history for the `serve` dashboard (currently
  in-memory and per-session by design)
- Changelog generation from raw commit history (not just tags), for
  repositories that don't tag every release

Feel free to open an issue if you have a feature request.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution guide. Bug
reports, feature requests, and pull requests are always welcome.

## License

This project is licensed under the [MIT License](LICENSE).
