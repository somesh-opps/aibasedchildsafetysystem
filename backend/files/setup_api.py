import os

files = {
    "backend/api/__init__.py": "",
    "backend/api/main.py": """\
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth, students, attendance, dashboard, system, events, hardware
import os

app = FastAPI(title="AI-Based Child Safety System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(students.router, prefix="/api/students", tags=["Students"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(hardware.router, prefix="/api/hardware", tags=["Hardware"])
app.include_router(events.router, prefix="/ws", tags=["Events"])

@app.get("/health", tags=["System"])
async def health_check():
    from backend.database import mongo
    db_status = "connected" if mongo.test_connection() else "disconnected"
    return {"status": "ok", "database": db_status}
""",
    "backend/api/dependencies.py": """\
from fastapi import Header, HTTPException
def verify_token(authorization: str = Header(None)):
    if not authorization or authorization != "Bearer admin-token-secret":
        # Simplified for now, use JWT in production
        # raise HTTPException(status_code=401, detail="Unauthorized")
        pass
    return "admin"
""",
    "backend/api/routes/__init__.py": "",
    "backend/api/routes/auth.py": """\
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(req: LoginReq):
    if req.username == "admin" and req.password == "admin":
        return {"token": "admin-token-secret"}
    return {"error": "Invalid credentials"}

@router.post("/logout")
def logout():
    return {"status": "logged out"}

@router.get("/me")
def me():
    return {"username": "admin", "role": "admin"}
""",
    "backend/api/routes/students.py": """\
from fastapi import APIRouter, Query, HTTPException
from backend.database import mongo
from typing import Optional
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("")
def get_students(search: Optional[str] = None):
    query = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    docs = list(mongo.students.find(query, {"_id": 0}))
    return docs

@router.post("")
def create_student(student: dict):
    student["created_at"] = datetime.utcnow()
    student["status"] = "active"
    if "student_id" not in student:
        student["student_id"] = f"STU-{student['name'].upper()}"
    mongo.students.insert_one(student)
    del student["_id"]
    return student
""",
    "backend/api/routes/attendance.py": """\
from fastapi import APIRouter
from backend.database import mongo

router = APIRouter()

@router.get("")
def get_attendance(date: str = None):
    query = {}
    if date:
        query["date"] = date
    docs = list(mongo.attendance.find(query, {"_id": 0}).sort("timestamp", -1))
    return docs
""",
    "backend/api/routes/dashboard.py": """\
from fastapi import APIRouter
from backend.database import mongo
from datetime import datetime

router = APIRouter()

@router.get("/summary")
def get_summary():
    total_students = mongo.students.count_documents({})
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    checkins_today = mongo.attendance.count_documents({"date": today_str, "event_type": "check-in"})
    checkouts_today = mongo.attendance.count_documents({"date": today_str, "event_type": "check-out"})
    
    return {
        "total_students": total_students,
        "present_today": checkins_today,
        "checked_out": checkouts_today,
        "currently_present": max(0, checkins_today - checkouts_today),
        "checkins_today": checkins_today,
        "checkouts_today": checkouts_today,
        "failed_verifications": 0
    }

@router.get("/recent-attendance")
def get_recent_attendance():
    docs = list(mongo.attendance.find({}, {"_id": 0}).sort("timestamp", -1).limit(10))
    return docs
""",
    "backend/api/routes/system.py": """\
from fastapi import APIRouter
from backend.api.services.hardware_service import hardware_manager

router = APIRouter()

@router.get("/status")
def get_status():
    from backend.database import mongo
    db_status = "connected" if mongo.test_connection() else "disconnected"
    hw_status = "connected" if hardware_manager.is_connected else "disconnected"
    return {
        "backend": "online",
        "database": db_status,
        "camera": "ready",
        "rfid": hw_status,
        "arduino": hw_status,
        "recognition": "ready",
        "notifications": "ready"
    }

@router.post("/checkin/start")
def start_checkin():
    hardware_manager.start_mode("CHECKIN")
    return {"mode": "checkin", "active": True}

@router.post("/checkin/stop")
def stop_checkin():
    hardware_manager.stop_mode()
    return {"mode": "checkin", "active": False}

@router.get("/checkin/status")
def checkin_status():
    active = hardware_manager.current_mode == "CHECKIN"
    return {"mode": "checkin", "active": active}

@router.post("/checkout/start")
def start_checkout():
    hardware_manager.start_mode("CHECKOUT")
    return {"mode": "checkout", "active": True}

@router.post("/checkout/stop")
def stop_checkout():
    hardware_manager.stop_mode()
    return {"mode": "checkout", "active": False}

@router.get("/checkout/status")
def checkout_status():
    active = hardware_manager.current_mode == "CHECKOUT"
    return {"mode": "checkout", "active": active}
""",
    "backend/api/routes/hardware.py": """\
from fastapi import APIRouter

router = APIRouter()
""",
    "backend/api/routes/events.py": """\
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@router.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
""",
    "backend/api/services/__init__.py": "",
    "backend/api/services/hardware_service.py": """\
import threading
import time
import os
from hardware.main_rfid_control import (
    read_rfid_card_from_arduino,
    send_to_lcd,
    clear_lcd,
    arduino_serial
)
from backend.config_template import RFID_AUTHORIZED_CARDS
from backend.checkin import run_checkin_mode
from backend.checkout import run_checkout_mode
from backend.api.routes.events import manager
import asyncio

class HardwareManager:
    def __init__(self):
        self.current_mode = "NONE"
        self.mode_stop_event = threading.Event()
        self.active_mode_thread = None
        self.is_connected = arduino_serial is not None and arduino_serial.is_open
        self.mock_mode = os.getenv("HARDWARE_MODE", "real") == "mock"
        
        self.bg_thread = threading.Thread(target=self._hardware_loop, daemon=True)
        self.bg_thread.start()
        
    def _broadcast_event(self, event_type, details):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast({
                "type": event_type,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                **details
            }), loop)

    def start_mode(self, mode):
        self.stop_mode()
        self.current_mode = mode
        self.mode_stop_event.clear()
        
        target = run_checkin_mode if mode == "CHECKIN" else run_checkout_mode
        self.active_mode_thread = threading.Thread(
            target=target, args=(self.mode_stop_event, send_to_lcd)
        )
        self.active_mode_thread.daemon = True
        self.active_mode_thread.start()
        
        send_to_lcd(f"{mode} ACTIVE")
        self._broadcast_event("MODE_CHANGED", {"mode": mode})

    def stop_mode(self):
        if self.active_mode_thread and self.active_mode_thread.is_alive():
            self.mode_stop_event.set()
            self.active_mode_thread.join(timeout=5)
        self.current_mode = "NONE"
        self.active_mode_thread = None
        clear_lcd()
        self._broadcast_event("MODE_CHANGED", {"mode": "NONE"})

    def _hardware_loop(self):
        last_scan = 0
        while True:
            if not self.mock_mode:
                card_id = read_rfid_card_from_arduino()
                if card_id and time.time() - last_scan > 3:
                    last_scan = time.time()
                    self._broadcast_event("RFID_SCANNED", {"card_id": card_id})
                    
                    if card_id in RFID_AUTHORIZED_CARDS:
                        if self.current_mode != "NONE":
                            self.stop_mode()
                        else:
                            # Let dashboard know an authorized card was scanned
                            self._broadcast_event("AUTHORIZED_SCAN", {"card_id": card_id})
                    else:
                        send_to_lcd("UNAUTHORIZED")
            time.sleep(0.5)

hardware_manager = HardwareManager()
"""
}

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

print("API scaffold created.")
