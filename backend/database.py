import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "childdatadb")


class MongoDB:
    def __init__(self, uri: str = None, database_name: str = None):
        self.uri = uri or MONGODB_URI
        self.database_name = database_name or MONGODB_DATABASE
        self._client = None
        self._db = None

        if self.uri:
            self._connect()
        else:
            print("[MONGODB WARN] MONGODB_URI is not set in environment or .env file.")

    def _connect(self):
        """Initializes the MongoDB client without exposing sensitive URI credentials."""
        try:
            self._client = MongoClient(
                self.uri,
                server_api=ServerApi(
                    "1",
                    strict=True,
                    deprecation_errors=True
                )
            )
            self._db = self._client[self.database_name]
        except Exception:
            print("[MONGODB ERROR] Unable to initialize MongoDB Atlas client.")
            self._client = None
            self._db = None

    @property
    def client(self):
        if self._client is None and self.uri:
            self._connect()
        return self._client

    @property
    def db(self):
        if self._db is None and self.uri:
            self._connect()
        return self._db

    def test_connection(self) -> bool:
        """Pings MongoDB Atlas to verify active connection."""
        if not self.uri:
            print("[MONGODB ERROR] MONGODB_URI is not configured in .env")
            return False
        try:
            if self.client is None:
                print("[MONGODB ERROR] MongoDB client is not initialized.")
                return False
            self.client.admin.command("ping")
            return True
        except PyMongoError:
            print("[MONGODB ERROR] Unable to connect to MongoDB Atlas.")
            return False
        except Exception:
            print("[MONGODB ERROR] Unexpected error while pinging MongoDB Atlas.")
            return False

    @property
    def students(self):
        if self.db is None:
            return None
        return self.db["students"]

    @property
    def guardians(self):
        if self.db is None:
            return None
        return self.db["guardians"]

    @property
    def attendance(self):
        if self.db is None:
            return None
        return self.db["attendance"]

    @property
    def system_events(self):
        if self.db is None:
            return None
        return self.db["system_events"]


# Global MongoDB singleton instance
mongo = MongoDB()



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

def record_checkin(
    student_id: str = None,
    student_name: str = None,
    timestamp = None,
    verification: dict = None,
    method: str = "Face Recognition",
    phone: str = None
) -> bool:
    """
    Records a student check-in event into the MongoDB 'attendance' collection.
    Also ensures the student document exists in 'students'.
    """
    if mongo.attendance is None:
        print("[MONGODB ERROR] Attendance collection unavailable. Checkin not recorded in cloud.")
        return False

    now = datetime.utcnow() if timestamp is None else (
        timestamp if isinstance(timestamp, datetime) else datetime.strptime(str(timestamp), "%Y-%m-%d %H:%M:%S")
    )
    date_str = now.strftime("%Y-%m-%d")

    resolved_id = student_id
    if not resolved_id:
        try:
            existing = mongo.students.find_one({"name": student_name})
            if existing and "student_id" in existing:
                resolved_id = existing["student_id"]
            else:
                resolved_id = f"STU-{student_name.upper()}"
        except Exception:
            resolved_id = f"STU-{student_name.upper()}"

    doc = {
        "student_id": resolved_id,
        "student_name": student_name,
        "event_type": "check-in",
        "timestamp": now,
        "date": date_str,
        "method": method,
        "verification": verification or {"student_face": True}
    }

    try:
        mongo.attendance.insert_one(doc)
        _broadcast_attendance(doc)
        print(f"[MONGODB] Recorded check-in for {student_name} ({resolved_id}) at {now.strftime('%H:%M:%S')}")

        # Upsert student profile in students collection
        if mongo.students is not None:
            update_data = {
                "name": student_name,
                "status": "active",
                "updated_at": now
            }
            if phone:
                update_data["phone"] = phone
            mongo.students.update_one(
                {"student_id": resolved_id},
                {
                    "$set": update_data,
                    "$setOnInsert": {
                        "student_id": resolved_id,
                        "rfid_id": None,
                        "created_at": now
                    }
                },
                upsert=True
            )
        return True
    except PyMongoError:
        print(f"[MONGODB ERROR] Failed to record check-in for {student_name} in MongoDB Atlas.")
        return False
    except Exception as e:
        print(f"[MONGODB ERROR] Unexpected exception during check-in: {type(e).__name__}")
        return False


def record_checkout(
    student_id: str = None,
    student_name: str = None,
    guardian_name: str = None,
    guardian_id: str = None,
    relationship: str = "authorized_guardian",
    timestamp = None,
    verification: dict = None,
    method: str = "Student Face + Guardian Face",
    phone: str = None
) -> bool:
    """
    Records a student check-out event with guardian details into the MongoDB 'attendance' collection.
    Also ensures the guardian document exists in 'guardians'.
    """
    if mongo.attendance is None:
        print("[MONGODB ERROR] Attendance collection unavailable. Checkout not recorded in cloud.")
        return False

    now = datetime.utcnow() if timestamp is None else (
        timestamp if isinstance(timestamp, datetime) else datetime.strptime(str(timestamp), "%Y-%m-%d %H:%M:%S")
    )
    date_str = now.strftime("%Y-%m-%d")

    resolved_student_id = student_id
    if not resolved_student_id:
        try:
            existing = mongo.students.find_one({"name": student_name})
            if existing and "student_id" in existing:
                resolved_student_id = existing["student_id"]
            else:
                resolved_student_id = f"STU-{student_name.upper()}"
        except Exception:
            resolved_student_id = f"STU-{student_name.upper()}"

    resolved_guardian_id = guardian_id or f"GDN-{guardian_name.upper()}"

    doc = {
        "student_id": resolved_student_id,
        "student_name": student_name,
        "event_type": "check-out",
        "timestamp": now,
        "date": date_str,
        "method": method,
        "guardian": {
            "guardian_id": resolved_guardian_id,
            "name": guardian_name,
            "relationship": relationship
        },
        "verification": verification or {
            "student_face": True,
            "guardian_face": True
        }
    }

    try:
        mongo.attendance.insert_one(doc)
        _broadcast_attendance(doc)
        print(f"[MONGODB] Recorded check-out for {student_name} with Guardian {guardian_name} at {now.strftime('%H:%M:%S')}")

        # Upsert guardian record in guardians collection
        if mongo.guardians is not None:
            g_update = {
                "name": guardian_name,
                "student_id": resolved_student_id,
                "relationship": relationship,
                "status": "authorized",
                "updated_at": now
            }
            if phone:
                g_update["phone"] = phone
            mongo.guardians.update_one(
                {"guardian_id": resolved_guardian_id, "student_id": resolved_student_id},
                {
                    "$set": g_update,
                    "$setOnInsert": {
                        "guardian_id": resolved_guardian_id,
                        "created_at": now
                    }
                },
                upsert=True
            )
        return True
    except PyMongoError:
        print(f"[MONGODB ERROR] Failed to record check-out for {student_name} in MongoDB Atlas.")
        return False
    except Exception as e:
        print(f"[MONGODB ERROR] Unexpected exception during check-out: {type(e).__name__}")
        return False


def log_system_event(event_type: str, details: dict = None, level: str = "INFO") -> bool:
    """
    Logs an internal system event (e.g. RFID scan, mode change, unauthorized attempt) into 'system_events'.
    """
    if mongo.system_events is None:
        return False

    event_doc = {
        "event_type": event_type,
        "details": details or {},
        "level": level,
        "timestamp": datetime.utcnow()
    }

    try:
        mongo.system_events.insert_one(event_doc)
        return True
    except Exception:
        print(f"[MONGODB ERROR] Failed to log system event '{event_type}'.")
        return False
