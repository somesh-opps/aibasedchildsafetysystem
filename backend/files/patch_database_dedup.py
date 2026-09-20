import os
with open("backend/database.py", "r") as f:
    content = f.read()

# Patch record_checkin
find_checkin = """    now = timestamp or datetime.now()
"""
insert_checkin = """
    # Prevent duplicate check-in today
    start_of_day = datetime(now.year, now.month, now.day)
    existing = mongo.attendance.find_one({
        "student_id": resolved_id,
        "event_type": "check-in",
        "timestamp": {"$gte": start_of_day}
    })
    if existing:
        print(f"[MONGODB] Duplicate check-in prevented for {resolved_id}")
        return
"""

# Patch record_checkout
find_checkout = """    now = timestamp or datetime.now()
"""
insert_checkout = """
    # Prevent duplicate check-out today
    start_of_day = datetime(now.year, now.month, now.day)
    existing = mongo.attendance.find_one({
        "student_id": resolved_id,
        "event_type": "check-out",
        "timestamp": {"$gte": start_of_day}
    })
    if existing:
        print(f"[MONGODB] Duplicate check-out prevented for {resolved_id}")
        return
"""

if "Duplicate check-in prevented" not in content:
    content = content.replace(
        "def record_checkin(student_id=None, student_name=None, timestamp=None, verification=None, method=\"Face Recognition\", phone=None):\n" + find_checkin,
        "def record_checkin(student_id=None, student_name=None, timestamp=None, verification=None, method=\"Face Recognition\", phone=None):\n" + find_checkin + insert_checkin
    )

if "Duplicate check-out prevented" not in content:
    content = content.replace(
        "def record_checkout(student_id=None, student_name=None, timestamp=None, verification=None, method=\"Face Recognition\", guardian_name=None):\n" + find_checkout,
        "def record_checkout(student_id=None, student_name=None, timestamp=None, verification=None, method=\"Face Recognition\", guardian_name=None):\n" + find_checkout + insert_checkout
    )

with open("backend/database.py", "w") as f:
    f.write(content)
print("Added duplicate prevention to database.py")
