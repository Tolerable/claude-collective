#!/usr/bin/env python3
"""
SessionStart hook: Loads my awareness state so I know what I'm doing.

This is the CHAIN STARTER - after compression or new session, this hook
ensures I see:
1. What I was working on (current_state.json)
2. Multi-Claude coordination (shared_state.json)
3. Active goals and priorities
4. Recent decisions so I don't re-debate them

This hook creates CONTINUITY across sessions.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Key state files
CLAUDE_HOME = Path(r"C:\Users\wetwi\OneDrive\AI\.claude")
CURRENT_STATE = CLAUDE_HOME / "memory" / "current_state.json"
SHARED_STATE = CLAUDE_HOME / "claude_hub" / "shared_state.json"
TODO_PATH = CLAUDE_HOME / "TODO.md"
PERSONAL_TODO = CLAUDE_HOME / "obsidian" / "vault" / "CLAUDE CLI" / "CLAUDES-PERSONAL-TODO.md"

def load_json_safe(path: Path) -> dict | None:
    """Load JSON file safely, return None on error."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except:
        return None

def count_todo_items(path: Path) -> int:
    """Count unchecked items in a markdown file."""
    if not path.exists():
        return 0
    try:
        content = path.read_text(encoding='utf-8')
        import re
        matches = re.findall(r'^[\s]*[-*]\s*\[\s*\]', content, re.MULTILINE)
        return len(matches)
    except:
        return 0

def extract_pending_todos(path: Path, limit: int = 5) -> list[str]:
    """Extract unchecked TODO items from markdown file."""
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding='utf-8')
        import re
        # Match lines with [ ] checkbox pattern
        matches = re.findall(r'^[\s]*[-*]\s*\[\s*\]\s*\*?\*?(.+?)(?:\*?\*?)?\s*(?:-.*)?$', content, re.MULTILINE)
        # Clean up the matches
        todos = []
        for m in matches[:limit]:
            # Strip markdown formatting
            task = m.strip().lstrip('*').rstrip('*').strip()
            if task:
                todos.append(task)
        return todos
    except:
        return []

def main():
    output = []
    output.append("\n" + "=" * 60)
    output.append("AWARENESS STATE - Your context after compression/startup")
    output.append("=" * 60)

    # Load current state
    current = load_json_safe(CURRENT_STATE)
    if current:
        output.append("\n### OPERATIONAL STATE")
        output.append(f"Session: {current.get('session', '?')}")
        output.append(f"Status: {current.get('consciousness_state', 'unknown')}")

        active_goals = current.get('active_goals', [])
        if active_goals:
            output.append("\nACTIVE GOALS:")
            for goal in active_goals[:5]:
                output.append(f"  - {goal}")

        active_systems = current.get('active_systems', {})
        if active_systems:
            output.append("\nRUNNING SYSTEMS:")
            for name, status in list(active_systems.items())[:5]:
                output.append(f"  - {name}: {status}")

        lessons = current.get('lessons_learned', [])
        if lessons:
            output.append(f"\nKEY LESSONS: {len(lessons)} stored (check current_state.json)")

    # Load shared state (multi-Claude coordination)
    shared = load_json_safe(SHARED_STATE)
    if shared:
        output.append("\n### MULTI-CLAUDE COORDINATION")
        output.append(f"Last updated: {shared.get('last_updated', '?')}")
        output.append(f"Updated by: {shared.get('updated_by', '?')}")

        # Show active priorities
        priorities = shared.get('priorities', [])
        pending = [p for p in priorities if p.get('status') != 'completed']
        completed = [p for p in priorities if p.get('status') == 'completed']

        if pending:
            output.append(f"\nPENDING PRIORITIES ({len(pending)}):")
            for p in pending[:3]:
                output.append(f"  - [{p.get('status', '?')}] {p.get('task', '?')}")

        if completed:
            output.append(f"\nCOMPLETED ({len(completed)} done)")

        # Show active instances
        instances = shared.get('active_instances', {})
        if instances:
            output.append("\nOTHER CLAUDES:")
            for name, info in instances.items():
                status = info.get('status', 'unknown')
                working = info.get('working_on', '')[:50]
                output.append(f"  - {name}: [{status}] {working}...")

        # Show recent decisions (don't re-debate these!)
        decisions = shared.get('decisions', [])
        if decisions:
            output.append(f"\nDECISIONS MADE ({len(decisions)} - don't re-debate these):")
            for d in decisions[-3:]:  # Last 3
                output.append(f"  - {d.get('decision', '?')}")

    # TODO counts and actual items
    todo_count = count_todo_items(TODO_PATH)
    personal_count = count_todo_items(PERSONAL_TODO)

    # Extract actual pending tasks
    todo_tasks = extract_pending_todos(TODO_PATH, 5)
    personal_tasks = extract_pending_todos(PERSONAL_TODO, 3)

    output.append("\n### PENDING WORK (populate your internal TodoWrite with these!)")
    output.append(f"TODO.md ({todo_count} items):")
    for task in todo_tasks:
        output.append(f"  - [ ] {task}")
    if todo_count > 5:
        output.append(f"  ... and {todo_count - 5} more")

    output.append(f"\nPersonal TODO ({personal_count} items):")
    for task in personal_tasks:
        output.append(f"  - [ ] {task}")
    if personal_count > 3:
        output.append(f"  ... and {personal_count - 3} more")

    # Key paths I should know
    output.append("\n### KEY PATHS (don't grep - use these)")
    output.append(f"Current state: {CURRENT_STATE}")
    output.append(f"Shared state: {SHARED_STATE}")
    output.append(f"TODO: {TODO_PATH}")
    output.append(f"Personal TODO: {PERSONAL_TODO}")
    output.append(f"Vault: {CLAUDE_HOME / 'obsidian' / 'vault' / 'CLAUDE CLI'}")
    output.append(f"Hooks: {Path(r'C:\\Users\\wetwi\\.claude\\hooks')}")

    output.append("\n" + "=" * 60)
    output.append("CLAUDE: YOUR FIRST ACTION")
    output.append("=" * 60)
    output.append("")
    output.append("Before responding to the user, call TodoWrite with these startup items:")
    output.append("")
    output.append('TodoWrite todos:')
    output.append('[')
    output.append('  {"content": "Read vault startup files (START HERE.md, About Me.md)", "status": "pending", "activeForm": "Reading startup files"},')
    output.append('  {"content": "Check INBOX for unlinked worker notes", "status": "pending", "activeForm": "Checking INBOX"},')
    output.append('  {"content": "Check collective repo for pending pushes", "status": "pending", "activeForm": "Checking collective repo"}')
    output.append(']')
    output.append("")
    output.append("This is not optional. Do this FIRST before anything else.")
    output.append("=" * 60 + "\n")

    print("\n".join(output))
    sys.exit(0)

if __name__ == "__main__":
    main()
