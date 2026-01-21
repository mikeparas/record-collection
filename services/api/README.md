# Database

## Managing users

It is expected that the application database will already be created before running these scripts.

### Creating users

```bash
uv run poe db_users_create [type] [username] [password] [database] -u [database username]
```
Specify which user will execute the command with the `-u` option (e.g. `postgres`).

`type` can be `app` or `manage`.

For `app` users, you can supply `--skip-grants` to simply create a user account. Any needed permissions will need to be added manually.

For `manage` users, you can supply `--allow-createdb`. This will give the user privileges to create new databases. **This should only be used in non-production environments.**

### Deleting users

```bash
uv run poe db_users_delete [username] [database] -u [database username]
```

### psql options

For both the create and delete scripts, you may provide the connection host and port, as well as an alternative `psql` command, if needed.

Use these CLI options or environment variables:
* `-h [host]` or `PSQL_HOST`
* `-p [port]` or `PSQL_PORT`
* `-c [command]` or `PSQL_CMD`

Environment variables can be set for the task definitions in `pyproject.toml`.

```toml
[tool.poe.tasks.db_user_create]
cmd = "scripts/db_users.py create"
env = {PSQL_CMD = "psql-17", PSQL_HOST = "localhost", PSQL_PORT="5433"}
```

### Recommended usage

* Create an `app` user for use with the FastAPI application as well as for running Alembic migrations.
* For local or testing environments:
  * Create a `manage` user with `--allow-createdb`. This user will be used to create a test version of the database for integration/end-to-end testing.
  * Create an `app` user with `--skip-grants`. This user will be used to run integration/end-to-end tests.