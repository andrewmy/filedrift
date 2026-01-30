lint:
    ruff check .

test:
    python test_filedrift.py

ci: lint test
