# ensure these match with your environment or .env
PROD_DB?=record_collection
TEST_DB?=test_record_collection

PYTHON_UV_RUN_API=uv run --directory services/api

PYTHON_DB_INIT_SCRIPT=$(PYTHON_UV_RUN_API) -m scripts.db_init_cli
PYTHON_DB_SETUP=$(PYTHON_DB_INIT_SCRIPT) setup
PYTHON_DB_MIGRATE=$(PYTHON_UV_RUN_API) alembic upgrade head

COMPOSE_TOOLS_RUN=docker compose --profile tools run --rm

sync_api:
	uv sync --all-groups --all-extras

sync_enrich:
	pnpm i

sync: sync_api sync_enrich

.PHONY: secrets
secrets:
	./scripts/generate_rabbitmq_cookie.sh

secrets-check:
	test -f ./secrets/.erlang.cookie || make secrets

env_file:
	ln -sf $(realpath .env) services/api/.env
	ln -sf $(realpath .env) services/enrich/.env

build:
	docker compose build
	docker compose --profile tools build

build_service:
	docker compose build $(SERVICE)

build_tools_service:
	docker compose --profile tools build $(SERVICE)

dev: secrets-check
	docker compose up -d

db_setup:
	$(COMPOSE_TOOLS_RUN) -e DB_NAME=$(PROD_DB) db_setup $(PYTHON_DB_SETUP)

db_migrate:
	$(COMPOSE_TOOLS_RUN) -e DB_NAME=$(PROD_DB) db_setup $(PYTHON_DB_MIGRATE)
	$(COMPOSE_TOOLS_RUN) -e DB_NAME=$(PROD_DB) node_migrate

db_api_migrate_generate:
	DB_NAME=$(PROD_DB) $(PYTHON_UV_RUN_API) alembic revision --autogenerate -m $(MIGRATION)

db_enrich_migrate_generate:
	cd services/enrich && pnpm db:migrate-generate src/migrations/$(MIGRATION)

dev_full: dev db_setup db_migrate

test_api_unit:
	DB_NAME=test uv run --directory services/api pytest tests/unit

test_enrich_unit:
	pnpm test

test_enrich_unit_cov:
	pnpm test:cov

test: test_api_unit test_enrich_unit	

test_db_setup:
	$(COMPOSE_TOOLS_RUN) -e DB_NAME=$(TEST_DB) -e MODE=test db_setup $(PYTHON_DB_SETUP)

test_db_migrate:
	$(COMPOSE_TOOLS_RUN) -e DB_NAME=$(TEST_DB) db_setup $(PYTHON_DB_MIGRATE)
	$(COMPOSE_TOOLS_RUN) -e DB_NAME=$(TEST_DB) node_migrate

test_db_teardown:
	$(COMPOSE_TOOLS_RUN) -e DB_NAME=$(TEST_DB) -e MODE=test db_setup $(PYTHON_DB_INIT_SCRIPT) teardown

api_integrate:
	$(COMPOSE_TOOLS_RUN) -e PYTEST_ARGS=tests/integration api_tests

enrich_integrate:
	$(COMPOSE_TOOLS_RUN) enrich_integrate

enrich_integrate_cov:
	$(COMPOSE_TOOLS_RUN) -e COVERAGE_ENABLED=true enrich_integrate

test_integrate_pre: test_db_setup test_db_migrate

test_api_integrate: test_integrate_pre api_integrate test_db_teardown

test_enrich_integrate: test_integrate_pre enrich_integrate test_db_teardown

test_enrich_integrate_cov: test_integrate_pre enrich_integrate_cov test_db_teardown

test_integrate: test_integrate_pre api_integrate enrich_integrate test_db_teardown

precommit:
	uv run poe precommit
	pnpm precommit

lint_api:
	uv run poe lint

lint_enrich:
	pnpm lint

lint: lint_api lint_enrich

clean:
	docker compose down -v
