FROM node:24-alpine AS builder
RUN corepack enable pnpm && corepack install -g pnpm@latest
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/pnpm/store pnpm fetch && pnpm install -P --frozen-lockfile
COPY services/enrich ./services/enrich

# nest app
FROM builder AS enrich
CMD pnpm start

# migrations
FROM builder AS node_migrate
RUN --mount=type=cache,target=/pnpm/store pnpm install -P -D --frozen-lockfile
CMD pnpm --loglevel verbose migrate

# integration (use node_migrate because it has dev dependencies)
FROM node_migrate AS integration
ENV COVERAGE_ENABLED=false
CMD pnpm --loglevel verbose test:integration --coverage=$COVERAGE_ENABLED
