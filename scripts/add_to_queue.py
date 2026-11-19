import json
import sys
from pathlib import Path
from mail_queue.db import add_to_queue
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



def main():
    with open("output.json","r", encoding="utf-8") as f:
        data = json.load(f)
        
    add_to_queue(data)
    print("Add to queue")
    
if __name__ == "__main__":
    main()