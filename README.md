# Record Collection

This project provides a simple interface for managing a record collection (yes, Discogs is a thing).

## Overview

FastAPI + PostgreSQL + RabbitMQ + NestJS Microservice (future)

## Quickstart

```bash
cp .env.sample .env  
# edit .env with preferred psql and rabbitmq credentials
make env_file        # symlink .env to service directories
make sync            # get dependencies
make dev_full        # set up containers
make test_integrate  # run integrations tests
```

## Prerequisites

| Runtime | Version |
| --- | --- |
| Python | 3.14 |
| Node | 25.2.1 |

| Tool | Installation |
| --- | --- |
| `uv` | https://docs.astral.sh/uv/getting-started/installation/ |
| `pnpm` | https://pnpm.io/installation |
| `podman` | https://podman.io/docs/installation |

Podman is used as a drop-in replacement for Docker. If using Docker (or other container tool), simply replace `podman` in the `Makefile` targets.

## Commands

| Command | Purpose |
| --- | --- |
| `make dev_full` | Full stack setup + migrations |
| `make dev` | DB + RabbitMQ + API |
| `make db_setup` | Database setup (database, roles, grants) |
| `make db_migrate` | Database migrations |  
| `make test_integrate` | Integration tests |
| `make test` | Unit tests |
| `make precommit` | Format + lint | 
| `make clean` | Clean up containers |

## Dev Environment
Sets up containers for PostgreSQL, RabbitMQ, and FastAPI. Additional services run to initialize the database and run E2E tests.

```bash
make dev_full    # full stack and db setup (recommended first step)
make dev         # just db, rabbitmq, and api containers
make db_setup    # run db setup script (if dev already running)
make db_migrate  # run migrations
```

## Python Development
FastAPI code lives in `services/api`. With the dev environment, the API should be accessible at `http://localhost:8000`.

Download project dependencies.
```bash
make sync_api
```

Run unit tests.
```bash
make test_api_unit
```

## Node Development

NestJS code lives in `services/enrich`.

Download project dependencies.
```bash
make sync_enrich
```

Run unit tests.
```bash
make test_api_enrich
```

## Database

Currently uses PostgreSQL 17. 

Python side manages database models for the core entities with SQLAlchemy. Migrations are done with Alembic. API will have read access to the tables managed by the microservice.

Node side manages database models for "extra" data tables using TypeORM, which will also handle migrations for those tables. Microservice will have read access to the core tables. 

> TODO: Notes and tooling for migrations.

## Tests

Unit and integration tests are run with Pytest for Python and Jest for Node.

For integration tests, a test version of the database will be used. Using the appropriate `make` targets will run setup and teardown scripts for this. For RabbitMQ, test versions of the exchanges and queues will be used. These are created in the test code.

Integration tests cover each service in isolation (e.g., Python tests only cover the API).

> TODO: Full E2E tests.

## Version Control

Please format and lint before committing.
```bash
make precommit
```

> TODO: Probably have actual precommit hook.