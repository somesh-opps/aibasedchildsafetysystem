from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth, students, attendance, dashboard, system, events, hardware, guardians, events_history
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
app.include_router(guardians.router, prefix="/api/guardians", tags=["Guardians"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(hardware.router, prefix="/api/hardware", tags=["Hardware"])
app.include_router(events.router, prefix="/ws", tags=["Events"])
app.include_router(events_history.router, prefix="/api/events", tags=["System Events"])

@app.get("/health", tags=["System"])
async def health_check():
    from backend.database import mongo
    db_status = "connected" if mongo.test_connection() else "disconnected"
    return {"status": "ok", "database": db_status}
