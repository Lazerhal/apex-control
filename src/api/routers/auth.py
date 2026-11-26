from fastapi import APIRouter, HTTPException, status, Response, Request
from pydantic import BaseModel
from src.auth import verify_password, create_access_token
from src.config import get_settings
from src.events import emit

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
        # The submitted username is not recorded: it could be a mistyped password
        await emit("auth.login_failure", "api", status="error",
                   payload={"reason": "unknown_username"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Validate password
    if not verify_password(data.password, settings.apex_dashboard_password_hash):
        await emit("auth.login_failure", "api", actor=settings.apex_dashboard_username[:50],
                   status="error", payload={"reason": "bad_password"})
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
    
    await emit("auth.login_success", "api", actor=data.username[:50])
    
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
