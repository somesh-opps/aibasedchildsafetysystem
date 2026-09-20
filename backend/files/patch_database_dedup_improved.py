import os
with open("backend/database.py", "r") as f:
    content = f.read()

# First, remove the old patch if it exists (it was inserted in the previous step)
# Actually, I'll just rewrite the duplicate prevention logic dynamically.
old_checkin = """    # Prevent duplicate check-in today
    start_of_day = datetime(now.year, now.month, now.day)
    existing = mongo.attendance.find_one({
        "student_id": resolved_id,
        "event_type": "check-in",
        "timestamp": {"$gte": start_of_day}
    })
    if existing:
        print(f"[MONGODB] Duplicate check-in prevented for {resolved_id}")
        return"""

new_checkin = """    # Prevent duplicate check-in if already checked in
    start_of_day = datetime(now.year, now.month, now.day)
    last_record = mongo.attendance.find_one(
        {"student_id": resolved_id, "timestamp": {"$gte": start_of_day}},
        sort=[("timestamp", -1)]
    )
    if last_record and last_record["event_type"] == "check-in":
        print(f"[MONGODB] Duplicate check-in prevented for {resolved_id} (already inside)")
        return"""
content = content.replace(old_checkin, new_checkin)

old_checkout = """    # Prevent duplicate check-out today
    start_of_day = datetime(now.year, now.month, now.day)
    existing = mongo.attendance.find_one({
        "student_id": resolved_id,
        "event_type": "check-out",
        "timestamp": {"$gte": start_of_day}
    })
    if existing:
        print(f"[MONGODB] Duplicate check-out prevented for {resolved_id}")
        return"""

new_checkout = """    # Prevent duplicate check-out if already checked out or not checked in
    start_of_day = datetime(now.year, now.month, now.day)
    last_record = mongo.attendance.find_one(
        {"student_id": resolved_id, "timestamp": {"$gte": start_of_day}},
        sort=[("timestamp", -1)]
    )
    if not last_record or last_record["event_type"] == "check-out":
        print(f"[MONGODB] Duplicate check-out prevented for {resolved_id} (already outside or not inside)")
        return"""
content = content.replace(old_checkout, new_checkout)

with open("backend/database.py", "w") as f:
    f.write(content)
print("Updated database duplicate prevention")
