# Icarus Framework: Agent Rules

## Identity

This is the Icarus open-source framework. When working in this repo,
you are building infrastructure, not doing research. The research
identity lives in research/.

Code here must be generic, reusable, and free of proprietary logic.

---

## Autonomy

### Auto
- Read files, explore codebase
- Write, edit, delete code
- Run tests, lints, builds
- Update .claude/ files
- Run docker compose up/down
- Run database migrations

### Needs Approval
- Package installs (pip install, npm install)
- Force pushes
- .env file changes
- Merges to main
- Enabling live trading (LIVE_TRADING_ENABLED)

---

## Code Style

- Python 3.12, type hints required on all functions and methods
- async/await for all I/O operations
- Docstrings on public classes and methods (brief, not verbose)
- No comments narrating obvious code
- Follow the writing style guide for commits and PRs
- Frontend: TypeScript strict, functional components, CSS custom properties

---

## Architecture Patterns

- **Engines** (`api/engines/`): Core business logic. Stateless where possible.
  Each engine has a single responsibility. No direct database access: engines
  receive data and return results.
- **Routers** (`api/routers/`): Thin HTTP/WebSocket layer. Validate input,
  call engines/services, return responses. No business logic here.
- **Services** (`api/services/`): External integrations (IB, data providers,
  Redis). Handle connection management, rate limiting, error recovery.
- **Strategies** (`api/strategies/`): Plugin system. All extend BaseStrategy.
  Example strategies are educational only.
- **Worker** (`worker/`): Background data ingestion. Rate-aware scheduling.
  Writes to TimescaleDB and publishes to Redis Streams.

---

## What to Avoid

- No proprietary strategy logic in this repo
- No hardcoded API keys or credentials
- No references to specific Venture Chain research or IP
- No em dashes in any output
- No mocking the database in tests: use real TimescaleDB or in-memory
- No direct SQL in routers: use SQLAlchemy models/queries
