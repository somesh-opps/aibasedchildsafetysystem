import sys

def patch_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    # Remove global imports
    content = content.replace("import pywhatkit as kit\n", "")
    content = content.replace("import pyautogui\n", "")
    
    # Inject lazy import into send_whatsapp_message
    if "def send_whatsapp_message(" in content or "def send_whatsapp_message_checkout(" in content:
        # We'll just replace the function body to do lazy import
        old_str = "    if not phone_number"
        new_str = """    try:
        import pywhatkit as kit
        import pyautogui
    except Exception as e:
        print(f"[WARN] WhatsApp automation disabled (GUI not available): {e}")
        kit = None

    if not phone_number"""
        content = content.replace(old_str, new_str)
        
        # also guard the actual call
        call_str = "kit.sendwhatmsg_instantly("
        new_call_str = "if kit:\n            kit.sendwhatmsg_instantly("
        content = content.replace(call_str, new_call_str)
        
        call_str2 = "pyautogui.FAILSAFE"
        new_call_str2 = "if kit:\n            pyautogui.FAILSAFE"
        content = content.replace(call_str2, new_call_str2)

        call_str3 = "pyautogui.press"
        new_call_str3 = "if kit:\n            pyautogui.press"
        content = content.replace(call_str3, new_call_str3)

        call_str4 = "pyautogui.hotkey"
        new_call_str4 = "if kit:\n            pyautogui.hotkey"
        content = content.replace(call_str4, new_call_str4)
        
    with open(filepath, "w") as f:
        f.write(content)

patch_file("backend/checkin.py")
patch_file("backend/checkout.py")
print("Patched X11 dependencies")
