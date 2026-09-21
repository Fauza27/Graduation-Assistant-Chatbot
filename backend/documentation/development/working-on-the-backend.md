# Working on the Backend

## Local server

Activate the existing virtual environment, then start the API from `backend`:

```powershell
.\virtual_environment\Scripts\Activate.ps1
python main.py
```

The server listens on port `8000`. In development, local AI models warm in the
background so the HTTP server can become available first. The first retrieval
can still be slower while the model is loading.

## Tests

Run the complete test suite before a completed change:

```powershell
.\virtual_environment\Scripts\python.exe -m pytest -q
```

Run focused tests while changing one component, for example:

```powershell
.\virtual_environment\Scripts\python.exe -m pytest -q tests\test_ai_services.py
```

Tests must not require a production database mutation. Use mocks or local test
fixtures for external services.

## Coding conventions

- Keep API handlers thin; move reusable business logic into a service or
  domain module.
- Prefer standard collections and small functions over a new abstraction.
- Name functions after their observable responsibility, such as
  `_build_sources` or `_persist_error_metrics`.
- Close an opened monitoring stage with `finally` when the guarded operation
  can raise.
- Do not log raw secrets, tokens, or full sensitive user content.
- Preserve public API response shapes unless frontend and tests are changed in
  the same commit.

## Refactor boundaries

The active refactor excludes `src/bot`, `src/ingestion`,
`src/generation/intent_classifier/ga_dibutuhin_lagi`, and `classifier.py`.
See [Refactoring Memory](../REFACTORING_MEMORY.md) for the current work record.
