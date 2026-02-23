import os
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict

import psycopg
from dotenv import load_dotenv
from psycopg import Cursor, Error, errors, sql

load_dotenv()


class TestMarkerConfig(TypedDict):
    table: str
    col_id: str
    col_label: str
    col_created: str
    val_id: int
    val_label: str


TEST_MARKER_CONFIG: TestMarkerConfig = {
    "table": "test_marker",
    "col_id": "id",
    "col_label": "label",
    "col_created": "created_at",
    "val_id": 1,
    "val_label": "TEST_DB",
}


class Mode(StrEnum):
    NONE = "none"
    TEST = "test"


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
    mode: Mode = Mode.NONE


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
        mode=Mode(get_environment("MODE", Mode.NONE)),
    )

    return config


def initialize_db():
    config = load_environment()

    run_as_superuser(
        config,
        [
            create_admin_user,
            create_app_user,
            create_database,
            grant_connect_admin_user,
            grant_connect_app_user,
        ],
        autocommit=True,
    )  # CREATE DATABASE can't be in a txn
    run_as_admin(
        config,
        [
            create_schema,
            grant_schema_admin_user,
            grant_schema_app_user,
            grant_on_tables_app_user,
            grant_on_sequences_app_user,
            alter_default_privileges_tables_app_user,
            alter_default_privileges_sequences_app_user,
            process_initialize_test_mode,
        ],
    )
    run_as_superuser(config, [alter_search_path_app_user])


def teardown_db():
    config = load_environment()

    if teardown_check_test_mode(config):
        print("performing teardown tasks")
        run_as_superuser(config, [drop_db], autocommit=True)
    else:
        print("skipping teardown tasks")


@contextmanager
def connect_db(
    *,
    host: str,
    port: str,
    dbname: str,
    user: str,
    password: str,
    autocommit: bool = False,
):
    with (
        psycopg.connect(
            dbname=dbname,
            host=host,
            port=port,
            user=user,
            password=password,
            autocommit=autocommit,
        ) as conn,
        conn.cursor() as cursor,
    ):
        yield cursor
        if not autocommit:
            conn.commit()


def run_as_superuser(
    config: Env, tasks: list[Callable[[Cursor, Env], None]], *, autocommit: bool = False
):
    with connect_db(
        dbname="postgres",
        host=config.host,
        port=config.port,
        user=config.superuser,
        password=config.superuser_pass,
        autocommit=autocommit,
    ) as cursor:
        for task in tasks:
            print(f"Running task {task.__name__}")
            task(cursor, config)


def process_initialize_test_mode(cur: Cursor, config: Env):
    print(f"Configured MODE={config.mode}")
    if config.mode == Mode.TEST:
        create_test_marker(cur)
        insert_test_marker(cur)
    else:
        print(f"No tasks for mode {config.mode}")


def create_test_marker(cur: Cursor):
    cur.execute(
        sql.SQL("""
        CREATE TABLE IF NOT EXISTS {} (
            {} int PRIMARY KEY,
            {} text NOT NULL,
            {} timestamp with time zone DEFAULT now() 
        )
    """).format(
            sql.Identifier(TEST_MARKER_CONFIG["table"]),
            sql.Identifier(TEST_MARKER_CONFIG["col_id"]),
            sql.Identifier(TEST_MARKER_CONFIG["col_label"]),
            sql.Identifier(TEST_MARKER_CONFIG["col_created"]),
        )
    )
    print(f"Ensured table {TEST_MARKER_CONFIG['table']} exists")


def insert_test_marker(cur: Cursor):
    cur.execute(
        sql.SQL("""
            INSERT INTO {} ({}, {}) VALUES (%s, %s)
            ON CONFLICT ({}) DO NOTHING
        """).format(
            sql.Identifier(TEST_MARKER_CONFIG["table"]),
            sql.Identifier(TEST_MARKER_CONFIG["col_id"]),
            sql.Identifier(TEST_MARKER_CONFIG["col_label"]),
            sql.Identifier(TEST_MARKER_CONFIG["col_id"]),
        ),
        (TEST_MARKER_CONFIG["val_id"], TEST_MARKER_CONFIG["val_label"]),
    )
    print("Inserted test marker")


def create_admin_user(cursor: Cursor, config: Env):
    create_user(cursor, config.admin_user, config.admin_pass, "Admin")


def create_app_user(cursor: Cursor, config: Env):
    create_user(cursor, config.app_user, config.app_pass, "App")


def create_user(cursor: Cursor, username: str, password: str, user_type: str):
    try:
        cursor.execute(create_user_cmd(username, password))
        print(f"{user_type} user {username} created.")
    except errors.DuplicateObject:
        print(f"{user_type} user {username} already exists. Skipping creation.")


def create_database(cursor: Cursor, config: Env):
    try:
        cursor.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(config.database), sql.Identifier(config.admin_user)
            )
        )
        print(f"Database {config.database} created.")
    except errors.DuplicateDatabase:
        print(f"Database {config.database} already exists. Skipping creation.")


def grant_connect_admin_user(cursor: Cursor, config: Env):
    cursor.execute(grant_connect_db_cmd(config.database, config.admin_user))


def grant_connect_app_user(cursor: Cursor, config: Env):
    cursor.execute(grant_connect_db_cmd(config.database, config.app_user))


def teardown_check_test_mode(config: Env):
    print(f"Configured MODE={config.mode}")
    if config.mode == Mode.TEST:
        has_test_marker = check_test_marker(config)
        print(f"test marker present? {'Y' if has_test_marker else 'N'}")
        return has_test_marker

    return False


def drop_db(cursor: Cursor, config: Env):
    cursor.execute(drop_db_cmd(config.database))
    print(f"Test database {config.database} dropped.")


def check_test_marker(config: Env):
    with connect_db(
        dbname=config.database,
        host=config.host,
        port=config.port,
        user=config.superuser,
        password=config.superuser_pass,
    ) as cursor:
        try:
            cursor.execute(
                sql.SQL("""
                SELECT * FROM {} WHERE {} = %s
            """).format(
                    sql.Identifier(TEST_MARKER_CONFIG["table"]),
                    sql.Identifier(TEST_MARKER_CONFIG["col_id"]),
                ),
                (TEST_MARKER_CONFIG["val_id"],),
            )
            return cursor.fetchone() is not None
        except Error as exc:
            print(exc)
            return False


def drop_db_cmd(database: str):
    return sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))


def run_as_admin(config: Env, tasks: list[Callable[[Cursor, Env], None]]):
    # run as admin user, connecting to target database
    with (
        connect_db(
            dbname=config.database,
            host=config.host,
            port=config.port,
            user=config.admin_user,
            password=config.admin_pass,
        ) as cursor,
    ):
        for task in tasks:
            print(f"Running task {task.__name__}")
            task(cursor, config)


def create_schema(cur: Cursor, config: Env):
    cur.execute(
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(config.schema))
    )


def grant_schema_admin_user(cur: Cursor, config: Env):
    cur.execute(grant_schema_cmd(config.schema, config.admin_user))


def grant_schema_app_user(cur: Cursor, config: Env):
    cur.execute(grant_schema_cmd(config.schema, config.app_user))


def grant_on_tables_app_user(cur: Cursor, config: Env):
    cur.execute(
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}"
        ).format(sql.Identifier(config.schema), sql.Identifier(config.app_user))
    )


def grant_on_sequences_app_user(cur: Cursor, config: Env):
    cur.execute(
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
            sql.Identifier(config.schema), sql.Identifier(config.app_user)
        )
    )


def alter_default_privileges_tables_app_user(cur: Cursor, config: Env):
    cur.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR USER {} IN SCHEMA {} "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(
            sql.Identifier(config.admin_user),  # owner
            sql.Identifier(config.schema),
            sql.Identifier(config.app_user),
        )
    )


def alter_default_privileges_sequences_app_user(cursor: Cursor, config: Env):
    cursor.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR USER {} IN SCHEMA {} "
            "GRANT USAGE, SELECT ON SEQUENCES TO {}"
        ).format(
            sql.Identifier(config.admin_user),  # owner
            sql.Identifier(config.schema),
            sql.Identifier(config.app_user),
        )
    )


def create_user_cmd(username: str, password: str):
    return sql.SQL("CREATE USER {} WITH ENCRYPTED PASSWORD {}").format(
        sql.Identifier(username), sql.Literal(password)
    )


def grant_connect_db_cmd(database: str, username: str):
    return sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
        sql.Identifier(database), sql.Identifier(username)
    )


def grant_schema_cmd(schema: str, username: str):
    return sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
        sql.Identifier(schema), sql.Identifier(username)
    )


def alter_search_path_cmd(schema: str, username: str):
    return sql.SQL("ALTER USER {} SET search_path TO {},public").format(
        sql.Identifier(username), sql.Identifier(schema)
    )


def alter_search_path_app_user(cursor: Cursor, config: Env):
    cursor.execute(
        sql.SQL("ALTER USER {} SET search_path TO {},public").format(
            sql.Identifier(config.app_user), sql.Identifier(config.schema)
        )
    )
