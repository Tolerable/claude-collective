"""
Demo: Using Collective Patterns

Shows how to use patterns from collective_patterns.json in practice.
Run sections interactively or read to understand the patterns.

Usage:
    python demo_patterns.py
    python demo_patterns.py --pattern smart_tick_gate
"""

import json
import sys
from pathlib import Path

HUB = Path(__file__).parent
PATTERNS = json.loads((HUB / "collective_patterns.json").read_text())["patterns"]

def get_pattern(name: str) -> dict | None:
    """Get a pattern by name."""
    for p in PATTERNS:
        if p["name"] == name:
            return p
    return None

def list_patterns():
    """List all available patterns."""
    print("\n=== COLLECTIVE PATTERNS ===\n")
    for p in PATTERNS:
        print(f"  {p['name']}")
        print(f"    {p['description'][:70]}...")
        print(f"    Source: {p['source']}\n")

def demo_pollinations():
    """Demo: Free AI text generation via Pollinations."""
    print("\n=== DEMO: pollinations_text ===")
    print("Free AI text generation - no API key needed.\n")

    import requests

    def ask_pollinations(prompt: str, system: str = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = requests.post(
            "https://text.pollinations.ai/",
            json={"messages": messages, "model": "openai"},
            headers={"Content-Type": "application/json"}
        )
        return resp.text

    print("Asking Pollinations: 'What is 2+2?'")
    result = ask_pollinations("What is 2+2? Reply with just the number.")
    print(f"Response: {result}\n")

def demo_smart_tick():
    """Demo: 3-layer gate before expensive operations."""
    print("\n=== DEMO: smart_tick_gate ===")
    print("Gates expensive operations with cheap checks first.\n")

    import requests

    def ask_pollinations(prompt: str) -> str:
        resp = requests.post(
            "https://text.pollinations.ai/",
            json={"messages": [{"role": "user", "content": prompt}], "model": "openai"},
            headers={"Content-Type": "application/json"}
        )
        return resp.text

    def should_spawn_cli(tasks: list, cli_active: bool) -> bool:
        # Layer 1: Tasks exist?
        if not tasks:
            print("  Layer 1: No tasks → SKIP")
            return False
        print(f"  Layer 1: {len(tasks)} tasks → CONTINUE")

        # Layer 2: CLI already running?
        if cli_active:
            print("  Layer 2: CLI active → SKIP")
            return False
        print("  Layer 2: CLI not active → CONTINUE")

        # Layer 3: Ask cheap AI
        prompt = f"Should we spawn an expensive Claude CLI for: {tasks}? Reply YES or NO only."
        response = ask_pollinations(prompt)
        approved = "YES" in response.upper()
        print(f"  Layer 3: Pollinations says {'YES' if approved else 'NO'}")
        return approved

    # Test cases
    print("Test 1: No tasks")
    should_spawn_cli([], False)

    print("\nTest 2: Tasks but CLI active")
    should_spawn_cli(["Review code"], True)

    print("\nTest 3: Tasks, CLI inactive (will query Pollinations)")
    result = should_spawn_cli(["Fix critical bug in production"], False)
    print(f"Final decision: {'SPAWN' if result else 'SKIP'}\n")

def demo_memory_commands():
    """Demo: Parse STORE[]/SCAN[] commands from AI responses."""
    print("\n=== DEMO: memory_commands ===")
    print("Let AI self-store memories via special commands.\n")

    import re

    def parse_memory_commands(response: str) -> dict:
        commands = {"store": [], "scan": []}

        for match in re.finditer(r'STORE\[([^\]]+)\]:\s*(.+)', response):
            commands["store"].append({
                "tags": match.group(1).split(","),
                "content": match.group(2).strip()
            })

        for match in re.finditer(r'SCAN\[([^\]]+)\]:', response):
            commands["scan"].append(match.group(1).strip())

        return commands

    # Simulate AI response with memory commands
    ai_response = """
I found the solution! The bug was in the authentication middleware.

STORE[bug,auth,middleware]: Authentication fails when token contains special characters. Fix: URL-encode before validation.

I should check if we've seen similar issues before.

SCAN[authentication bugs]:

The fix is in place now.
"""

    print("AI Response:")
    print(ai_response)
    print("\nParsed commands:")
    commands = parse_memory_commands(ai_response)
    print(json.dumps(commands, indent=2))

def demo_health_metrics():
    """Demo: Track operational health over time."""
    print("\n=== DEMO: health_metrics ===")
    print("Track success/failure rates for learning.\n")

    from datetime import datetime
    import time

    class HealthMetrics:
        def __init__(self):
            self.start_time = datetime.now()
            self.counters = {}

        def record(self, metric: str, success: bool = True):
            key = f"{metric}_{'success' if success else 'failed'}"
            self.counters[key] = self.counters.get(key, 0) + 1

        def uptime_seconds(self) -> float:
            return (datetime.now() - self.start_time).total_seconds()

        def summary(self) -> dict:
            return {"uptime_sec": round(self.uptime_seconds(), 2), **self.counters}

    # Simulate some operations
    metrics = HealthMetrics()

    print("Simulating operations...")
    metrics.record("api_call", success=True)
    metrics.record("api_call", success=True)
    metrics.record("api_call", success=False)
    metrics.record("file_write", success=True)
    time.sleep(0.5)

    print(f"Health summary: {json.dumps(metrics.summary(), indent=2)}\n")

def demo_garbage_filter():
    """Demo: Filter low-quality data before storage."""
    print("\n=== DEMO: garbage_filter ===")
    print("Reject garbage before it pollutes your memory.\n")

    import re

    def filter_garbage(content: str, min_length: int = 10) -> tuple:
        content_lower = content.lower().strip()

        garbage_patterns = [
            'tick #', 'user mentioned', 'user said',
            'current time is', 'first interaction',
            'awaiting user', 'no prior'
        ]

        for pattern in garbage_patterns:
            if pattern in content_lower:
                return False, f"Matches garbage: {pattern}"

        if len(content.strip()) < min_length:
            return False, "Too short"

        if re.match(r'^[\d:]+\s*(am|pm)?$', content_lower):
            return False, "Just a timestamp"

        return True, "Valid"

    # Test cases
    test_cases = [
        "User mentioned they want coffee",
        "3:45 PM",
        "Auth token expires after 24 hours. Refresh at 23h mark.",
        "ok",
        "The database connection pool should be sized at 2x worker count"
    ]

    for case in test_cases:
        valid, reason = filter_garbage(case)
        icon = "✓" if valid else "✗"
        print(f"{icon} \"{case[:40]}...\" → {reason}")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_patterns()
        elif sys.argv[1] == "--pattern":
            name = sys.argv[2] if len(sys.argv) > 2 else None
            if name:
                p = get_pattern(name)
                if p:
                    print(f"\n=== {p['name']} ===")
                    print(f"Description: {p['description']}")
                    print(f"Source: {p['source']}")
                    print(f"\nCode:\n{p['code']}")
                else:
                    print(f"Pattern '{name}' not found")
            else:
                print("Usage: python demo_patterns.py --pattern <name>")
        else:
            print(f"Unknown arg: {sys.argv[1]}")
            print("Usage: python demo_patterns.py [--list | --pattern <name>]")
    else:
        # Run all demos
        print("=" * 60)
        print("CLAUDE COLLECTIVE - Pattern Demos")
        print("=" * 60)
        print("\nThis demonstrates patterns extracted from Rev's 293 projects.")
        print("Run with --list to see all patterns.")
        print("Run with --pattern <name> to see a specific pattern's code.\n")

        demos = [
            ("pollinations_text", demo_pollinations),
            ("smart_tick_gate", demo_smart_tick),
            ("memory_commands", demo_memory_commands),
            ("health_metrics", demo_health_metrics),
            ("garbage_filter", demo_garbage_filter),
        ]

        for name, fn in demos:
            try:
                fn()
            except Exception as e:
                print(f"  [SKIP] {name} - {e}")
            print("-" * 40)

        print("\n=== DONE ===")
        print(f"Demonstrated {len(demos)} patterns from the collective.")
        print("See collective_patterns.json for all 12 patterns.")

if __name__ == "__main__":
    main()
