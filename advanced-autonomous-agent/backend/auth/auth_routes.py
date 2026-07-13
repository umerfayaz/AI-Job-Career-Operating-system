import os
import time
import httpx
from uuid import uuid4
import bcrypt
import structlog
from backend.redis.redis_memory import redis_client
from datetime import datetime, timedelta, timezone, UTC
from fastapi import APIRouter, HTTPException, Depends, Request
from backend.application import get_agent_app
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()
logger = structlog.get_logger()


# Turnstille Secret Key
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")

# JWT Secret key
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise Exception("JWT SECRET KEY is not Set")

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    captcha_token: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_token: str | None = None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    return await decode_token(credentials.credentials)

async def get_db_instance():
    agent_app = await get_agent_app()
    return agent_app.multi_agent_orchestrator.outcome_loop.outcome_database
    

def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload ={"sub": user_id, "user_id": user_id, "exp": expire, "iat": datetime.now(timezone.utc)}
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM )
    return token

async def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload["user_id"]

        stored_token = await redis_client.get(f"session:{user_id}")
        if stored_token !=token:
            raise HTTPException(
              status_code = 401,
              detail="Session expired"
            )
            

        return payload["user_id"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Rate Limiting for signup
async def rate_limit(key: str, limit: int = 4, window: int = 60, block: bool = True):
    now = int(time.time())

    redis_key = f"rate:{key}:{now // window}"
    count = await redis_client.incr(redis_key)

    if count ==1:
        await redis_client.expire(redis_key, window)
    
    if block and count > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down."
        )
    
    return count > limit


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    db = await get_db_instance()
    try:
        user = await db.get_active_user_id(user_id)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="User not found"
            )
        return {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "created_at": user.created_at
        }
    
    except HTTPException:
        raise

    except Exception:
       logger.error("Error in signup", exc_info=True)

       raise HTTPException(
        status_code=404, 
        detail="No user found"
    )


@router.post("/signup")
async def signup(body: SignupRequest, request: Request):
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    db = await get_db_instance()

    try: 

        #limiting signup and email requests for the user
        ip = request.client.host

        await rate_limit(
            key = f"sign_ip:{ip}",
            limit=5,
            window=3600,
            block=True
        )

        captcha_required = await rate_limit(
            key=f"signup_email:{body.email}",
            limit=5,
            window=3600,
            block=True
        )

        if captcha_required:
            if not body.captcha_token:
                raise HTTPException(
                    status_code=401,
                    detail="Captcha token required"
                )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data = {
                        "secret": TURNSTILE_SECRET_KEY,
                        "response": body.captcha_token,
                        "remoteip": request.client.host,
                    }
                )

                result = response.json()
                if not result.get("success"):
                    raise HTTPException(
                        status_code=401,
                        detail="Caption verification required"
                    )

        
        existing = await db.get_user_by_email(body.email)

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        password_hash = bcrypt.hashpw(
            body.password.encode(),
            bcrypt.gensalt()
        ).decode()

        user_id = f"user_id{uuid4().hex[:12]}"

        await db.create_user(
            user_id=user_id,
            email=body.email,
            name=body.name,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
            last_active=datetime.now(UTC)
        )

        token = create_token(user_id)

        # Session key for user signup
        session_key = f"session:{user_id}"
        await redis_client.set(
            session_key,
            token,
            ex=TOKEN_EXPIRE_MINUTES * 60
        )
        return {"token": token, "user_id": user_id, "name": body.name, "email": body.email}
    
    except HTTPException:
        raise
    
    except Exception:
        logger.error("Signup Failed", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Internal server error"
        ) 

@router.post("/login")
async def login(body: LoginRequest, request: Request):
    db = await get_db_instance()
    try:
        ip = request.client.host

        await rate_limit(
            key= f"login_ip:{ip}",
            limit=5,
            window=300,
            block=True
        )

        captcha_required = await rate_limit(
            key=f"login_email:{body.email}",
            limit=5,
            window=300,
            block= False
        )

        if captcha_required:
            if not body.captcha_token:
                raise HTTPException(
                    status_code=400,
                    detail="Captcha token required"
                )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data = {
                        "secret": TURNSTILE_SECRET_KEY,
                        "response": body.captcha_token,
                        "remoteip": request.client.host
                    }
                )

                result = response.json()
                if not result.get("success"):
                    raise HTTPException(
                        status_code=401,
                        detail="Captcha verification failed"
                    )


        user = await db.get_user_by_email(body.email)

        if not user:
            raise HTTPException(
                status_code=400,
                detail="Invalid credentials"
            )
        
        if not bcrypt.checkpw(
            body.password.encode(),
            user.password_hash.encode()
        ):
          
          raise HTTPException(
            status_code=401,
            detail="Incorrect password and email"
          )
        
        token = create_token(user.user_id)

        # Generating session key
        session_key = f"session:{user.user_id}"
        await redis_client.set(
            session_key,
            token,
            ex=TOKEN_EXPIRE_MINUTES * 60
        )

        return {"token": token, "user_id": user.user_id, "name": user.name, "email": user.email}
    
    except HTTPException:
        raise

    except Exception:
        logger.error("Login Failed", exc_info=True)

        raise HTTPException(
            status_code=500, 
            detail="Invalid Credentials"
        )


@router.post("/logout")
async def logout(user_id:str = Depends(get_current_user)):
    await redis_client.delete(f"session:{user_id}")

    return {"message": "logged out"}





