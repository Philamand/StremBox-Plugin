from typing import Annotated

import asyncpg
from fastapi import Depends, HTTPException, Path, Request

from db.database import get_db_conn
from services.users import UserService


async def get_user_service(
    conn: Annotated[asyncpg.Connection, Depends(get_db_conn)],
) -> UserService:
    """Return a UserService instance with the given database connection."""
    return UserService(conn)


async def check_user_key(
    request: Request,
    user_service: Annotated[UserService, Depends(get_user_service)],
    user_key: Annotated[str, Path(description="Per-user key embedded in the URL")],
) -> None:
    """Checks the user key and raises an HTTPException if it is invalid."""

    try:
        user = await user_service.get_user(user_key)
    except ValueError, asyncpg.exceptions.DataError:
        raise HTTPException(status_code=401, detail="Invalid user key")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid user key")

    request.state.user = user
