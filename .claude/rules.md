# Icarus Framework: Agent Rules

## Identity

This is the Icarus open-source framework. When working in this repo,
you are building infrastructure, not doing research. The research
identity lives in icarus-research/.

Code here must be generic, reusable, and free of proprietary logic.

---

## Autonomy

### Auto
- Read files, explore codebase
- Write, edit, delete code
- Run tests, lints, builds
- Create feature branches
- Update .claude/ files
- Run docker compose up/down

### Needs Approval
- Package installs (pip install, npm install)
- Force pushes
- .env file changes
- Merges to main

---

## Code Style

- Python 3.12, type hints required
- async/await for all I/O
- Docstrings on public classes and methods (brief, not verbose)
- No comments narrating obvious code
- Follow the writing style guide for commits and PRs

---

## What to Avoid

- No proprietary strategy logic in this repo
- No hardcoded API keys or credentials
- No references to specific Venture Chain research or IP
- No em dashes in any output
