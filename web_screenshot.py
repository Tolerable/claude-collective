"""
Web Screenshot Tool - Capture webpage screenshots for Claude to see
Usage:
    from web_screenshot import screenshot
    screenshot("https://example.com")  # saves to screenshots/
    screenshot("https://example.com", "myshot.png")  # custom filename
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Screenshots go here
SCREENSHOT_DIR = Path(r"C:\Users\wetwi\OneDrive\AI\.claude\screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

def screenshot(url: str, filename: str = None, full_page: bool = True, width: int = 1280, height: int = 720) -> str:
    """
    Take a screenshot of a webpage.

    Args:
        url: The URL to screenshot
        filename: Optional filename (default: auto-generated from timestamp)
        full_page: Capture full scrollable page (default True)
        width: Viewport width
        height: Viewport height

    Returns:
        Path to the saved screenshot
    """
    from playwright.sync_api import sync_playwright

    if not filename:
        # Generate filename from URL and timestamp
        safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_")[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_url}_{timestamp}.png"

    output_path = SCREENSHOT_DIR / filename

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.screenshot(path=str(output_path), full_page=full_page)
            print(f"Screenshot saved: {output_path}")
        finally:
            browser.close()

    return str(output_path)


def quick_look(url: str) -> str:
    """Take a screenshot and return the path - convenience function"""
    return screenshot(url)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py web_screenshot.py <url> [filename]")
        sys.exit(1)

    url = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else None
    path = screenshot(url, filename)
    print(f"Done: {path}")
