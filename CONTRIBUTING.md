# Contributing to Icarus

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes
4. Run tests: `pytest`
5. Open a pull request

## Code Style

- Python: type hints on all functions, async for I/O
- TypeScript: strict mode
- Comments explain why, not what
- No em dashes

## Pull Requests

- One logical change per PR
- Tests for new endpoints and strategy interface changes
- PR description size matches change size

## Strategy Contributions

If you've built a useful strategy on Icarus and want to share it as an example:

1. It must extend `BaseStrategy`
2. Clearly label it as educational
3. Include a brief docstring explaining the approach
4. Include a basic test

## Bug Reports

Open an issue with:
- What happened
- What you expected
- Steps to reproduce
- Icarus version and environment
