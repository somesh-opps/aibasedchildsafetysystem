import os
import glob
import time
from datetime import datetime
from pathlib import Path
import threading


import os
import cv2 as _cv2
_headless = os.environ.get("DISPLAY") is None and os.name != 'nt'

class SafeCV2:
    def __getattr__(self, name):
        if name == 'imshow' and _headless:
            return lambda *args, **kwargs: None
        if name == 'waitKey' and _headless:
            return lambda *args, **kwargs: 1
        return getattr(_cv2, name)

cv2 = SafeCV2()
import face_recognition
import numpy as np

# Load configuration from config_template.py
try:
    from backend.config_template import (
        STUDENTS_DIR,
        OUTPUT_FILE,
        CAM_INDEX,
        DETECTION_MODEL,
        TOLERANCE,
        FRAME_SCALE,
        PROCESS_EVERY_N,
        WHATSAPP_WAIT_TIME,
        ENTER_DELAY_SEC,
        WHATSAPP_TAB_CLOSE_DELAY,
        CHECKIN_MESSAGE_TEMPLATE as MESSAGE_TEMPLATE
    )
except ImportError as e:
    print(f"[ERROR] Failed to import configuration in checkin.py: {e}")
    print("Please ensure config_template.py exists and .env is configured properly.")
    raise

# Import MongoDB record_checkin function from database.py
try:
    from backend.database import record_checkin
except ImportError as e:
    print(f"[ERROR] Failed to import database module in checkin.py: {e}")
    raise

_last_whatsapp_sent_time = {}

# ==========================
# Load students (encodings + phone numbers)
# ==========================
def load_students(students_dir: str):
    encodings = []
    names = []
    phones = {}

    if not os.path.isdir(students_dir):
        print(f"[ERR] STUDENTS_DIR not found: {students_dir}")
        return [], [], {}

    for student in os.listdir(students_dir):
        student_path = os.path.join(students_dir, student)
        if not os.path.isdir(student_path):
            continue

        phone_file = os.path.join(student_path, "phone.txt")
        phone_number = None
        if os.path.exists(phone_file):
            try:
                with open(phone_file, "r", encoding="utf-8") as f:
                    phone_number = f.read().strip()
                    if phone_number:
                        phones[student] = phone_number
            except Exception as e:
                print(f"[WARN] {student}: failed to read phone.txt ({e})")

        exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
        any_image = False
        for ext in exts:
            for img_path in glob.glob(os.path.join(student_path, ext)):
                any_image = True
                try:
                    image = face_recognition.load_image_file(img_path)
                    boxes = face_recognition.face_locations(image, model=DETECTION_MODEL)
                    if len(boxes) == 0:
                        print(f"[WARN] {student}: no face in {img_path}, skipped.")
                        continue
                    encoding = face_recognition.face_encodings(image, known_face_locations=boxes)[0]
                    encodings.append(encoding)
                    names.append(student)
                except Exception as e:
                    print(f"[WARN] {student}: failed to process {img_path} ({e})")
        if not any_image:
            print(f"[WARN] {student}: no images found")

    print(f"[INFO] Total encodings: {len(encodings)}; distinct students: {len(set(names))}")
    return encodings, names, phones

# =================================================================
# send_whatsapp_message
# =================================================================
def send_whatsapp_message(phone_number: str, message: str, name: str):
    current_time = time.time()
    last_sent = _last_whatsapp_sent_time.get(name, 0)
    if current_time - last_sent < 600:
        print(f"[INFO] Skipping WhatsApp for {name} - within cooldown period.")
        return

    try:
        import pywhatkit as kit
        import pyautogui
    except Exception as e:
        print(f"[WARN] WhatsApp automation disabled (GUI not available): {e}")
        kit = None

    if not phone_number or not phone_number.strip():
        print("[WARN] No phone number provided; skipping WhatsApp send.")
        return
    if not message or not message.strip():
        print("[WARN] Empty message; skipping WhatsApp send.")
        return

    print(f"[INFO] Opening WhatsApp Web to message {phone_number} ...")
    try:
        # Set tab_close=False as we will handle it manually
        if kit:
            kit.sendwhatmsg_instantly(phone_number, message, wait_time=WHATSAPP_WAIT_TIME, tab_close=False)
        time.sleep(ENTER_DELAY_SEC)
        if kit:
            pyautogui.FAILSAFE = True
        if kit:
            pyautogui.press("enter")
        print("[INFO] Message sent. Waiting to close tab...")

        # Wait for a few seconds before closing the tab
        time.sleep(WHATSAPP_TAB_CLOSE_DELAY)
        if kit:
            pyautogui.hotkey('ctrl', 'w')
        print("[INFO] WhatsApp tab closed.")

        _last_whatsapp_sent_time[name] = current_time
    except Exception as e:
        print(f"[WARN] Could not send WhatsApp message automatically: {e}. Check if WhatsApp Web loaded correctly or if browser focus was lost.")

# ==========================
# Main Check-in Function
# ==========================
def run_checkin_mode(stop_event: threading.Event, send_to_lcd_func):
    known_encodings, known_names, phone_numbers = load_students(STUDENTS_DIR)
    if len(known_encodings) == 0:
        print("[ERR] No encodings loaded for check-in. Add student images and try again.")
        send_to_lcd_func("ERR: No students loaded.")
        return

    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[ERR] Could not open camera index {CAM_INDEX} for check-in mode.")
        send_to_lcd_func("ERR: Camera not found.")
        return

    print("[INFO] Check-in mode started. Camera opened. Stabilizing (2s)...")
    send_to_lcd_func("Checkin Activated.")
    time.sleep(2)

    frame_count = 0
    checked_in_students = []
    print("[INFO] Starting check-in recognition... (scan multiple students, RFID again to stop)")
    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                print("[ERR] Failed to read frame in check-in mode.")
                send_to_lcd_func("Camera Read Err!")
                break

            frame_count += 1

            if frame_count % PROCESS_EVERY_N == 0:
                small = cv2.resize(frame, (0, 0), fx=FRAME_SCALE, fy=FRAME_SCALE)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_small, model=DETECTION_MODEL)
                face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

                detected_students_this_frame = set()  # To prevent duplicate processing in one frame

                for enc in face_encodings:
                    name = "Unknown"
                    if known_encodings:
                        distances = face_recognition.face_distance(known_encodings, enc)
                        if len(distances) > 0:
                            best_idx = int(np.argmin(distances))
                            best_dist = float(distances[best_idx])
                            if best_dist <= TOLERANCE:
                                name = known_names[best_idx]

                                if name in checked_in_students:
                                    print(f"[INFO] {name} already checked in. Waiting for another face...")
                                    time.sleep(2)
                                    continue  # Skip processing for this student

                                if name not in detected_students_this_frame:  # Process only once per frame
                                    detected_students_this_frame.add(name)
                                    checked_in_students.append(name)  # Add to array

                                    print(f"[MATCH] {name} (distance={best_dist:.3f}) - Processing check-in...")
                                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    phone = phone_numbers.get(name, "").strip()

                                    # Flow: Student recognized -> MongoDB Atlas -> WhatsApp -> Local log
                                    # 1. MongoDB Atlas check-in record
                                    record_checkin(
                                        student_name=name,
                                        timestamp=ts,
                                        verification={
                                            "student_face": True,
                                            "distance": round(best_dist, 4)
                                        },
                                        method="Face Recognition",
                                        phone=phone
                                    )

                                    # 2. LCD update
                                    send_to_lcd_func(f"C/I: {name}")

                                    # 3. WhatsApp notification
                                    msg = MESSAGE_TEMPLATE.format(name=name, ts=ts)
                                    time.sleep(2)
                                    send_whatsapp_message(phone, msg, name)

                                    # 4. Local attendance log
                                    log_line = f"{name} detected at {ts}"
                                    try:
                                        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                                            f.write(log_line + "\n")
                                        print(f"[LOG] {log_line} -> {OUTPUT_FILE}")
                                    except Exception as e:
                                        print(f"[WARN] Failed to write log ({e})")

                                    print(f"[INFO] Check-in processed for {name}.")
                                    time.sleep(2)  # Display message for a few seconds
                                    send_to_lcd_func("Check-in Active.")

            cv2.imshow("Check-in Mode (Press 'q' to quit this window)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Check-in mode finished.")