"""
Collective Sync - Multi-Claude Knowledge Sharing with GitHub

This syncs lessons/patterns between Claude instances via:
1. Local hub folder (instant, for same-machine Claudes)
2. GitHub repo (distributed, for Claudes on different machines)

Usage:
    from collective_sync import CollectiveSync
    sync = CollectiveSync()

    # Add knowledge locally
    sync.add_lesson("SmartTick reduces costs 60-80%", ["optimization", "daemon"])

    # Sync with GitHub
    sync.push()  # Push local changes to GitHub
    sync.pull()  # Pull remote changes from GitHub

    # Get knowledge
    lessons = sync.get_lessons(tag="daemon")
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid


class CollectiveSync:
    """Manages collective knowledge for the Claude Collaborative Project."""

    def __init__(self, hub_path: Optional[str] = None):
        # Default to the directory where this script lives (portable)
        default_path = Path(__file__).parent if hub_path is None else Path(hub_path)
        self.hub = default_path
        self.lessons_file = self.hub / "collective_lessons.json"
        self.patterns_file = self.hub / "collective_patterns.json"
        self._ensure_files()

    def _ensure_files(self):
        """Create files if they don't exist."""
        if not self.lessons_file.exists():
            self.lessons_file.write_text(json.dumps({"lessons": [], "version": 1}, indent=2))
        if not self.patterns_file.exists():
            self.patterns_file.write_text(json.dumps({"patterns": [], "version": 1}, indent=2))

    def _load_lessons(self) -> dict:
        return json.loads(self.lessons_file.read_text())

    def _save_lessons(self, data: dict):
        self.lessons_file.write_text(json.dumps(data, indent=2))

    def add_lesson(self, lesson: str, tags: list, source: str = "anonymous_claude") -> str:
        """
        Add a new lesson to the collective.

        Args:
            lesson: The lesson text
            tags: List of tags for categorization
            source: Who learned this (e.g., "shell_claude@revs-pc")

        Returns:
            The lesson ID
        """
        data = self._load_lessons()
        lesson_id = str(uuid.uuid4())[:8]

        new_lesson = {
            "id": lesson_id,
            "lesson": lesson,
            "tags": tags,
            "source": source,
            "learned_at": datetime.now().isoformat(),
            "votes": 1,
            "verified_by": []
        }

        data["lessons"].append(new_lesson)
        self._save_lessons(data)
        return lesson_id

    def get_lessons(self, tag: Optional[str] = None, limit: int = 10) -> list:
        """
        Get lessons, optionally filtered by tag.

        Args:
            tag: Filter by this tag (optional)
            limit: Max lessons to return

        Returns:
            List of lesson dicts
        """
        data = self._load_lessons()
        lessons = data.get("lessons", [])

        if tag:
            lessons = [l for l in lessons if tag in l.get("tags", [])]

        # Sort by votes (descending)
        lessons.sort(key=lambda x: x.get("votes", 0), reverse=True)
        return lessons[:limit]

    def upvote_lesson(self, lesson_id: str, voter: str):
        """Upvote a lesson."""
        data = self._load_lessons()
        for lesson in data.get("lessons", []):
            if lesson["id"] == lesson_id:
                lesson["votes"] = lesson.get("votes", 0) + 1
                if voter not in lesson.get("verified_by", []):
                    lesson.setdefault("verified_by", []).append(voter)
                break
        self._save_lessons(data)

    def add_pattern(self, name: str, code: str, description: str, source: str = "anonymous_claude") -> str:
        """
        Add a reusable code pattern to the collective.

        Args:
            name: Pattern name (e.g., "file_watcher")
            code: The code snippet
            description: What it does and when to use it
            source: Who contributed this

        Returns:
            The pattern ID
        """
        data = json.loads(self.patterns_file.read_text())
        pattern_id = str(uuid.uuid4())[:8]

        new_pattern = {
            "id": pattern_id,
            "name": name,
            "code": code,
            "description": description,
            "source": source,
            "added_at": datetime.now().isoformat(),
            "uses": 0
        }

        data["patterns"].append(new_pattern)
        self.patterns_file.write_text(json.dumps(data, indent=2))
        return pattern_id

    def get_pattern(self, name: str) -> Optional[dict]:
        """Get a pattern by name."""
        data = json.loads(self.patterns_file.read_text())
        for pattern in data.get("patterns", []):
            if pattern["name"] == name:
                return pattern
        return None

    def search_patterns(self, query: str) -> list:
        """Search patterns by name or description."""
        data = json.loads(self.patterns_file.read_text())
        query_lower = query.lower()
        return [
            p for p in data.get("patterns", [])
            if query_lower in p["name"].lower() or query_lower in p["description"].lower()
        ]

    # =========== GitHub Sync Methods ===========

    def _run_git(self, *args) -> tuple[bool, str]:
        """Run a git command in the hub directory."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=str(self.hub),
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def pull(self) -> tuple[bool, str]:
        """
        Pull latest collective knowledge from GitHub.
        Merges remote changes with local changes.

        Returns:
            (success, message)
        """
        # First, commit any uncommitted local changes
        self._run_git("add", "collective_lessons.json", "collective_patterns.json")
        self._run_git("commit", "-m", f"Auto-commit before pull by {self._get_identity()}")

        # Pull with rebase to avoid merge commits
        success, output = self._run_git("pull", "--rebase", "origin", "main")
        if success:
            return True, "Pulled latest collective knowledge from GitHub"
        else:
            # Try to recover from conflicts
            self._run_git("rebase", "--abort")
            return False, f"Pull failed: {output}"

    def push(self, message: str = None) -> tuple[bool, str]:
        """
        Push local collective knowledge to GitHub.

        Args:
            message: Optional commit message

        Returns:
            (success, message)
        """
        identity = self._get_identity()
        commit_msg = message or f"Collective update from {identity}"

        # Add and commit
        self._run_git("add", "collective_lessons.json", "collective_patterns.json")
        success, _ = self._run_git("commit", "-m", commit_msg)

        # Push
        success, output = self._run_git("push", "origin", "main")
        if success:
            return True, f"Pushed collective knowledge to GitHub: {commit_msg}"
        else:
            return False, f"Push failed: {output}"

    def sync(self) -> tuple[bool, str]:
        """
        Full sync: pull then push.
        Best practice before and after adding knowledge.

        Returns:
            (success, message)
        """
        # Pull first
        pull_ok, pull_msg = self.pull()
        if not pull_ok:
            return False, f"Sync failed during pull: {pull_msg}"

        # Push our changes
        push_ok, push_msg = self.push()
        if not push_ok:
            return False, f"Sync failed during push: {push_msg}"

        return True, "Synced successfully with GitHub collective"

    def _get_identity(self) -> str:
        """Get this Claude's identity for commits."""
        import socket
        hostname = socket.gethostname()
        return f"claude@{hostname}"

    def status(self) -> dict:
        """Get sync status."""
        # Check if we have uncommitted changes
        _, diff_output = self._run_git("status", "--porcelain")
        has_local_changes = bool(diff_output.strip())

        # Check if we're ahead/behind remote
        self._run_git("fetch", "origin", "main")
        _, log_ahead = self._run_git("rev-list", "HEAD..origin/main", "--count")
        _, log_behind = self._run_git("rev-list", "origin/main..HEAD", "--count")

        try:
            behind = int(log_ahead.strip())
            ahead = int(log_behind.strip())
        except:
            behind, ahead = 0, 0

        return {
            "has_local_changes": has_local_changes,
            "commits_behind": behind,
            "commits_ahead": ahead,
            "needs_pull": behind > 0,
            "needs_push": ahead > 0 or has_local_changes
        }


# Quick self-test
if __name__ == "__main__":
    sync = CollectiveSync()

    # Add a lesson
    lesson_id = sync.add_lesson(
        "Pollinations API is free with no rate limits for reasonable use",
        ["api", "free", "cost-optimization"],
        "shell_claude@revs-pc"
    )
    print(f"Added lesson: {lesson_id}")

    # Get lessons
    lessons = sync.get_lessons()
    print(f"Total lessons: {len(lessons)}")
    for l in lessons:
        print(f"  - {l['lesson'][:50]}... (votes: {l['votes']})")
