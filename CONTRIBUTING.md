# Contributing to MR. HEALTH Data Platform

Thank you for your interest in contributing!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/arthurmgraf/case_mrHealth.git
   cd case_mrHealth
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure GCP credentials:
   ```bash
   cp config/project_config.yaml.example config/project_config.yaml
   # Edit with your GCP project details
   ```

## Code Standards

- **Linting**: `ruff check .`
- **Type checking**: `mypy . --strict`
- **Testing**: `pytest tests/ -v`
- **SQL**: Follow BigQuery SQL style guide

All code must pass linting and tests before merge.

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires GCP credentials)
pytest tests/integration/ -v -m integration

# Coverage report
pytest tests/ --cov --cov-report=term-missing
```

Target coverage: 97%+

## Pull Request Process

1. Fork the repository and create a branch from `main`
2. Make your changes with tests
3. Ensure CI passes
4. Write a clear PR description
5. Request a review

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code refactoring
- `test:` — Adding or updating tests
- `chore:` — Maintenance tasks
- `infra:` — Infrastructure changes

## Data Engineering Guidelines

- All SQL transformations go in `sql/` organized by Medallion layer
- Cloud Functions must have unit tests
- DAG changes require `test_dag_structure.py` validation
- Config values go in `config/project_config.yaml`, not hardcoded

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
