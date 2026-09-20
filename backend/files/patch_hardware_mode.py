import sys

with open("backend/api/services/hardware_service.py", "r") as f:
    content = f.read()

old_start = """        target = run_checkin_mode if mode == "CHECKIN" else run_checkout_mode
        self.active_mode_thread = threading.Thread(
            target=target, args=(self.mode_stop_event, send_to_lcd)
        )
        self.active_mode_thread.daemon = True
        self.active_mode_thread.start()
        
        if not self.mock_mode:
            send_to_lcd(f"{mode} ACTIVE")"""

new_start = """        target = run_checkin_mode if mode == "CHECKIN" else run_checkout_mode
        
        enable_webcam = os.getenv("ENABLE_WEBCAM", "false").lower() == "true"
        
        if not self.mock_mode or enable_webcam:
            self.active_mode_thread = threading.Thread(
                target=target, args=(self.mode_stop_event, send_to_lcd)
            )
            self.active_mode_thread.daemon = True
            self.active_mode_thread.start()
        else:
            print(f"[MOCK] {mode} started without webcam (ENABLE_WEBCAM=false). Use /mock/face API to simulate recognition.")
        
        if not self.mock_mode:
            send_to_lcd(f"{mode} ACTIVE")"""

content = content.replace(old_start, new_start)

with open("backend/api/services/hardware_service.py", "w") as f:
    f.write(content)
