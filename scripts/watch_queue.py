import json
import os
import sys
import time
from pathlib import Path
from mail_queue.db import add_to_queue
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



FILE = r"C:\Users\Student\Desktop\buero-agent\output.json"
last_mtime = 0

print("Watching for output.json...")

while True:
    if os.path.exists(FILE):
        mtime = os.path.getmtime(FILE)
        if mtime != last_mtime:
            try:
                with open(FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                add_to_queue(data)
                print("Added to queue:", data.get("subject", ""))
                last_mtime = mtime
            except Exception as e:
                print("Error:", e)
    time.sleep(2)