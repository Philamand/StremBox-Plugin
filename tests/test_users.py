# This file is AI-generated
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from dependencies import get_user_service
from main import app
from schemas.users import UserCreateData, UserData
from services.users import UserService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_create_data(
    librebox_url: str = "https://librebox.example.com",
    librebox_token: str = "token-abc",
    *,
    c411_key: str | None = "c411-key-123",
    tr4ker_key: str | None = "tr4ker-key-456",
    lacale_key: str | None = "lacale-key-789",
) -> UserCreateData:
    """Build a UserCreateData with sensible defaults so tests stay concise."""
    return UserCreateData(
        librebox_url=librebox_url,
        librebox_token=librebox_token,
        c411_key=c411_key,
        tr4ker_key=tr4ker_key,
        lacale_key=lacale_key,
    )


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


async def test_create_user_returns_uuid_string(conn: asyncpg.Connection) -> None:
    """create_user should return the new user's ID as a string."""
    svc = UserService(conn)
    user_id = await svc.create_user(_make_create_data())

    # Must be a valid UUID (asyncpg returns a UUID object; str() for safety).
    uuid.UUID(str(user_id))


async def test_create_user_persists_all_fields(conn: asyncpg.Connection) -> None:
    """Every field supplied at creation must be persisted correctly."""
    svc = UserService(conn)
    data = _make_create_data(
        librebox_url="https://box.org",
        librebox_token="secret",
        c411_key="c411-x",
        tr4ker_key="tr4ker-y",
        lacale_key="lacale-z",
    )
    user_id = await svc.create_user(data)

    row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    assert row is not None
    assert row["librebox_url"] == data.librebox_url
    assert row["librebox_token"] == data.librebox_token
    assert row["c411_key"] == data.c411_key
    assert row["tr4ker_key"] == data.tr4ker_key
    assert row["lacale_key"] == data.lacale_key


async def test_create_user_optional_keys_can_be_none(conn: asyncpg.Connection) -> None:
    """None values in optional key fields should round-trip as NULL."""
    svc = UserService(conn)
    data = _make_create_data(c411_key=None, tr4ker_key=None, lacale_key=None)
    user_id = await svc.create_user(data)

    row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    assert row is not None
    assert row["c411_key"] is None
    assert row["tr4ker_key"] is None
    assert row["lacale_key"] is None


async def test_create_user_different_users_get_different_ids(
    conn: asyncpg.Connection,
) -> None:
    """Two users created independently must receive distinct IDs."""
    svc = UserService(conn)
    id_a = await svc.create_user(_make_create_data())
    id_b = await svc.create_user(_make_create_data(librebox_url="https://other.box"))
    assert id_a != id_b


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------


async def test_get_user_returns_user_data(conn: asyncpg.Connection) -> None:
    """get_user should return a UserData matching the created row."""
    svc = UserService(conn)
    created_id = await svc.create_user(
        _make_create_data(
            librebox_url="https://get.me",
            librebox_token="tok",
            c411_key="ck",
            tr4ker_key="tk",
            lacale_key="lk",
        )
    )

    user = await svc.get_user(created_id)

    assert isinstance(user, UserData)
    assert str(user.id) == str(created_id)
    assert user.librebox_url == "https://get.me"
    assert user.librebox_token == "tok"
    assert user.c411_key == "ck"
    assert user.tr4ker_key == "tk"
    assert user.lacale_key == "lk"


async def test_get_user_nonexistent_raises_valueerror(conn: asyncpg.Connection) -> None:
    """Querying a non-existent user ID must raise ValueError."""
    svc = UserService(conn)
    fake_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(ValueError, match="User not found"):
        await svc.get_user(fake_id)


# ---------------------------------------------------------------------------
# Route tests (HTTP layer)
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(
    conn: asyncpg.Connection,
) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client with UserService dependency overridden for testing.

    The ``get_user_service`` dependency is replaced so that the test database
    connection (from the ``conn`` fixture) is used instead of the real pool.
    """

    def _get_test_user_service() -> UserService:
        return UserService(conn)

    app.dependency_overrides[get_user_service] = _get_test_user_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def test_index_returns_html(client: AsyncClient) -> None:
    """GET / should return an HTML response with status 200."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_create_user_returns_user_id(client: AsyncClient) -> None:
    """POST / with valid form data should create a user and return the ID."""
    resp = await client.post(
        "/",
        data={
            "librebox_url": "https://librebox.example.com",
            "librebox_token": "test-token",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data
    # Must be a valid UUID
    uuid.UUID(data["user_id"])


async def test_create_user_persists_in_db(
    client: AsyncClient, conn: asyncpg.Connection
) -> None:
    """POST / should persist every field in the database."""
    resp = await client.post(
        "/",
        data={
            "librebox_url": "https://persist.example.com",
            "librebox_token": "persist-token",
            "c411_key": "c411-persist",
            "tr4ker_key": "tr4ker-persist",
            "lacale_key": "lacale-persist",
        },
    )
    assert resp.status_code == 200
    user_id = resp.json()["user_id"]

    row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    assert row is not None
    assert row["librebox_url"] == "https://persist.example.com"
    assert row["librebox_token"] == "persist-token"
    assert row["c411_key"] == "c411-persist"
    assert row["tr4ker_key"] == "tr4ker-persist"
    assert row["lacale_key"] == "lacale-persist"


async def test_create_user_optional_keys_can_be_omitted(client: AsyncClient) -> None:
    """POST / without optional keys should succeed (they default to None/NULL)."""
    resp = await client.post(
        "/",
        data={
            "librebox_url": "https://minimal.example.com",
            "librebox_token": "minimal-token",
        },
    )
    assert resp.status_code == 200
    user_id = resp.json()["user_id"]
    uuid.UUID(user_id)
