import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

import psycopg
from alembic.config import Config
from dotenv import load_dotenv
from psycopg import errors, sql

from alembic import command

load_dotenv()


@dataclass(kw_only=True)
class Env:
    superuser: str
    superuser_pass: str
    database: str
    schema: str
    host: str
    port: str
    admin_user: str
    admin_pass: str
    app_user: str
    app_pass: str
    test_database: str | None = None
    test_user: str | None = None
    test_pass: str | None = None


def get_environment(key: str, default: str | None = None) -> str:
    envval = os.getenv(key, default)
    if envval is None:
        raise RuntimeError(f"{key} not set in environment")

    return envval


def load_environment():
    config = Env(
        superuser=get_environment("DB_SUPERUSER", "postgres"),
        superuser_pass=get_environment("DB_SUPERUSER_PASS"),
        database=get_environment("DB_NAME"),
        schema=get_environment("DB_SCHEMA"),
        host=get_environment("DB_HOST", "localhost"),
        port=get_environment("DB_PORT", "5432"),
        admin_user=get_environment("DB_ADMIN_USER"),
        admin_pass=get_environment("DB_ADMIN_PASS"),
        app_user=get_environment("DB_APP_USER"),
        app_pass=get_environment("DB_APP_PASS"),
    )

    test_database = get_environment("DB_TEST_DATABASE", "")
    if len(test_database) > 0:
        config.test_database = test_database
        config.test_user = get_environment("DB_TEST_USER")
        config.test_pass = get_environment("DB_TEST_PASS")

    return config


def initialize():
    config = load_environment()

    init_db(config)
    init_users(config)
    alter_user_search_path(config)

    # build connection url for alembic to use
    os.environ["DB_MIGRATE"] = config.database
    run_migrations()


def run_migrations():
    scripts_dir = Path(__file__).parent.resolve()

    proj_root = scripts_dir.parent
    alembic_ini_path = proj_root / "alembic.ini"

    alembic_config = Config(alembic_ini_path)

    command.upgrade(alembic_config, "head")


def build_database_url(config: Env):
    safe_password = quote_plus(config.admin_pass)
    return f"postgresql+psycopg://{config.admin_user}:{safe_password}@{config.host}:{config.port}/{config.database}"


def init_db(config: Env):
    # run as superuser
    with (
        psycopg.connect(
            dbname="postgres",
            host=config.host,
            port=config.port,
            user=config.superuser,
            password=config.superuser_pass,
            autocommit=True,  # CREATE DATABASE can't be in a transaction
        ) as conn,
        conn.cursor() as cur,
    ):
        # create users
        try:
            cur.execute(create_user_cmd(config.admin_user, config.admin_pass))
            print(f"Admin user {config.admin_user} created.")
        except errors.DuplicateObject:
            print(f"User {config.admin_user} already exists. Skipping creation.")

        try:
            cur.execute(create_user_cmd(config.app_user, config.app_pass))
            print(f"App user {config.app_user} created.")
        except errors.DuplicateObject:
            print(f"User {config.app_user} already exists. Skipping creation.")

        if (
            config.test_database is not None
            and config.test_user is not None
            and config.test_pass is not None
        ):
            try:
                cur.execute(create_user_cmd(config.test_user, config.test_pass))
                print(f"Test user {config.test_user} created.")
            except errors.DuplicateObject:
                print(f"User {config.test_user} already exists. Skipping creation.")

        # create database and set owner to admin user
        try:
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(config.database), sql.Identifier(config.admin_user)
                )
            )
            print(f"Database {config.database} created.")
        except errors.DuplicateDatabase:
            print(f"Database {config.database} already exists. Skipping creation.")

        # grant connect to admin user and app user
        cur.execute(grant_connect_db_cmd(config.database, config.admin_user))
        cur.execute(grant_connect_db_cmd(config.database, config.app_user))


def app_user_cmds(*, schema: str, username: str, owner: str) -> list[sql.Composed]:
    return [
        # grant usage on schema
        grant_schema_cmd(schema, username),
        # grant select, insert, update, delete on tables
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}"
        ).format(sql.Identifier(schema), sql.Identifier(username)),
        # grant usage, select on sequences
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
            sql.Identifier(schema), sql.Identifier(username)
        ),
        # alter table default privileges
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR USER {} IN SCHEMA {} "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(
            sql.Identifier(owner),
            sql.Identifier(schema),
            sql.Identifier(username),
        ),
        # alter sequence default privileges
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR USER {} IN SCHEMA {} "
            "GRANT USAGE, SELECT ON SEQUENCES TO {}"
        ).format(
            sql.Identifier(owner),
            sql.Identifier(schema),
            sql.Identifier(username),
        ),
    ]


def init_users(config: Env):
    # run as admin user, connecting to target database
    with (
        psycopg.connect(
            dbname=config.database,
            host=config.host,
            port=config.port,
            user=config.admin_user,
            password=config.admin_pass,
        ) as conn,
        conn.cursor() as cur,
    ):
        # create schema
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(config.schema)
            )
        )

        # grant usage and create on schema to admin user
        cur.execute(grant_schema_cmd(config.schema, config.admin_user))

        user_cmds = app_user_cmds(
            schema=config.schema, username=config.app_user, owner=config.admin_user
        )
        for cmd in user_cmds:
            cur.execute(cmd)

        conn.commit()


def alter_user_search_path(config: Env):
    # run as superuser
    with (
        psycopg.connect(
            dbname="postgres",
            host=config.host,
            port=config.port,
            user=config.superuser,
            password=config.superuser_pass,
        ) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(alter_search_path_cmd(config.schema, config.app_user))

        if config.test_database is not None and config.test_user is not None:
            cur.execute(alter_search_path_cmd(config.schema, config.test_user))
            print(f"Test user {config.test_user} search_path set.")

        conn.commit()


def create_user_cmd(username: str, password: str):
    return sql.SQL("CREATE USER {} WITH ENCRYPTED PASSWORD {}").format(
        sql.Identifier(username), sql.Literal(password)
    )


def grant_connect_db_cmd(database: str, username: str):
    return sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
        sql.Identifier(database), sql.Identifier(username)
    )


def grant_schema_cmd(schema: str, username: str):
    return sql.SQL("GRANT USAGE ON schema {} TO {}").format(
        sql.Identifier(schema), sql.Identifier(username)
    )


def alter_search_path_cmd(schema: str, username: str):
    return sql.SQL("ALTER USER {} SET search_path TO {},public").format(
        sql.Identifier(username), sql.Identifier(schema)
    )


if __name__ == "__main__":
    initialize()
