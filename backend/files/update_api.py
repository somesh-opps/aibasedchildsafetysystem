import os

files = {
    "backend/api/routes/students.py": """\
from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form
from backend.database import mongo
from typing import Optional
from datetime import datetime

router = APIRouter()

@router.get("")
def get_students(search: Optional[str] = None):
    query = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    docs = list(mongo.students.find(query, {"_id": 0}))
    return {"records": docs}

@router.post("")
def create_student(student: dict):
    student["created_at"] = datetime.utcnow()
    student["status"] = "active"
    if "student_id" not in student or not student["student_id"]:
        student["student_id"] = f"STU-{student['name'].upper()}"
    mongo.students.insert_one(student)
    del student["_id"]
    return student

import json

@router.post("/register-with-face")
async def register_student_with_face(payload: str = Form(...), face_image: Optional[UploadFile] = File(None)):
    student_data = json.loads(payload)
    student_data["created_at"] = datetime.utcnow()
    student_data["status"] = "active"
    if "student_id" not in student_data or not student_data["student_id"]:
        student_data["student_id"] = f"STU-{student_data['name'].upper()}"
    
    # Save the face image to STUDENTS_DIR if provided
    if face_image:
        from backend.config_template import STUDENTS_DIR
        student_dir = os.path.join(STUDENTS_DIR, student_data["name"])
        os.makedirs(student_dir, exist_ok=True)
        img_path = os.path.join(student_dir, f"{student_data['name']}.jpg")
        with open(img_path, "wb") as f:
            f.write(await face_image.read())
            
        # Optional: Save guardian info/phone if provided
        phone = student_data.get("guardian_phone")
        if phone:
            with open(os.path.join(student_dir, "phone.txt"), "w") as f:
                f.write(phone)
                
    mongo.students.insert_one(student_data)
    del student_data["_id"]
    return {"status": "success", "data": student_data}
""",
    "backend/api/routes/attendance.py": """\
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
""",
}

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

print("API routes updated for App.tsx compatibility.")
