from fastapi import APIRouter, HTTPException, Depends
from backend.api.services.hardware_service import hardware_manager
from backend.database import mongo, record_checkin, record_checkout
from backend.api.dependencies import get_current_admin
from datetime import datetime
import asyncio
from backend.api.routes.events import manager

router = APIRouter()

@router.get("/status")
def get_status():
    db_status = "connected" if mongo.test_connection() else "disconnected"
    hw_status = "connected" if hardware_manager.is_connected else "disconnected"
    return {
        "backend": "online",
        "database": db_status,
        "camera": "ready",
        "hardware": hw_status,
        "api": "live",
        "checkin": hardware_manager.current_mode == "CHECKIN",
        "checkout": hardware_manager.current_mode == "CHECKOUT"
    }

@router.post("/checkin/start")
def start_checkin(admin=Depends(get_current_admin)):
    hardware_manager.start_mode("CHECKIN")
    _log_event("CHECKIN_MODE_STARTED", "Admin started check-in mode")
    return get_status()

@router.post("/checkin/stop")
def stop_checkin(admin=Depends(get_current_admin)):
    hardware_manager.stop_mode()
    _log_event("CHECKIN_MODE_STOPPED", "Admin stopped check-in mode")
    return get_status()

@router.post("/checkout/start")
def start_checkout(admin=Depends(get_current_admin)):
    hardware_manager.start_mode("CHECKOUT")
    _log_event("CHECKOUT_MODE_STARTED", "Admin started check-out mode")
    return get_status()

@router.post("/checkout/stop")
def stop_checkout(admin=Depends(get_current_admin)):
    hardware_manager.stop_mode()
    _log_event("CHECKOUT_MODE_STOPPED", "Admin stopped check-out mode")
    return get_status()

def _log_event(event_type, details, level="info"):
    event = {
        "event_type": event_type,
        "details": details,
        "level": level,
        "timestamp": datetime.utcnow()
    }
    mongo.system_events.insert_one(event)
    # Broadcast event as well
    event["id"] = str(event.pop("_id"))
    event["timestamp"] = event["timestamp"].isoformat()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast({"event": "system_event", "data": event}), loop)
    except:
        pass

@router.post("/mock/rfid/{card_id}")
def mock_rfid(card_id: str, admin=Depends(get_current_admin)):
    hardware_manager.mock_scan(card_id)
    return {"status": "ok", "card_id": card_id}

@router.post("/mock/face/{student_id}")
def mock_face(student_id: str, admin=Depends(get_current_admin)):
    student = mongo.students.find_one({"student_id": student_id})
    if not student:
        _log_event("FACE_NOT_RECOGNIZED", f"Unknown face detected for {student_id}", "warning")
        raise HTTPException(status_code=404, detail="Student not found")
        
    _log_event("FACE_RECOGNIZED", f"Face recognized: {student['name']}")
    
    if hardware_manager.current_mode == "CHECKIN":
        record_checkin(student_id=student["student_id"], student_name=student["name"], method="Software Mock")
        _log_event("CHECKIN_SUCCESS", f"{student['name']} checked in successfully")
    elif hardware_manager.current_mode == "CHECKOUT":
        # Waiting for guardian verification (can just emit an event indicating we need guardian)
        _broadcast_event("attendance", {"event_type": "AWAITING_GUARDIAN", "student_id": student["student_id"], "student_name": student["name"]})
    else:
        return {"status": "ignored", "reason": "No active mode"}
        
    return {"status": "ok", "student_id": student_id}

@router.post("/mock/guardian/{student_id}")
def mock_guardian_verification(student_id: str, success: bool, admin=Depends(get_current_admin)):
    student = mongo.students.find_one({"student_id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    if hardware_manager.current_mode != "CHECKOUT":
        raise HTTPException(status_code=400, detail="Must be in checkout mode")
        
    if success:
        _log_event("GUARDIAN_VERIFIED", f"Guardian verified for {student['name']}")
        record_checkout(student_id=student["student_id"], student_name=student["name"], method="Software Mock", guardian_name="Mock Guardian")
        _log_event("CHECKOUT_SUCCESS", f"{student['name']} checked out successfully")
    else:
        _log_event("GUARDIAN_VERIFICATION_FAILED", f"Guardian verification failed for {student['name']}", "warning")
        
    return {"status": "ok", "success": success}

def _broadcast_event(event_type, payload):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast({"event": event_type, "data": payload}), loop)
    except:
        pass
