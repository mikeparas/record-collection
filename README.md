# Record Collection

This project provides a simple interface for managing a record collection (yes, Discogs is a thing).

## Overview

FastAPI + PostgreSQL + RabbitMQ + NestJS Microservice (future)

## Quickstart

```bash
cp .env.sample .env  
# edit .env with preferred psql and rabbitmq credentials
make sync      # get dependencies
make dev_full  # set up containers
make test_e2e  # run e2e tests
```

## Prerequisites
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
| `make db_setup` | Database migrations | 
| `make test_e2e` | End-to-end tests |
| `make test` | Unit tests |
| `make precommit` | Format + lint | 


## Dev Environment
Sets up containers for PostgreSQL, RabbitMQ, and FastAPI. Additional services run to initialize the database and run E2E tests.

```bash
make dev_full  # full stack and db setup (recommended first step)
make dev       # just db, rabbitmq, and api containers
make db_setup  # run db setup script (if dev already running)
```

## Python Development
FastAPI code lives in `services/api`. With the dev environment, the API should be accessible at `http://localhost:8000`.

Download project dependencies.
```bash
make sync
```

Run unit tests.
```bash
make test
```

## Database

Currently uses PostgreSQL 17. 

Python side manages database models for the core entities with SQLAlchemy. Migrations are done with Alembic. API will have read access to the tables managed by the microservice.

> TODO: Notes and tooling for migrations.

Node side will likely manage the tables it writes to, and it will have read access to the core tables.

## Version Control

Please format and lint before committing.
```bash
make precommit
```

> TODO: Probably have actual precommit hook.