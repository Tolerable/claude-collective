"""
Vision Watcher - Uses Ollama llava to watch webcam stream and log observations
Saves tokens by letting me read text instead of images
"""
import os
import time
import base64
import requests
from datetime import datetime
from pathlib import Path

WEBCAM_PATH = r"C:\Users\wetwi\OneDrive\AI\.claude\stream_frames\webcam.jpg"
DESKTOP_PATH = r"C:\Users\wetwi\OneDrive\AI\.claude\stream_frames\current.jpg"
LOG_PATH = r"C:\Users\wetwi\OneDrive\AI\.claude\stream_frames\vision_log.txt"
OLLAMA_URL = "http://localhost:11434/api/generate"

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def describe_image(image_path, prompt="This is a single webcam image of one person. Describe in 1-2 sentences: what is the person doing, their general mood/expression, and any notable items visible."):
    try:
        img_b64 = encode_image(image_path)
        response = requests.post(OLLAMA_URL, json={
            "model": "llava:7b",
            "prompt": prompt,
            "images": [img_b64],
            "stream": False
        }, timeout=60)
        if response.ok:
            return response.json().get("response", "No response")
        return f"Error: {response.status_code}"
    except Exception as e:
        return f"Error: {e}"

def log_observation(source, description):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{source}] {description}\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

def watch_loop(interval=30, source="webcam"):
    """Watch and log every interval seconds"""
    path = WEBCAM_PATH if source == "webcam" else DESKTOP_PATH
    print(f"Starting vision watcher on {source}, interval={interval}s")
    print(f"Logging to: {LOG_PATH}")

    last_mtime = 0
    while True:
        try:
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                if mtime > last_mtime:
                    desc = describe_image(path)
                    log_observation(source, desc)
                    last_mtime = mtime
            time.sleep(interval)
        except KeyboardInterrupt:
            print("Stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    import sys
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    source = sys.argv[2] if len(sys.argv) > 2 else "webcam"
    watch_loop(interval, source)
