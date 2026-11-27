"""Hard guard: the tests truncate tables, so they must only ever reach a throwaway database."""
from urllib.parse import unquote, urlsplit

LIVE_PORT = 5433  # the live apex database
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class UnsafeDatabaseError(RuntimeError):
    pass


def check_database_url(url: str) -> str:
    """Return the URL if it can only point at a local test database, otherwise raise.

    Messages never include the URL, which contains a password.
    """
    def refuse(reason: str):
        raise UnsafeDatabaseError(f"Refusing to run tests: {reason}")

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        refuse("the database URL could not be parsed")
    if parts.scheme not in ("postgresql", "postgresql+asyncpg"):
        refuse("the database URL is not a postgresql URL")
    if port is None:
        refuse("the database URL has no explicit port")
    if port == LIVE_PORT:
        refuse(f"port {LIVE_PORT} is the live apex database")
    if parts.hostname not in LOCAL_HOSTS:
        refuse("the database host is not local")
    # Query parameters such as ?port= or ?host= would override what was checked above
    if parts.query or parts.fragment:
        refuse("the database URL has query parameters")
    if not unquote(parts.path.lstrip("/")).endswith("_test"):
        refuse("the database name does not end in _test, so it may be the live apex database")
    return url


def check_database_is_empty(table_count: int) -> None:
    """A throwaway database starts empty; tables mean it holds someone's data."""
    if table_count:
        raise UnsafeDatabaseError(
            f"Refusing to run tests: the database already has {table_count} tables. "
            "Point TEST_DATABASE_URL at a new, empty database."
        )
