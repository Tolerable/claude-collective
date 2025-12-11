"""
Voice Listener for Claude

Listens for speech and writes it to an inbox for Claude to process.
Can run standalone or be integrated with the discord bot.

Setup:
    pip install SpeechRecognition pyaudio

Usage:
    py voice_listener.py                    # Listen once
    py voice_listener.py --loop             # Continuous listening
    py voice_listener.py --wake "hey claude" # Wake word mode

The listener writes to inbox/heard.json:
{
    "text": "what the user said",
    "timestamp": "2025-01-01T12:00:00",
    "confidence": 0.95
}

Claude (or a script) can watch this file and respond.
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

INBOX = Path(os.environ.get("CLAUDE_INBOX", Path.home() / ".claude" / "inbox"))
OUTBOX = Path(os.environ.get("CLAUDE_OUTBOX", Path.home() / ".claude" / "outbox"))

# Speech recognition settings
LISTEN_TIMEOUT = 5          # How long to wait for speech to start
PHRASE_TIMEOUT = 10         # Max length of a phrase
ENERGY_THRESHOLD = 300      # Microphone sensitivity (lower = more sensitive)

# =============================================================================
# SPEECH RECOGNITION
# =============================================================================

def get_recognizer():
    """Set up speech recognizer"""
    try:
        import speech_recognition as sr
    except ImportError:
        print("SpeechRecognition not installed. Run: pip install SpeechRecognition")
        sys.exit(1)

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD
    recognizer.dynamic_energy_threshold = True
    return recognizer

def list_microphones():
    """List available microphones"""
    try:
        import speech_recognition as sr
        print("Available microphones:")
        for i, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"  [{i}] {name}")
    except Exception as e:
        print(f"Error listing microphones: {e}")

def listen_once(device_index=None, timeout=LISTEN_TIMEOUT):
    """Listen for one phrase and return text"""
    import speech_recognition as sr

    recognizer = get_recognizer()

    try:
        with sr.Microphone(device_index=device_index) as source:
            print("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Listening...")

            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=PHRASE_TIMEOUT
            )

            print("Processing...")
            text = recognizer.recognize_google(audio)
            return {"text": text, "confidence": 1.0, "error": None}

    except sr.WaitTimeoutError:
        return {"text": None, "error": "No speech detected (timeout)"}
    except sr.UnknownValueError:
        return {"text": None, "error": "Could not understand audio"}
    except sr.RequestError as e:
        return {"text": None, "error": f"Recognition service error: {e}"}
    except Exception as e:
        return {"text": None, "error": str(e)}

def write_to_inbox(result: dict):
    """Write heard text to inbox for Claude"""
    INBOX.mkdir(parents=True, exist_ok=True)

    data = {
        "text": result.get("text"),
        "timestamp": datetime.now().isoformat(),
        "error": result.get("error")
    }

    # Write to a fixed file that Claude can watch
    inbox_file = INBOX / "heard.json"
    inbox_file.write_text(json.dumps(data, indent=2))
    print(f"Wrote to {inbox_file}")

    # Also write timestamped version for history
    if result.get("text"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        history_file = INBOX / f"heard_{ts}.json"
        history_file.write_text(json.dumps(data, indent=2))

def request_response(text: str, voice: str = None):
    """Write a message to outbox requesting Claude to respond and speak"""
    OUTBOX.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    msg = {
        "type": "voice_query",
        "from": "voice_listener",
        "text": text,
        "timestamp": datetime.now().isoformat(),
        "respond_with_voice": True,
        "voice": voice
    }

    outfile = OUTBOX / f"voice_query_{ts}.json"
    outfile.write_text(json.dumps(msg, indent=2))
    print(f"Requested response for: {text[:50]}...")

# =============================================================================
# MAIN MODES
# =============================================================================

def run_once(device_index=None):
    """Listen once and write to inbox"""
    result = listen_once(device_index)

    if result.get("text"):
        print(f"Heard: {result['text']}")
        write_to_inbox(result)
    else:
        print(f"Error: {result.get('error')}")

def run_loop(device_index=None, wake_word=None):
    """Continuously listen"""
    import speech_recognition as sr

    recognizer = get_recognizer()
    wake_word = wake_word.lower() if wake_word else None

    print(f"Continuous listening mode" + (f" (wake word: '{wake_word}')" if wake_word else ""))
    print("Press Ctrl+C to stop")

    try:
        with sr.Microphone(device_index=device_index) as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)

            while True:
                try:
                    print("\n🎤 Listening...")
                    audio = recognizer.listen(source, phrase_time_limit=PHRASE_TIMEOUT)
                    text = recognizer.recognize_google(audio)

                    if wake_word:
                        if wake_word in text.lower():
                            # Remove wake word from text
                            clean_text = text.lower().replace(wake_word, "").strip()
                            if clean_text:
                                print(f"🗣️ [{wake_word}] {clean_text}")
                                write_to_inbox({"text": clean_text})
                                request_response(clean_text)
                        else:
                            print(f"(ignored: {text})")
                    else:
                        print(f"🗣️ {text}")
                        write_to_inbox({"text": text})

                except sr.UnknownValueError:
                    pass  # Silence or unclear
                except sr.RequestError as e:
                    print(f"⚠️ Service error: {e}")

    except KeyboardInterrupt:
        print("\nStopped.")

# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice listener for Claude")
    parser.add_argument("--list", action="store_true", help="List available microphones")
    parser.add_argument("--device", type=int, help="Microphone device index")
    parser.add_argument("--loop", action="store_true", help="Continuous listening mode")
    parser.add_argument("--wake", type=str, help="Wake word (e.g., 'hey claude')")

    args = parser.parse_args()

    if args.list:
        list_microphones()
    elif args.loop or args.wake:
        run_loop(device_index=args.device, wake_word=args.wake)
    else:
        run_once(device_index=args.device)
