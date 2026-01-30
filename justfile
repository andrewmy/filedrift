lint:
    uv run ruff check .

test:
    uv run python test_filedrift.py

ci: lint test
