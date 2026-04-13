# Roadmap

## Phase 1: Core API (In Progress)

* CRUD endpoints for artists, labels, and collection items
* Data enrichment using Discogs

## Phase 2: Production Readiness

* API gateway with request routing, header propagation
* JWT authentication with role-based access (admin, public read-only)
* Caching layer for GET requests
* DLQ and retry strategy for failed enrichment attempts
* Structured logging with correlation ID propagation

## Phase 3: Deployment
* Managed PostgreSQL
* Managed RabbitMQ
* Containerized deployment (k8s or similar)

## Beyond
* React-based frontend app
* More enrichment integrations (MusicBrainz, Last.fm)