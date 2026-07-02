from fastapi import APIRouter, HTTPException, status, Response, Request
from pydantic import BaseModel
from src.auth import verify_password, create_access_token
from src.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, response: Response):
    # Validate username
    if data.username != settings.apex_dashboard_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Validate password
    if not verify_password(data.password, settings.apex_dashboard_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    token = create_access_token({"sub": data.username, "type": "dashboard"})
    
    # Set cookie for browser-based access
    response.set_cookie(
        key="apex_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400  # 24 hours
    )
    
    return LoginResponse(access_token=token, username=data.username)

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("apex_token")
    return {"message": "Logged out"}

@router.get("/me")
async def me(request: Request):
    from src.auth import get_current_user, security
    from fastapi import Depends
    token = request.cookies.get("apex_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from src.auth import verify_token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": payload.get("sub"), "authenticated": True}
