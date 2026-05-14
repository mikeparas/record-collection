FROM node:24-alpine3.23 AS builder
RUN corepack enable pnpm && corepack install -g pnpm@latest
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY services/enrich ./services/enrich
RUN --mount=type=cache,target=/pnpm/store pnpm fetch && pnpm install --frozen-lockfile

# nest app (prune dev dependencies)
FROM builder AS enrich
ENV CI=true
RUN pnpm build
RUN --mount=type=cache,target=/pnpm/store pnpm prune --prod
CMD pnpm start:prod

# migrations
FROM builder AS node_migrate
RUN --mount=type=cache,target=/pnpm/store pnpm install --frozen-lockfile
CMD pnpm --loglevel verbose migrate

# integration
FROM node_migrate AS integration
ENV COVERAGE_ENABLED=false
CMD pnpm --loglevel verbose test:integration --coverage=$COVERAGE_ENABLED
