from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, hash_password, user_by_email, verify_password
from app.db import get_db
from app.models import User
from app.schemas import AuthRequest, TokenResponse, UserOut

router = APIRouter()


def _token(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_token(user.id), user=UserOut(id=user.id, email=user.email))


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: AuthRequest, session: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.lower()
    if user_by_email(session, email) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    return _token(user)


@router.post("/login", response_model=TokenResponse)
def login(body: AuthRequest, session: Session = Depends(get_db)) -> TokenResponse:
    user = user_by_email(session, body.email.lower())
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email)
