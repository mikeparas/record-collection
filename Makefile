sync:
	uv sync --all-groups --all-extras

.PHONY: secrets
secrets:
	./scripts/generate_rabbitmq_cookie.sh

secrets-check:
	test -f ./secrets/.erlang.cookie || make secrets

dev: secrets-check
	podman compose up -d

db_setup:
	podman compose --profile tools run --rm db_setup

dev_full: dev db_setup

test:
	uv run pytest -m "not e2e"

test_e2e:
	podman compose --profile tools run --rm api_e2e

precommit:
	uv run poe precommit

clean:
	podman compose down -v