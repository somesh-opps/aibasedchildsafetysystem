import threading
import time
import os
import asyncio
from hardware.main_rfid_control import (
    read_rfid_card_from_arduino,
    send_to_lcd,
    clear_lcd
)
from backend.config_template import RFID_AUTHORIZED_CARDS
from backend.checkin import run_checkin_mode
from backend.checkout import run_checkout_mode
from backend.api.routes.events import manager

class HardwareManager:
    def __init__(self):
        self.current_mode = "NONE"
        self.mode_stop_event = threading.Event()
        self.active_mode_thread = None
        self.mock_mode = os.getenv("HARDWARE_MODE", "real") == "mock"
        
        # We assume connected if mock, else we'd need to actually open the port.
        self.is_connected = self.mock_mode

        self.bg_thread = threading.Thread(target=self._hardware_loop, daemon=True)
        self.bg_thread.start()
        
    def _broadcast_event(self, event_type, details):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(manager.broadcast({
                    "event": event_type,
                    "data": {
                        "type": event_type,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        **details
                    }
                }), loop)
        except Exception as e:
            print(f"[WS WARN] Failed to broadcast event: {e}")

    def start_mode(self, mode):
        self.stop_mode()
        self.current_mode = mode
        self.mode_stop_event.clear()
        
        target = run_checkin_mode if mode == "CHECKIN" else run_checkout_mode
        
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
            send_to_lcd(f"{mode} ACTIVE")
        self._broadcast_event("system_status", {"checkin": mode == "CHECKIN", "checkout": mode == "CHECKOUT"})

    def stop_mode(self):
        if self.active_mode_thread and self.active_mode_thread.is_alive():
            self.mode_stop_event.set()
            self.active_mode_thread.join(timeout=5)
        self.current_mode = "NONE"
        self.active_mode_thread = None
        if not self.mock_mode:
            clear_lcd()
        self._broadcast_event("system_status", {"checkin": False, "checkout": False})

    def mock_scan(self, card_id):
        """Simulate an RFID scan from the API (mock mode)."""
        if self.mock_mode:
            self._handle_scan(card_id)

    def _handle_scan(self, card_id):
        self._broadcast_event("attendance", {"event_type": "RFID_SCANNED", "student_id": card_id, "student_name": card_id, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "scanned", "method": "RFID"})
        
        if card_id in RFID_AUTHORIZED_CARDS:
            if self.current_mode != "NONE":
                self.stop_mode()
            else:
                self._broadcast_event("attendance", {"event_type": "AUTHORIZED_SCAN", "student_id": card_id, "student_name": card_id, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "success", "method": "RFID"})
        else:
            if not self.mock_mode:
                send_to_lcd("UNAUTHORIZED")

    def _hardware_loop(self):
        last_scan = 0
        while True:
            if not self.mock_mode:
                try:
                    card_id = read_rfid_card_from_arduino()
                    if card_id and time.time() - last_scan > 3:
                        last_scan = time.time()
                        self._handle_scan(card_id)
                except Exception as e:
                    pass
            time.sleep(0.5)

hardware_manager = HardwareManager()
