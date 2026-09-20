from fastapi import APIRouter, HTTPException, Depends
from backend.database import mongo
from backend.api.dependencies import get_current_admin

router = APIRouter()

@router.get("/student/{student_id}")
def get_guardians_by_student(student_id: str):
    docs = list(mongo.guardians.find({"student_id": student_id, "status": "active"}, {"_id": 0}))
    return {"records": docs}

@router.post("")
def add_guardian(guardian: dict, admin=Depends(get_current_admin)):
    guardian["status"] = "active"
    if "guardian_id" not in guardian or not guardian["guardian_id"]:
        guardian["guardian_id"] = f"GDN-{guardian['name'].upper().replace(' ', '')}"
    mongo.guardians.insert_one(guardian)
    del guardian["_id"]
    return {"data": guardian}

@router.put("/{guardian_id}")
def update_guardian(guardian_id: str, update_data: dict, admin=Depends(get_current_admin)):
    result = mongo.guardians.update_one({"guardian_id": guardian_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Guardian not found")
    return {"status": "ok"}

@router.delete("/{guardian_id}")
def remove_guardian(guardian_id: str, admin=Depends(get_current_admin)):
    result = mongo.guardians.update_one({"guardian_id": guardian_id}, {"$set": {"status": "inactive"}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Guardian not found")
    return {"status": "ok"}
