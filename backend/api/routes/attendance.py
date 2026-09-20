from fastapi import APIRouter
from backend.database import mongo
from datetime import datetime

router = APIRouter()

@router.get("")
def get_attendance(date: str = None):
    query = {}
    if date:
        query["date"] = date
    docs = list(mongo.attendance.find(query, {"_id": 0}).sort("timestamp", -1))
    return {"records": docs}

@router.get("/today")
def get_attendance_today():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    docs = list(mongo.attendance.find({"date": today_str}, {"_id": 0}).sort("timestamp", -1))
    return {"records": docs}
