import os

def patch_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()
        
    # 1. Replace pywhatkit / pyautogui imports
    content = content.replace("import pywhatkit as kit\n", "")
    content = content.replace("import pyautogui\n", "")
    
    # 2. Inject lazy import in send_whatsapp_message
    if "def send_whatsapp_message(" in content or "def send_whatsapp_message_checkout(" in content:
        content = content.replace(
            "def send_whatsapp_message",
            "def send_whatsapp_message"
        )
        # Find where to insert lazy import
        old_str = "    if not phone_number"
        new_str = """    try:
        import pywhatkit as kit
        import pyautogui
    except Exception as e:
        print(f"[WARN] WhatsApp automation disabled (GUI not available): {e}")
        kit = None

    if not phone_number"""
        content = content.replace(old_str, new_str)
        
        # 3. Guard pyautogui and kit calls
        content = content.replace("kit.sendwhatmsg_instantly(", "if kit:\n            kit.sendwhatmsg_instantly(")
        content = content.replace("pyautogui.FAILSAFE", "if kit:\n            pyautogui.FAILSAFE")
        content = content.replace("pyautogui.press", "if kit:\n            pyautogui.press")
        content = content.replace("pyautogui.hotkey", "if kit:\n            pyautogui.hotkey")

    # 4. Safe cv2
    safe_cv2_code = """
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
"""
    content = content.replace("import cv2\n", safe_cv2_code)
    
    with open(filepath, "w") as f:
        f.write(content)

patch_file("backend/checkin.py")
patch_file("backend/checkout.py")
print("Cleanly patched X11 dependencies")
