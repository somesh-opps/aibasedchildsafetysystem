import os
import glob
import time
from datetime import datetime
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
        CHECKOUT_MESSAGE_TEMPLATE as MESSAGE_TEMPLATE
    )
except ImportError as e:
    print(f"[ERROR] Failed to import configuration in checkout.py: {e}")
    print("Please ensure config_template.py exists and .env is configured properly.")
    raise

# Import MongoDB record_checkout function from database.py
try:
    from backend.database import record_checkout
except ImportError as e:
    print(f"[ERROR] Failed to import database module in checkout.py: {e}")
    raise

_checked_out_pairs_session = set()
_last_whatsapp_sent_time_checkout = {}

# ==========================
# Load encodings
# ==========================
def load_students_and_guardians(students_dir: str):
    student_encodings = []
    student_names = []
    phone_numbers = {}
    guardians_encodings = {}

    if not os.path.isdir(students_dir):
        print(f"[ERR] STUDENTS_DIR not found: {students_dir}")
        return [], [], {}, {}

    for student in os.listdir(students_dir):
        student_path = os.path.join(students_dir, student)
        if not os.path.isdir(student_path):
            continue

        phone_file = os.path.join(student_path, "phone.txt")
        if os.path.exists(phone_file):
            try:
                with open(phone_file, "r", encoding="utf-8") as f:
                    phone = f.read().strip()
                    if phone:
                        phone_numbers[student] = phone
            except Exception as e:
                print(f"[WARN] Failed to read phone.txt for {student}: {e}")

        exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp")
        student_images_found = False
        for ext in exts:
            for img_path in glob.glob(os.path.join(student_path, ext)):
                if "guardian" in img_path.lower():
                    continue
                student_images_found = True
                try:
                    img = face_recognition.load_image_file(img_path)
                    boxes = face_recognition.face_locations(img, model=DETECTION_MODEL)
                    if boxes:
                        encoding = face_recognition.face_encodings(img, boxes)[0]
                        student_encodings.append(encoding)
                        student_names.append(student)
                except Exception as e:
                    print(f"[WARN] Failed to load student image {img_path} for {student}: {e}")
        if not student_images_found:
            print(f"[WARN] No student images found for {student}.")

        guardian_dir = os.path.join(student_path, "guardian")
        if os.path.isdir(guardian_dir):
            guardians_encodings[student] = []
            guardian_images_found = False
            for ext in exts:
                for img_path in glob.glob(os.path.join(guardian_dir, ext)):
                    guardian_images_found = True
                    guardian_name = os.path.splitext(os.path.basename(img_path))[0]
                    try:
                        img = face_recognition.load_image_file(img_path)
                        boxes = face_recognition.face_locations(img, model=DETECTION_MODEL)
                        if boxes:
                            encoding = face_recognition.face_encodings(img, boxes)[0]
                            guardians_encodings[student].append((encoding, guardian_name))
                    except Exception as e:
                        print(f"[WARN] Failed to load guardian image {img_path} for {guardian_name} of {student}: {e}")
            if not guardian_images_found:
                print(f"[WARN] No guardian images found for {student}.")

    print(f"[INFO] Loaded {len(student_encodings)} student encodings and {len(guardians_encodings)} student-guardian sets.")
    return student_encodings, student_names, phone_numbers, guardians_encodings

# =================================================================
# send_whatsapp_message_checkout
# =================================================================
def send_whatsapp_message_checkout(phone_number: str, message: str, student_name: str):
    current_time = time.time()
    last_sent = _last_whatsapp_sent_time_checkout.get(student_name, 0)
    if current_time - last_sent < 600:
        print(f"[INFO] Skipping WhatsApp checkout message for {student_name} - within cooldown period.")
        return

    try:
        import pywhatkit as kit
        import pyautogui
    except Exception as e:
        print(f"[WARN] WhatsApp automation disabled (GUI not available): {e}")
        kit = None

    if not phone_number:
        print("[WARN] No phone number; skipping send for checkout.")
        return
    if not message.strip():
        print("[WARN] Empty message; skipping send for checkout.")
        return

    print(f"[INFO] Opening WhatsApp Web to message {phone_number} for {student_name}...")
    try:
        # Set tab_close=False as we will handle it manually
        if kit:
            kit.sendwhatmsg_instantly(phone_number, message, wait_time=WHATSAPP_WAIT_TIME, tab_close=False)
        time.sleep(ENTER_DELAY_SEC)
        if kit:
            pyautogui.FAILSAFE = True
        if kit:
            pyautogui.press("enter")
        print("[INFO] Checkout message sent. Waiting to close tab...")

        # Wait for a few seconds before closing the tab
        time.sleep(WHATSAPP_TAB_CLOSE_DELAY)
        if kit:
            pyautogui.hotkey('ctrl', 'w')
        print("[INFO] WhatsApp tab closed.")

        _last_whatsapp_sent_time_checkout[student_name] = current_time
    except Exception as e:
        print(f"[WARN] Could not send WhatsApp checkout message automatically for {student_name}: {e}. Please check WhatsApp Web.")

# ==========================
# Recognition helper
# ==========================
def recognize_first_face(frame, known_encodings, known_names, model=DETECTION_MODEL, tolerance=TOLERANCE, frame_scale=FRAME_SCALE):
    small = cv2.resize(frame, (0, 0), fx=frame_scale, fy=frame_scale)
    rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb_small, model=model)
    encs = face_recognition.face_encodings(rgb_small, boxes)

    if not encs:
        return None

    for enc in encs:
        distances = face_recognition.face_distance(known_encodings, enc)
        if len(distances) > 0:
            best_idx = np.argmin(distances)
            if distances[best_idx] <= tolerance:
                return known_names[best_idx]
    return None

# ==========================
# Main Checkout Function
# ==========================
def run_checkout_mode(stop_event: threading.Event, send_to_lcd_func):
    global _checked_out_pairs_session
    _checked_out_pairs_session.clear()

    student_encodings, student_names, phone_numbers, guardians_encodings = load_students_and_guardians(STUDENTS_DIR)

    if len(student_encodings) == 0:
        print("[ERR] No student encodings loaded for checkout. Add student images and try again.")
        send_to_lcd_func("ERR: No students loaded")
        return

    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[ERR] Could not open camera index {CAM_INDEX} for checkout mode.")
        send_to_lcd_func("ERR: Camera not found.")
        return

    print("[INFO] Checkout mode started. Camera opened. Stabilizing (2s)...")
    send_to_lcd_func("Checkout Activated")
    time.sleep(2)

    print("[INFO] Starting sequential checkout process. Scan student first, then guardian. RFID again to stop.")

    checked_out_students = []
    try:
        while not stop_event.is_set():
            student_name = None
            student_frame_count = 0
            print("\n[CHECKOUT] Waiting for student scan...")
            send_to_lcd_func("Scaning Student")
            while not student_name and not stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    print("[ERR] Failed to read frame for student scan.")
                    send_to_lcd_func("Camera Read Err!")
                    break
                student_frame_count += 1
                if student_frame_count % PROCESS_EVERY_N == 0:
                    candidate_name = recognize_first_face(frame, student_encodings, student_names)
                    if candidate_name:
                        if candidate_name in checked_out_students:
                            print(f"[INFO] {candidate_name} already checked out. Waiting for another face...")
                            time.sleep(2)
                            continue  # Skip processing for this student
                        else:
                            student_name = candidate_name
                            checked_out_students.append(candidate_name)
                cv2.imshow("Checkout: Scan Student", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    stop_event.set()
                    break

            if stop_event.is_set() or not student_name:
                if not student_name and not stop_event.is_set():
                    print("[WARN] No student recognized or camera issue. Restarting scan loop.")
                    send_to_lcd_func("No student found\nRetrying...")
                    time.sleep(2)  # Display message
                continue

            print(f"[CHECKOUT] Student recognized: {student_name}. Waiting 5 seconds before guardian scan...")
            send_to_lcd_func(f"Scan Guardian for{student_name}")
            time.sleep(5)  # Give user time to see recognized student and prepare guardian

            guardian_name = None
            guardian_frame_count = 0
            guardian_data = guardians_encodings.get(student_name, [])
            guardian_encs = [enc for enc, name in guardian_data] if guardian_data else []
            guardian_names = [name for enc, name in guardian_data] if guardian_data else []

            if not guardian_encs:
                print(f"[WARN] No guardians registered for {student_name}. Skipping checkout for this student.")
                send_to_lcd_func(f"No Guardian found. Retry.")
                time.sleep(3)  # Display warning
                continue

            print(f"[CHECKOUT] Now show authorized guardian for {student_name}...")
            while not guardian_name and not stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    print("[ERR] Failed to read frame for guardian scan.")
                    send_to_lcd_func("Camera Read Err!")
                    break
                guardian_frame_count += 1
                if guardian_frame_count % PROCESS_EVERY_N == 0:
                    guardian_name = recognize_first_face(frame, guardian_encs, guardian_names)
                cv2.imshow(f"Checkout: Scan Guardian for {student_name}", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    stop_event.set()
                    break

            if stop_event.is_set():
                continue

            if not guardian_name:
                print(f"[WARN] No authorized guardian recognized for {student_name}. Resetting checkout process.")
                send_to_lcd_func("Guardian Not Rec. Retrying...")
                time.sleep(3)  # Display warning
                continue

            print(f"[CHECKOUT] Guardian recognized: {guardian_name}")
            send_to_lcd_func(f"Guardian: {guardian_name}")
            time.sleep(2)  # Briefly show guardian recognized message

            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pair = (student_name, guardian_name)
            phone = phone_numbers.get(student_name, "")

            if pair not in _checked_out_pairs_session:
                # Flow: Student verified -> Guardian verified -> MongoDB checkout -> WhatsApp -> Local log
                # 1. MongoDB Atlas checkout record
                record_checkout(
                    student_name=student_name,
                    guardian_name=guardian_name,
                    timestamp=current_timestamp,
                    verification={
                        "student_face": True,
                        "guardian_face": True
                    },
                    method="Student Face + Guardian Face",
                    phone=phone
                )

                # 2. LCD update
                send_to_lcd_func(f"C/O:{student_name}")

                # 3. WhatsApp notification
                msg = MESSAGE_TEMPLATE.format(student=student_name, guardian=guardian_name, ts=current_timestamp)
                time.sleep(2)
                send_whatsapp_message_checkout(phone, msg, student_name)

                # 4. Local attendance log
                log_line = f"{current_timestamp} - Student: {student_name}\n{current_timestamp} - Guardian: {guardian_name}"
                try:
                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        f.write(log_line + "\n")
                    print(f"[LOG] Checkout event saved: {log_line}")
                except Exception as e:
                    print(f"[WARN] Failed to write checkout log ({e})")

                _checked_out_pairs_session.add(pair)
                print(f"[INFO] Checkout successful for {student_name} with {guardian_name}.")

            else:
                print(f"[INFO] Duplicate checkout detected for {pair}. Skipping notification.")
                send_to_lcd_func(f"Already C/O:{student_name}")

            time.sleep(3)  # Display checkout confirmation message
            send_to_lcd_func("Checkout Active")  # Back to prompt for next student

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Checkout mode finished.")