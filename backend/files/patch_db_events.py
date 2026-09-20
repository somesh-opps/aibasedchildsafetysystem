import os
import sys

db_file = "backend/database.py"
with open(db_file, "r") as f:
    content = f.read()

# Add an event hook
hook_code = """
import traceback

def _broadcast_attendance(doc):
    try:
        import asyncio
        from backend.api.routes.events import manager
        loop = asyncio.get_event_loop()
        if loop.is_running():
            payload = {
                "event": "attendance",
                "data": {
                    "id": str(doc.get("_id", "")),
                    "student_id": doc.get("student_id"),
                    "student_name": doc.get("student_name"),
                    "event_type": doc.get("event_type"),
                    "timestamp": doc.get("timestamp").isoformat() if hasattr(doc.get("timestamp"), "isoformat") else doc.get("timestamp"),
                    "method": doc.get("method"),
                    "status": "success",
                    "verification": doc.get("verification")
                }
            }
            asyncio.run_coroutine_threadsafe(manager.broadcast(payload), loop)
    except Exception as e:
        print(f"[WS HOOK ERROR] {e}")

"""

if "_broadcast_attendance" not in content:
    content = content.replace("def record_checkin(", hook_code + "def record_checkin(")
    content = content.replace(
        "mongo.attendance.insert_one(doc)",
        "mongo.attendance.insert_one(doc)\n        _broadcast_attendance(doc)"
    )

with open(db_file, "w") as f:
    f.write(content)
print("Database patched with WS hooks.")
