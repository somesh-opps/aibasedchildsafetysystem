import os

def patch_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()
    
    # Catch imshow errors to avoid crashing if no display
    old_imshow = "cv2.imshow("
    new_imshow = """try:
            cv2.imshow("""
    
    if "try:\n            cv2.imshow" not in content:
        content = content.replace("        cv2.imshow(", new_imshow)
        content = content.replace("            cv2.imshow(", "    " + new_imshow)
        
        # We need to add the except block. We'll do it by regex or split.
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if "try:\n            cv2.imshow" in line: # This won't match line by line
                pass
            new_lines.append(line)
            
            # Simple approach: just replace 'cv2.imshow' and 'cv2.waitKey' with safe versions globally.
    
    # Actually, a simpler way is to redefine cv2.imshow at the top of the file!
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
    # Replace import cv2
    content = content.replace("import cv2\n", safe_cv2_code)
    
    with open(filepath, "w") as f:
        f.write(content)

patch_file("backend/checkin.py")
patch_file("backend/checkout.py")
