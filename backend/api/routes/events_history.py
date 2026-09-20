from fastapi import APIRouter, Depends, Query
from backend.database import mongo
from typing import Optional
from backend.api.dependencies import get_current_admin

router = APIRouter()

@router.get("")
def get_events(event_type: Optional[str] = None, level: Optional[str] = None, limit: int = 50, admin=Depends(get_current_admin)):
    query = {}
    if event_type:
        query["event_type"] = event_type
    if level:
        query["level"] = level
        
    docs = list(mongo.system_events.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit))
    return {"records": docs}
