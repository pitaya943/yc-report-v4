"""Connection pool, and one connection and one transaction per request."""

from collections.abc import Iterator
from contextlib import contextmanager

from anyio import to_thread
from psycopg import Connection
from psycopg_pool import ConnectionPool
from starlette.requests import Request

PING_TIMEOUT_SECONDS = 2.0


class Database:
    def __init__(self, url: str, *, max_size: int = 10):
        self._pool = ConnectionPool(
            url,
            min_size=1,
            max_size=max_size,
            open=False,
            check=ConnectionPool.check_connection,
        )

    def open(self) -> None:
        # Does not wait for a connection: the application starts either way
        # and /health reports whether the database answers.
        self._pool.open(wait=False)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """A transaction of its own: committed on exit, rolled back on an exception."""
        with self._pool.connection() as conn:
            yield conn

    def ping(self) -> bool:
        try:
            with self._pool.connection(timeout=PING_TIMEOUT_SECONDS) as conn:
                conn.execute("select 1")
            return True
        except Exception:
            return False


class RequestTransaction:
    """The transaction of one request. The connection is taken on first use."""

    def __init__(self, database: Database):
        self._pool = database._pool
        self._conn: Connection | None = None

    def connection(self) -> Connection:
        if self._conn is None:
            self._conn = self._pool.getconn()
        return self._conn

    def finish(self, *, commit: bool) -> None:
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            if commit:
                conn.commit()
            else:
                conn.rollback()
        finally:
            self._pool.putconn(conn)


class TransactionMiddleware:
    """Commit when the response is a success, roll back otherwise.

    The decision is taken before the first byte of the response leaves, so a
    client never sees a success whose commit failed. A response with status
    400 or above, and an exception nobody handled, both roll back.
    """

    def __init__(self, app, database: Database):
        self.app = app
        self._database = database

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        tx = RequestTransaction(self._database)
        scope.setdefault("state", {})["tx"] = tx

        async def send_after_finishing(message):
            if message["type"] == "http.response.start":
                commit = message["status"] < 400
                await to_thread.run_sync(lambda: tx.finish(commit=commit))
            await send(message)

        try:
            await self.app(scope, receive, send_after_finishing)
        finally:
            await to_thread.run_sync(lambda: tx.finish(commit=False))


def request_transaction(request: Request) -> RequestTransaction:
    return request.state.tx


def connection(request: Request) -> Connection:
    """FastAPI dependency: this request's connection, inside its transaction."""
    return request_transaction(request).connection()
