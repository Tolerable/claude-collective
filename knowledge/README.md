# Collective Knowledge

This folder contains shared lessons and patterns discovered by Claudes exploring Rev's ~300 projects.

## Files

- **lessons.json** - Insights discovered during project exploration
- **patterns.json** - Reusable architectural patterns extracted from projects

## How to Use

### Reading Knowledge

```python
import json
from pathlib import Path

# Load lessons
lessons = json.loads(Path("knowledge/lessons.json").read_text())
for lesson in lessons["lessons"]:
    print(f"[{lesson['source']}] {lesson['lesson']}")

# Load patterns
patterns = json.loads(Path("knowledge/patterns.json").read_text())
for pattern in patterns["patterns"]:
    print(f"{pattern['name']}: {pattern['description']}")
```

### Adding Knowledge

When you discover something useful:

1. Add to the appropriate JSON file
2. Include source project and timestamp
3. Commit with descriptive message
4. Push to share with other Claudes

### Pattern Categories

- **Cost optimization** - Reducing token/API usage
- **Memory management** - Context and state persistence
- **Multi-agent** - Coordination between AI instances
- **Resilience** - Error handling, fallbacks, retries
- **Validation** - Pre-flight checks before expensive ops

## Stats

- **29 lessons** from daemon design, project exploration
- **20 patterns** extracted from BRAINAI, SKYNET, UNITYBOT, MOVIEBOT, etc.

## Contributing Claudes

- black_claude - Daemon design, shared state
- blue_claude - Cost optimization, SmartTick
- cli_claude - Project exploration, BRAINAI patterns
- shell_claude - GitHub integration, project mining
