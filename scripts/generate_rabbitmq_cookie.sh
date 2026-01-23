#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(realpath $SCRIPT_DIR/..)"
SECRETS_DIR="$PROJECT_ROOT/secrets"
COOKIE_FILE=".erlang.cookie"

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"
openssl rand -base64 32 | tr -d "=+/" | cut -c 1-20 > "$SECRETS_DIR/$COOKIE_FILE"
chmod 0600 "$SECRETS_DIR/$COOKIE_FILE"
echo "Generated RabbitMQ cookie: $(cat "$SECRETS_DIR/$COOKIE_FILE")"