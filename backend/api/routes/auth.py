from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from passlib.context import CryptContext
from backend.database import mongo
import jwt
from datetime import datetime, timedelta
import os
from backend.api.dependencies import get_current_admin, SECRET_KEY, ALGORITHM

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginReq):
    admin = mongo.db.admins.find_one({"username": req.username})
    if not admin or not pwd_context.verify(req.password, admin["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = jwt.encode({
        "sub": str(admin["_id"]),
        "username": admin["username"],
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=24)
    }, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"data": {"token": token}}

@router.post("/logout")
def logout(admin=Depends(get_current_admin)):
    return {"data": {"status": "logged out"}}

@router.get("/me")
def me(admin=Depends(get_current_admin)):
    return {"data": {"username": admin["username"], "role": admin["role"]}}
