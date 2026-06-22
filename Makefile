.PHONY: dev test lint build
dev:
	docker compose up --build
test:
	cd apps/api && pytest
lint:
	cd apps/api && ruff check app tests
	cd apps/web && pnpm typecheck
build:
	docker compose build

