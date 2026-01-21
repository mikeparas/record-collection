import typer

from scripts.db_test_init import initialize_db, teardown_db

app = typer.Typer()


@app.command()
def setup():
    initialize_db()


@app.command()
def teardown():
    teardown_db()


if __name__ == "__main__":
    app()
