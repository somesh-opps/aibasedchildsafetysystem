import serial
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
        ARDUINO_SERIAL_PORT,
        ARDUINO_BAUD_RATE,
        RFID_AUTHORIZED_CARDS,
        validate_config
    )
    print("[CONFIG] Configuration loaded successfully from backend.config_template")
except ImportError as e:
    print(f"[ERROR] Failed to import configuration from backend.config_template.")
    print(f"Details: {e}")
    print("\nTo fix this:")
    print("1. Copy .env.example to .env")
    print("2. Fill in your actual values in .env")
    print("3. Make sure config_template.py is in the same directory")
    sys.exit(1)

# ==========================
# RFID and Arduino Settings
# ==========================
# Configuration is now loaded from config_template.py and .env file
# To modify settings, edit your .env file (NEVER commit .env to Git!)

# ==========================
# Global State
# ==========================
current_mode = "NONE" # Possible states: "NONE", "CHECKIN", "CHECKOUT"
mode_stop_event = threading.Event() # Event to signal the current mode's loop to stop
active_mode_thread = None # To hold the reference to the active mode's thread
arduino_serial = None # Global reference to the serial connection with Arduino

def send_to_lcd(message: str):
    """Sends a message to the Arduino to display on the LCD."""
    global arduino_serial
    if arduino_serial and arduino_serial.is_open:
        try:
            # Prefix the message with "LCD:" so Arduino knows it's an LCD command
            arduino_serial.write(f"LCD:{message}\n".encode('utf-8'))
            print(f"[LCD] Sent: '{message}'")
        except serial.SerialException as e:
            print(f"[LCD ERR] Failed to send to LCD: {e}")
    else:
        print("[LCD WARN] Arduino serial not open, cannot send LCD message.")

def clear_lcd():
    """Sends a command to the Arduino to clear the LCD and show default message."""
    global arduino_serial
    if arduino_serial and arduino_serial.is_open:
        try:
            arduino_serial.write(f"CLEAR_LCD\n".encode('utf-8'))
            print("[LCD] Sent CLEAR_LCD command.")
        except serial.SerialException as e:
            print(f"[LCD ERR] Failed to send CLEAR_LCD: {e}")

def read_rfid_card_from_arduino():
    """Reads RFID card ID from the Arduino serial if available."""
    global arduino_serial
    try:
        if arduino_serial and arduino_serial.in_waiting > 0:
            line = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
            # print(f"[ARDUINO RAW] {line}") # Uncomment for debugging
            if line.startswith("RFID:"):
                card_id = line.replace("RFID:", "").strip()
                return card_id.upper() # Arduino sends it uppercase, ensure consistency
        return None
    except serial.SerialException as e:
        print(f"[RFID ERR] Serial communication error with Arduino: {e}")
        return None
    except Exception as e:
        print(f"[RFID ERR] Error processing Arduino RFID read: {e}")
        return None

def stop_current_mode():
    """Stops the currently active mode thread if one is running."""
    global current_mode, mode_stop_event, active_mode_thread
    if active_mode_thread and active_mode_thread.is_alive():
        print(f"[CONTROL] Signaling current mode ({current_mode}) to stop...")
        send_to_lcd(f"Stopping {current_mode}...")
        mode_stop_event.set() # Set the event to tell the thread to exit its loop
        active_mode_thread.join(timeout=15) # Wait for the thread to finish gracefully
        if active_mode_thread.is_alive():
            print(f"[WARN] Current mode thread ({current_mode}) did not terminate cleanly after timeout.")
            send_to_lcd("Mode did not stop")
        else:
            print(f"[CONTROL] Current mode ({current_mode}) stopped.")
            send_to_lcd("Mode Stopped!")
        mode_stop_event.clear() # Clear the event for the next mode
        active_mode_thread = None
        current_mode = "NONE" # Reset the state
        time.sleep(1) # Give time for message to display
        clear_lcd() # Reset LCD to default prompt
        return True
    return False

def start_new_mode(mode_name, mode_function):
    """Starts a new mode (check-in or check-out) in a separate thread."""
    global current_mode, active_mode_thread
    # Ensure any previous mode is stopped before starting a new one.
    stop_current_mode()

    print(f"[CONTROL] Starting {mode_name} mode...")
    send_to_lcd(f"Starting {mode_name}...")
    current_mode = mode_name
    # Pass the serial connection to the mode functions so they can send LCD updates
    active_mode_thread = threading.Thread(target=mode_function, args=(mode_stop_event, send_to_lcd))
    active_mode_thread.daemon = True # Allows main program to exit even if this thread is running
    active_mode_thread.start()
    print(f"[CONTROL] {mode_name} mode is running in the background.")
    send_to_lcd(f"{mode_name} Activating.")


def main_control():
    global current_mode, arduino_serial

    # Validate configuration before starting
    if not validate_config():
        print("[ERROR] Configuration validation failed. Please check your .env file and config_template.py")
        sys.exit(1)

    # Initialize serial port for Arduino communication
    try:
        arduino_serial = serial.Serial(ARDUINO_SERIAL_PORT, ARDUINO_BAUD_RATE, timeout=0.1)
        print(f"[ARDUINO] Serial port {ARDUINO_SERIAL_PORT} opened successfully.")
        time.sleep(2) # Give Arduino time to reset after serial connection
        arduino_serial.flushInput()
        clear_lcd() # Initialize LCD display
    except serial.SerialException as e:
        print(f"[ARDUINO ERR] Could not open serial port {ARDUINO_SERIAL_PORT}: {e}")
        print("Please check port connection, name, and permissions for Arduino.")
        sys.exit(1)

    print("\n[SYSTEM] Ready. (Press Ctrl+C in terminal to force stop at any time)")

    COOLDOWN_BETWEEN_SCANS = 3 # seconds to prevent rapid mode changes
    last_card_scan_time = 0

    try:
        while True:
            # Always check for RFID scans from Arduino
            card_id = read_rfid_card_from_arduino()
            current_time = time.time()

            # If a card is scanned and cooldown has passed
            if card_id and card_id in RFID_AUTHORIZED_CARDS and (current_time - last_card_scan_time > COOLDOWN_BETWEEN_SCANS):
                last_card_scan_time = current_time
                print(f"\n[RFID] Authorized Card {card_id} scanned!")

                if current_mode != "NONE":
                    # If a mode is active, an authorized scan means stop it.
                    send_to_lcd("Card scanned! Stopping mode...")
                    stop_current_mode()
                    # After stopping, the loop will continue and show the main menu prompt below.
                else:
                    # No mode is active, prompt the user to choose
                    send_to_lcd("Card Scanned! Choose Mode:1/2")
                    time.sleep(0.5)

                    print("\n[SYSTEM] Please choose an option:")
                    print("  1. Start Check-in")
                    print("  2. Start Check-out")
                    choice = input("Enter your choice (1 or 2): ").strip()


                    if choice == '1':
                        start_new_mode("CHECKIN", run_checkin_mode)
                    elif choice == '2':
                        start_new_mode("CHECKOUT", run_checkout_mode)
                    else:
                        print("[WARN] Invalid choice. Please scan card and try again.")
                        send_to_lcd("Invalid choice. Scan again.")
                        time.sleep(3)
                        clear_lcd()
            elif card_id and card_id not in RFID_AUTHORIZED_CARDS:
                print(f"[RFID] Unauthorized card scanned: {card_id}")
                send_to_lcd("Unauthorized Card Try again.")
                time.sleep(3)
                if current_mode == "NONE":
                    clear_lcd() # Reset LCD if no mode is active
                else:
                    send_to_lcd(f"{current_mode} Active.")

            # Small delay to prevent the loop from using 100% CPU
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[SYSTEM] KeyboardInterrupt detected. Shutting down...")
        send_to_lcd("System Shutting Down")
        time.sleep(1)
    except Exception as e:
        print(f"[SYSTEM ERROR] An unhandled error occurred in main control: {e}")
        send_to_lcd("ERROR: See Console")
        time.sleep(2)
    finally:
        stop_current_mode() # Ensure any running mode is stopped on exit
        if arduino_serial and arduino_serial.is_open:
            clear_lcd() # Final clear for LCD
            arduino_serial.close()
            print("[ARDUINO] Serial port closed.")
        print("[SYSTEM] Program terminated.")

if __name__ == "__main__":
    main_control()