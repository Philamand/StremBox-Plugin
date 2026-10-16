from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from constants import CERTIFICATIONS
from dependencies import get_user_service
from schemas.users import UserCreateData
from services.users import UserService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Display the index page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"certifications": CERTIFICATIONS},
    )


@router.post("/", response_class=HTMLResponse)
async def create_user(
    request: Request,
    data: Annotated[UserCreateData, Form()],
    service: Annotated[UserService, Depends(get_user_service)],
):
    """Create a new user."""
    user_id = await service.create_user(data)
    return templates.TemplateResponse(
        request=request, name="success.html", context={"user_id": user_id}
    )


@router.get("/{user_id}/", response_class=HTMLResponse)
async def get_user(
    request: Request,
    user_id: str,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """Get a user by ID and display the setup page."""
    try:
        user = await service.get_user(user_id)
    except ValueError:
        raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        request=request, name="index.html", context={"user": user}
    )


@router.post("/{user_id}/", response_class=HTMLResponse)
async def update_user(
    request: Request,
    data: Annotated[UserCreateData, Form()],
    user_id: str,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """Update a user by ID."""
    try:
        await service.update_user(user_id, data)
    except ValueError:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request, name="success.html", context={"user_id": user_id}
    )
