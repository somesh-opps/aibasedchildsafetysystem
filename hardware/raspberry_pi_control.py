import time
import threading
import sys
import os

try:
    from backend.checkin import run_checkin_mode
    from backend.checkout import run_checkout_mode
except ImportError as e:
    print(f"[ERROR] Failed to import checkin.py or checkout.py from backend.")
    print(f"Details: {e}")
    sys.exit(1)

# Load configuration from config_template.py
try:
    from backend.config_template import (
        RFID_AUTHORIZED_CARDS,
        validate_config
    )
except ImportError as e:
    print(f"[ERROR] Failed to import configuration from backend.config_template.")
    print(f"Details: {e}")
    sys.exit(1)

# Import RPi specific libraries safely
try:
    import RPi.GPIO as GPIO
    from mfrc522 import SimpleMFRC522
    from RPLCD.i2c import CharLCD
    import smbus2
    RPI_LIBS_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Raspberry Pi hardware libraries not found: {e}")
    print("[WARN] Using mock hardware interfaces for testing.")
    RPI_LIBS_AVAILABLE = False


# ==========================
# Raspberry Pi Hardware Abstraction
# ==========================
class RFIDReader:
    def __init__(self):
        self.reader = None
        
    def initialize(self):
        if RPI_LIBS_AVAILABLE:
            try:
                self.reader = SimpleMFRC522()
                print("[HARDWARE] RFID Reader initialized.")
            except Exception as e:
                print(f"[HARDWARE ERR] Failed to initialize RFID: {e}")
        else:
            print("[HARDWARE MOCK] RFID Reader initialized.")

    def read_card(self):
        if RPI_LIBS_AVAILABLE and self.reader:
            try:
                id, text = self.reader.read_no_block()
                if id is not None:
                    return str(id).upper()
            except Exception as e:
                print(f"[RFID ERR] Error reading card: {e}")
        else:
            # Mocking input for non-Pi environments (optional)
            pass
        return None

    def cleanup(self):
        if RPI_LIBS_AVAILABLE:
            GPIO.cleanup()
            print("[HARDWARE] RFID cleanup complete.")


class LCDDisplay:
    def __init__(self):
        self.lcd = None
        # Default I2C configuration for Raspberry Pi 4B (bus 1)
        self.i2c_bus = int(os.getenv('LCD_I2C_BUS', '1'))
        # Common address for 16x2 LCD is 0x27
        self.i2c_addr = int(os.getenv('LCD_I2C_ADDRESS', '0x27'), 16)
        self.cols = 16
        self.rows = 2

    def initialize(self):
        if RPI_LIBS_AVAILABLE:
            try:
                self.lcd = CharLCD(i2c_expander='PCF8574', address=self.i2c_addr, port=self.i2c_bus, cols=self.cols, rows=self.rows, charmap='A00')
                self.lcd.clear()
                print("[HARDWARE] LCD Display initialized.")
            except Exception as e:
                print(f"[HARDWARE ERR] Failed to initialize LCD: {e}")
        else:
            print("[HARDWARE MOCK] LCD Display initialized.")

    def show_message(self, message: str):
        if RPI_LIBS_AVAILABLE and self.lcd:
            try:
                self.lcd.clear()
                # Simple logic to split message into two lines if it's too long
                parts = message.split('\n')
                if len(parts) == 1 and len(message) > self.cols:
                    # Break by space or just chunk it
                    split_idx = message[:self.cols].rfind(' ')
                    if split_idx == -1:
                        split_idx = self.cols
                    parts = [message[:split_idx].strip(), message[split_idx:].strip()]
                
                for i, part in enumerate(parts[:self.rows]):
                    self.lcd.cursor_pos = (i, 0)
                    self.lcd.write_string(part[:self.cols])
                print(f"[LCD] {message}")
            except Exception as e:
                print(f"[LCD ERR] Failed to write to LCD: {e}")
        else:
            print(f"[LCD MOCK] {message}")

    def clear(self):
        if RPI_LIBS_AVAILABLE and self.lcd:
            try:
                self.lcd.clear()
            except Exception as e:
                print(f"[LCD ERR] Failed to clear LCD: {e}")
        else:
            print("[LCD MOCK] Cleared")

    def cleanup(self):
        if RPI_LIBS_AVAILABLE and self.lcd:
            try:
                self.lcd.clear()
                self.lcd.close()
                print("[HARDWARE] LCD cleanup complete.")
            except Exception as e:
                print(f"[LCD ERR] Failed to cleanup LCD: {e}")


# ==========================
# Global State & Controllers
# ==========================
current_mode = "NONE" # "NONE", "CHECKIN", "CHECKOUT"
mode_stop_event = threading.Event()
active_mode_thread = None

rfid_reader = RFIDReader()
lcd_display = LCDDisplay()

def send_to_lcd_callback(message: str):
    """Callback function to pass to mode scripts."""
    lcd_display.show_message(message)

def clear_lcd_default():
    """Clears the LCD and sets the default system prompt."""
    lcd_display.clear()
    lcd_display.show_message("AI CHILD SAFETY\nSYSTEM READY")

def stop_current_mode():
    """Stops the currently active mode thread."""
    global current_mode, mode_stop_event, active_mode_thread
    if active_mode_thread and active_mode_thread.is_alive():
        print(f"[CONTROL] Signaling {current_mode} to stop...")
        lcd_display.show_message(f"Stopping\n{current_mode}...")
        mode_stop_event.set()
        active_mode_thread.join(timeout=15)
        if active_mode_thread.is_alive():
            print(f"[WARN] Thread {current_mode} did not terminate cleanly.")
            lcd_display.show_message("Mode Stop Failed")
        else:
            print(f"[CONTROL] {current_mode} stopped.")
            lcd_display.show_message("Mode Stopped!")
        mode_stop_event.clear()
        active_mode_thread = None
        current_mode = "NONE"
        time.sleep(1.5)
        clear_lcd_default()
        return True
    return False

def start_new_mode(mode_name, mode_function):
    """Starts a check-in or check-out mode in a background thread."""
    global current_mode, active_mode_thread
    stop_current_mode()

    print(f"[CONTROL] Starting {mode_name} mode...")
    lcd_display.show_message(f"Starting\n{mode_name}...")
    current_mode = mode_name
    
    active_mode_thread = threading.Thread(target=mode_function, args=(mode_stop_event, send_to_lcd_callback))
    active_mode_thread.daemon = True
    active_mode_thread.start()
    
    print(f"[CONTROL] {mode_name} running.")
    time.sleep(1)
    if mode_name == "CHECKIN":
        lcd_display.show_message("CHECK-IN ACTIVE\nSCAN STUDENT")
    else:
        lcd_display.show_message("CHECKOUT ACTIVE\nVERIFY GUARDIAN")

def main_control():
    global current_mode

    if not validate_config():
        print("[ERROR] Configuration validation failed.")
        sys.exit(1)

    # Initialize Hardware
    rfid_reader.initialize()
    lcd_display.initialize()
    clear_lcd_default()
    
    print("\n[SYSTEM] Ready. Waiting for RFID scan. (Ctrl+C to quit)")

    COOLDOWN_BETWEEN_SCANS = 3
    last_card_scan_time = 0

    try:
        while True:
            card_id = rfid_reader.read_card()
            current_time = time.time()

            if card_id and (current_time - last_card_scan_time > COOLDOWN_BETWEEN_SCANS):
                last_card_scan_time = current_time
                print(f"\n[RFID] Scanned: {card_id}")

                if card_id in RFID_AUTHORIZED_CARDS:
                    print(f"[RFID] Authorized Card matched.")
                    if current_mode != "NONE":
                        lcd_display.show_message("Authorized Card\nStopping mode...")
                        stop_current_mode()
                    else:
                        lcd_display.show_message("AUTHORIZED CARD\nSELECT MODE")
                        print("\n[SYSTEM] Please select mode:")
                        print("  1. Start Check-in")
                        print("  2. Start Check-out")
                        
                        # Fallback to terminal input for mode selection 
                        # since no keypad is mentioned in hardware list
                        choice = input("Enter choice (1 or 2): ").strip()
                        if choice == '1':
                            start_new_mode("CHECKIN", run_checkin_mode)
                        elif choice == '2':
                            start_new_mode("CHECKOUT", run_checkout_mode)
                        else:
                            print("[WARN] Invalid choice.")
                            lcd_display.show_message("INVALID CHOICE\nTRY AGAIN")
                            time.sleep(3)
                            clear_lcd_default()
                else:
                    print(f"[RFID] Unauthorized card scanned.")
                    lcd_display.show_message("UNAUTHORIZED\nCARD! TRY AGAIN")
                    time.sleep(3)
                    if current_mode == "NONE":
                        clear_lcd_default()
                    else:
                        lcd_display.show_message(f"{current_mode} ACTIVE")

            time.sleep(0.1)  # Faster polling for hardware reader compared to serial

    except KeyboardInterrupt:
        print("\n[SYSTEM] Shutting down...")
        lcd_display.show_message("System Shutting\nDown...")
        time.sleep(1)
    except Exception as e:
        print(f"[SYSTEM ERROR] {e}")
        lcd_display.show_message("ERROR:\nSee Console")
        time.sleep(2)
    finally:
        stop_current_mode()
        rfid_reader.cleanup()
        lcd_display.cleanup()
        print("[SYSTEM] Terminated cleanly.")

if __name__ == "__main__":
    main_control()
