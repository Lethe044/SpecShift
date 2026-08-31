# Contributing Guide

Thank you for your interest in contributing to SpecShift. This document
is meant to make the contribution process easier, both for you and for
the project maintainers.

## Setting up a development environment

```bash
git clone https://github.com/Lethe044/specshift.git
cd specshift
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

After installation, verify that the CLI works:

```bash
specshift --version
specshift diff examples/old_api.yaml examples/new_api.yaml
```

## Running tests

```bash
pytest --cov=specshift --cov-report=term-missing
```

When adding a new feature or fix, make sure to add corresponding tests.
The existing tests in `tests/test_differ.py` show the pattern to follow
when adding a new rule: build a small, focused OpenAPI snippet, run the
diff, and assert the expected severity and message.

## Code style

- Maintain Python 3.9+ compatibility.
- Use descriptive names for functions and variables.
- Add docstrings to new public functions.
- Use type hints wherever practical.
- Break large functions into small, testable pieces.

## Adding a new diff rule

Most of the diff engine consists of small, single-responsibility functions
inside `specshift/differ.py`. When adding a new rule:

1. Think about whether the change carries different weight depending on
   context (request vs. response). The same change can be harmless in a
   request but breaking in a response, or vice versa.
2. Pick the most appropriate severity level: `Severity.BREAKING`,
   `Severity.WARNING`, or `Severity.INFO`, and briefly explain your
   reasoning in the function or the commit message.
3. Add both a positive and a negative test case (the rule should trigger
   when it's supposed to, and should NOT trigger when it isn't).

## Reporting bugs

If you find a bug, please open an issue including:

- The specshift version you're using (`specshift --version`)
- A minimal OpenAPI example that triggers the issue (if possible)
- The expected behavior versus the observed behavior

## Pull request process

1. Fork the repository and create a new branch for your change.
2. Make your change along with test coverage.
3. Run `pytest` and make sure all tests pass.
4. Briefly describe what changed and why in the PR description.
5. Respond to feedback until CI turns green.

Small fixes (typos, documentation improvements) are welcome too, don't
hesitate to open a PR for those as well, every contribution matters.

## Code of conduct

This project expects respectful and constructive communication from
everyone involved. Constructive criticism is always welcome; personal
attacks and disrespectful language are not.
