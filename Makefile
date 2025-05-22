lint:
	ruff format --diff
	ruff check

format:
	ruff format
	ruff check --fix
