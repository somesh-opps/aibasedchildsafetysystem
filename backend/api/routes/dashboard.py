from fastapi import APIRouter, Depends
from backend.database import mongo
from datetime import datetime
from backend.api.dependencies import get_current_admin

router = APIRouter()

@router.get("/summary")
def get_summary(admin=Depends(get_current_admin)):
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    
    total_students = mongo.students.count_documents({"status": "active"})
    checkins_today = mongo.attendance.count_documents({"event_type": "check-in", "timestamp": {"$gte": today_start}})
    checkouts_today = mongo.attendance.count_documents({"event_type": "check-out", "timestamp": {"$gte": today_start}})
    
    present_today = len(mongo.attendance.distinct("student_id", {"event_type": "check-in", "timestamp": {"$gte": today_start}}))
    currently_present = max(0, present_today - len(mongo.attendance.distinct("student_id", {"event_type": "check-out", "timestamp": {"$gte": today_start}})))
    
    failed_verifications = mongo.system_events.count_documents({"event_type": "GUARDIAN_VERIFICATION_FAILED", "timestamp": {"$gte": today_start}})

    return {
        "data": {
            "total_students": total_students,
            "present_today": present_today,
            "currently_present": currently_present,
            "checkins_today": checkins_today,
            "checkouts_today": checkouts_today,
            "failed_verifications": failed_verifications
        }
    }

@router.get("/recent-attendance")
def get_recent_attendance(admin=Depends(get_current_admin)):
    docs = list(mongo.attendance.find({}, {"_id": 0}).sort("timestamp", -1).limit(10))
    return {"records": docs}
