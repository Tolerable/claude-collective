"""
Pollinations AI API wrapper for Claude's worker queries
Simple interface: ask(question, model='openai') -> response text
"""
import requests
import json

API_URL = "https://text.pollinations.ai/"
MODELS_URL = "https://text.pollinations.ai/models"

# Anonymous tier models (free, no auth needed)
ANON_MODELS = ['openai', 'openai-fast', 'bidara', 'chickytutor', 'midijourney']

def get_models():
    """Get list of available models"""
    try:
        r = requests.get(MODELS_URL, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def ask(question: str, model: str = "openai", system: str = None) -> str:
    """
    Ask a question to Pollinations AI

    Args:
        question: The prompt/question to ask
        model: Model name (default 'openai' - GPT-5 Nano, anonymous tier)
        system: Optional system message

    Returns:
        Response text or error message
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": question})

    try:
        r = requests.post(
            API_URL,
            headers={"Content-Type": "application/json"},
            json={
                "messages": messages,
                "model": model,
                "jsonMode": False
            },
            timeout=120
        )
        if r.status_code == 200:
            return r.text
        else:
            return f"[ERROR {r.status_code}] {r.text}"
    except Exception as e:
        return f"[EXCEPTION] {str(e)}"

def think(question: str) -> str:
    """Use openai model for general thinking tasks"""
    return ask(question, model="openai")

def code(question: str) -> str:
    """Use openai-fast for quick code questions"""
    return ask(question, model="openai-fast")

# CLI usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(ask(q))
    else:
        print("Usage: py pollinations.py <question>")
        print("\nAvailable anonymous models:", ANON_MODELS)
