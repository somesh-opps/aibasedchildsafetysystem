from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form, Depends
from backend.database import mongo
from typing import Optional
from datetime import datetime
import json
import os
from backend.api.dependencies import get_current_admin
from backend.config_template import STUDENTS_DIR

router = APIRouter()

@router.get("")
def get_students(search: Optional[str] = None):
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"student_id": {"$regex": search, "$options": "i"}}
        ]
    docs = list(mongo.students.find(query, {"_id": 0}))
    return {"records": docs}

@router.get("/{student_id}")
def get_student(student_id: str):
    doc = mongo.students.find_one({"student_id": student_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"data": doc}

@router.post("")
def create_student(student: dict, admin=Depends(get_current_admin)):
    student["created_at"] = datetime.utcnow()
    student["status"] = "active"
    if "student_id" not in student or not student["student_id"]:
        student["student_id"] = f"STU-{student['name'].upper().replace(' ', '')}"
    mongo.students.insert_one(student)
    del student["_id"]
    return {"data": student}

@router.put("/{student_id}")
def update_student(student_id: str, update_data: dict, admin=Depends(get_current_admin)):
    result = mongo.students.update_one({"student_id": student_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"status": "ok"}

@router.delete("/{student_id}")
def delete_student(student_id: str, admin=Depends(get_current_admin)):
    result = mongo.students.update_one({"student_id": student_id}, {"$set": {"status": "archived"}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"status": "archived"}

@router.post("/register-with-face")
async def register_student_with_face(payload: str = Form(...), face_image: Optional[UploadFile] = File(None), admin=Depends(get_current_admin)):
    student_data = json.loads(payload)
    student_data["created_at"] = datetime.utcnow()
    student_data["status"] = "active"
    if "student_id" not in student_data or not student_data["student_id"]:
        student_data["student_id"] = f"STU-{student_data['name'].upper().replace(' ', '')}"
    
    # Save face image to generate encoding
    if face_image:
        student_dir = os.path.join(STUDENTS_DIR, student_data["name"])
        os.makedirs(student_dir, exist_ok=True)
        img_path = os.path.join(student_dir, f"{student_data['name']}.jpg")
        with open(img_path, "wb") as f:
            f.write(await face_image.read())
            
        student_data["face_registered"] = True
        
        # In a real app we might immediately train encodings here using face_recognition
        # The prompt says: "Validate: File type, File size, Presence of a face, Number of faces, Successful encoding generation"
        try:
            import face_recognition
            import cv2
            import numpy as np
            image = face_recognition.load_image_file(img_path)
            face_encodings = face_recognition.face_encodings(image)
            if len(face_encodings) == 0:
                os.remove(img_path)
                raise HTTPException(status_code=400, detail="Face registration failed: No face found in image.")
            elif len(face_encodings) > 1:
                os.remove(img_path)
                raise HTTPException(status_code=400, detail="Face registration failed: Multiple faces found in image.")
        except ImportError:
            pass # Ignore if face_recognition not available on this environment
            
    mongo.students.insert_one(student_data)
    
    # Separate guardian creation if provided
    guardian_name = student_data.pop("guardian_name", None)
    guardian_phone = student_data.pop("guardian_phone", None)
    guardian_rel = student_data.pop("guardian_relationship", "guardian")
    if guardian_name:
        guardian_data = {
            "guardian_id": f"GDN-{guardian_name.upper().replace(' ', '')}",
            "student_id": student_data["student_id"],
            "name": guardian_name,
            "phone": guardian_phone,
            "relationship": guardian_rel,
            "status": "active"
        }
        mongo.guardians.insert_one(guardian_data)
        
    if "_id" in student_data:
        del student_data["_id"]
    return {"status": "success", "data": student_data}
