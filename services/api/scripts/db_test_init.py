import os
from dataclasses import dataclass
from urllib.parse import quote_plus

import psycopg
from dotenv import load_dotenv
from psycopg import errors, sql

from scripts.db_init import (
    app_user_cmds,
    get_environment,
    grant_connect_db_cmd,
    grant_schema_cmd,
    run_migrations,
)

load_dotenv()  # can use same as setup script


@dataclass(kw_only=True)
class Env:
    superuser: str
    superuser_pass: str
    schema: str
    host: str
    port: str
    admin_user: str
    admin_pass: str
    # keeping following as test_ to make explicit
    test_database: str
    test_user: str
    test_pass: str


def load_environment():
    return Env(
        superuser=get_environment("DB_SUPERUSER", "postgres"),
        superuser_pass=get_environment("DB_SUPERUSER_PASS"),
        schema=get_environment("DB_SCHEMA"),
        host=get_environment("DB_HOST", "localhost"),
        port=get_environment("DB_PORT", "5432"),
        admin_user=get_environment("DB_ADMIN_USER"),
        admin_pass=get_environment("DB_ADMIN_PASS"),
        test_database=get_environment("DB_TEST_DATABASE"),
        test_user=get_environment("DB_TEST_USER"),
        test_pass=get_environment("DB_TEST_PASS"),
    )


def build_database_url(config: Env):
    safe_password = quote_plus(config.admin_pass)
    return f"postgresql+psycopg://{config.admin_user}:{safe_password}@{config.host}:{config.port}/{config.test_database}"


def initialize_db():
    config = load_environment()

    init_db(config)
    init_users(config)

    # build connection url for alembic to use
    os.environ["DB_MIGRATE"] = config.test_database
    run_migrations()


def teardown_db():
    config = load_environment()

    # drop database
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
        cur.execute(drop_db_cmd(config.test_database))
        print(f"Test database {config.test_database} dropped.")


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
        # users should already exist

        # drop just in case
        cur.execute(drop_db_cmd(config.test_database))
        print(f"Dropping {config.test_database}...")

        # create database and set owner
        try:
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(config.test_database),
                    sql.Identifier(config.admin_user),
                )
            )
            print(f"Database {config.test_database} created.")
        except errors.DuplicateDatabase:
            print(f"Database {config.test_database} already exists. Skipping creation.")

        # grant connect to admin and test users
        cur.execute(grant_connect_db_cmd(config.test_database, config.admin_user))
        cur.execute(grant_connect_db_cmd(config.test_database, config.test_user))


def init_users(config: Env):
    # run as admin user connecting to test database
    with (
        psycopg.connect(
            dbname=config.test_database,
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
            schema=config.schema, username=config.test_user, owner=config.admin_user
        )
        for cmd in user_cmds:
            cur.execute(cmd)

        conn.commit()


def drop_db_cmd(database: str):
    return sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
