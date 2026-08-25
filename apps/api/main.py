from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import timedelta

from apps.api.core.config import settings
from apps.api.core.security import get_password_hash, verify_password, create_access_token, decode_token
from apps.api.realtime.websocket import router as ws_router
from apps.api.simulator.demo_simulator import simulator_instance

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket router
app.include_router(ws_router, prefix=settings.API_V1_STR)

# In-memory demo store for immediate development/testing
DEMO_USERS_DB = {}
DEMO_GROUPS_DB = {
    "grp_demo_rally": {
        "id": "grp_demo_rally",
        "name": "Pacific Coast Expedition",
        "code": "RALLY2026",
        "max_members": 20,
        "safe_distance_threshold_m": 150.0,
        "drifting_threshold_m": 250.0,
        "critical_separation_m": 350.0,
        "created_at": "2026-08-24T00:00:00Z"
    }
}

# Schemas
class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class GroupCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    max_members: Optional[int] = 20

@app.get("/")
async def root():
    return {
        "message": "Welcome to RALLY Real-time Group Mobility Intelligence Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "online"
    }

@app.get(f"{settings.API_V1_STR}/health")
async def health_check():
    return {"status": "ok", "service": "RALLY Core API"}

# Auth API
@app.post(f"{settings.API_V1_STR}/auth/register", response_model=TokenResponse)
async def register(payload: RegisterSchema):
    if payload.email in DEMO_USERS_DB:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed = get_password_hash(payload.password)
    user_id = f"usr_{len(DEMO_USERS_DB) + 1}"
    user_data = {
        "id": user_id,
        "email": payload.email,
        "full_name": payload.full_name,
        "phone": payload.phone,
        "role": "USER",
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={payload.full_name}"
    }
    DEMO_USERS_DB[payload.email] = {**user_data, "hashed_password": hashed}

    access_token = create_access_token(user_id)
    return {"access_token": access_token, "token_type": "bearer", "user": user_data}

@app.post(f"{settings.API_V1_STR}/auth/login", response_model=TokenResponse)
async def login(payload: LoginSchema):
    user = DEMO_USERS_DB.get(payload.email)
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_data = {k: v for k, v in user.items() if k != "hashed_password"}
    access_token = create_access_token(user["id"])
    return {"access_token": access_token, "token_type": "bearer", "user": user_data}

# Demo Simulator Endpoint
@app.get(f"{settings.API_V1_STR}/demo/simulation")
async def get_demo_simulation(step: int = Query(0, ge=0)):
    """Returns dynamic real-time group movement intelligence simulation state."""
    return simulator_instance.get_simulation_step(step)

# Group endpoints
@app.get(f"{settings.API_V1_STR}/groups")
async def list_groups():
    return list(DEMO_GROUPS_DB.values())

@app.post(f"{settings.API_V1_STR}/groups")
async def create_group(payload: GroupCreateSchema):
    group_id = f"grp_{len(DEMO_GROUPS_DB) + 1}"
    new_group = {
        "id": group_id,
        "name": payload.name,
        "description": payload.description,
        "code": f"RALLY{len(DEMO_GROUPS_DB) + 100}",
        "max_members": payload.max_members,
        "safe_distance_threshold_m": 150.0,
        "drifting_threshold_m": 250.0,
        "critical_separation_m": 350.0,
        "created_at": "2026-08-24T00:00:00Z"
    }
    DEMO_GROUPS_DB[group_id] = new_group
    return new_group
