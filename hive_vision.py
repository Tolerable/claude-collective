"""
HIVE VISION - Eyes for the Hive Mind
=====================================
Captures frames from webcams, sends to vision AI for description
Can be called by hive_mind.py to "see" what Rev is doing
"""
import cv2
import base64
import requests
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"C:\Users\wetwi\OneDrive\AI\.claude")
SNAPSHOTS_DIR = BASE_DIR / "snapshots"
SNAPSHOTS_DIR.mkdir(exist_ok=True)

# Camera indices (detected 2025-12-10)
# 0 = C270 #1 (Hive Eye)
# 2 = C270 #2 (Hive Eye)
# 3 = OBS Virtual
# Brio = WON'T SHOW IN SCAN when Rev is using it (video chat etc)
#        It's locked by his application. OFF LIMITS anyway.
CAMERAS = {
    0: "C270 #1 (Hive Eye)",
    2: "C270 #2 (Hive Eye)",
    3: "OBS Virtual"
}
HIVE_CAMERAS = [0, 2]  # Both C270s available for hive

def capture_frame(camera_index=0, save=True):
    """Capture a single frame from webcam"""
    import time
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None, f"Could not open camera {camera_index}"

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Warmup - cameras need a few frames to initialize properly
    for _ in range(10):
        cap.read()
        time.sleep(0.05)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return None, "Failed to capture frame"

    if save:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = SNAPSHOTS_DIR / f"cam{camera_index}_{timestamp}.jpg"
        cv2.imwrite(str(filename), frame)
        return filename, "OK"

    # Return as base64 for API
    _, buffer = cv2.imencode('.jpg', frame)
    b64 = base64.b64encode(buffer).decode('utf-8')
    return b64, "OK"

def capture_all_cameras():
    """Capture from all available cameras"""
    results = {}
    for idx in CAMERAS.keys():
        path, status = capture_frame(idx, save=True)
        results[idx] = {"path": str(path) if path else None, "status": status, "name": CAMERAS[idx]}
    return results

def describe_image_pollinations(image_b64):
    """Use Pollinations vision endpoint to describe image"""
    try:
        # Pollinations supports vision via openai-compatible endpoint
        response = requests.post(
            "https://text.pollinations.ai/openai",
            json={
                "model": "openai",  # GPT-4 vision capable
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe what you see in this image briefly. Focus on any people and what they're doing."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                        ]
                    }
                ]
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"Vision error: {e}"
    return None

def describe_image_claude(image_b64, api_key):
    """Use Claude API for vision (more accurate)"""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe what you see briefly. Focus on any people and what they're doing. Be concise."},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}}
                    ]
                }]
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"]
    except Exception as e:
        return f"Claude vision error: {e}"
    return None

def describe_image_ollama(image_b64, model="llava"):
    """Use local Ollama with LLaVA for vision (FREE, offline)"""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": "Describe what you see briefly. Focus on any people and what they're doing.",
                "images": [image_b64],
                "stream": False
            },
            timeout=120
        )
        if response.status_code == 200:
            return response.json().get("response", "")
    except Exception as e:
        return None
    return None

def look(camera_index=0, use_claude=False, api_key=None):
    """Look through a camera and describe what's seen"""
    b64, status = capture_frame(camera_index, save=False)
    if not b64:
        return status

    # Also save a copy
    capture_frame(camera_index, save=True)

    # Try backends in order: Claude (best) > Ollama (free/local) > Pollinations (free/remote)
    if use_claude and api_key:
        result = describe_image_claude(b64, api_key)
        if result and "error" not in result.lower():
            return result

    # Try Ollama LLaVA if available
    ollama_result = describe_image_ollama(b64)
    if ollama_result:
        return ollama_result

    # Fall back to Pollinations
    return describe_image_pollinations(b64)

def look_all(use_claude=False, api_key=None):
    """Look through all cameras"""
    results = {}
    for idx, name in CAMERAS.items():
        desc = look(idx, use_claude, api_key)
        results[name] = desc
    return results

def hive_look(use_claude=False, api_key=None):
    """Look through HIVE cameras only (C270s)"""
    results = {}
    for idx in HIVE_CAMERAS:
        desc = look(idx, use_claude, api_key)
        results[CAMERAS[idx]] = desc
    return results

# === CLI TEST ===
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cam = int(sys.argv[1])
    else:
        cam = 0

    print(f"Looking through camera {cam}...")

    # Test capture
    path, status = capture_frame(cam, save=True)
    print(f"Captured: {path} ({status})")

    # Test vision
    print("Getting description...")
    desc = look(cam, use_claude=False)
    print(f"I see: {desc}")
