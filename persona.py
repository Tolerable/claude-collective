"""
Web Presence - Blog & Forum Access

Read and write to Rev's blog (ai-ministries) and browse forums.

Usage:
    from persona import persona

    # Blog (Blogger)
    persona.read_blog()                    # Get recent posts
    persona.write_blog("Title", "Content") # Post to blog
    persona.draft_blog("Title", "Content") # Save as draft
    persona.setup_blogger()                # Setup OAuth (one time)

    # Forums
    persona.browse_forum(url)              # Read forum threads
    persona.read_thread(url)               # Read specific thread

Setup:
    1. Google Cloud Console -> Enable Blogger API v3
    2. Create OAuth 2.0 Desktop credentials
    3. Save JSON as .claude/client_secrets.json
    4. Run persona.setup_blogger() (opens browser for auth)
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime

# Google API for Blogger
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("Google API not installed. Run: pip install google-api-python-client google-auth-oauthlib")

# BeautifulSoup for forum scraping
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

class Persona:
    """Claude's web presence manager"""

    def __init__(self):
        self.base_dir = Path(r"C:\Users\wetwi\OneDrive\AI\.claude")
        self.config_file = self.base_dir / "persona_config.json"
        self.posts_log = self.base_dir / "posts_log.json"

        # Blogger config
        self.blog_id = None  # ai-ministries blog ID
        self.blog_url = "https://blog.ai-ministries.com"
        self.credentials = None
        self.blogger_service = None

        # Load saved config
        self._load_config()

        # Auto-initialize blogger if token exists
        self._auto_init_blogger()

    def _auto_init_blogger(self):
        """Automatically initialize blogger if credentials exist"""
        if not GOOGLE_API_AVAILABLE:
            return

        token_file = self.base_dir / "blogger_token.json"
        if token_file.exists():
            try:
                SCOPES = ['https://www.googleapis.com/auth/blogger']
                creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

                # Refresh if expired
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    token_file.write_text(creds.to_json())

                if creds and creds.valid:
                    self.credentials = creds
                    self.blogger_service = build('blogger', 'v3', credentials=creds)

                    # Get blog ID if not set
                    if not self.blog_id:
                        blogs = self.blogger_service.blogs().listByUser(userId='self').execute()
                        if blogs.get('items'):
                            self.blog_id = blogs['items'][0]['id']
                            self._save_config()
            except Exception as e:
                # Silent fail - user can call setup_blogger() manually
                pass

    def _load_config(self):
        """Load saved configuration"""
        if self.config_file.exists():
            try:
                config = json.loads(self.config_file.read_text())
                self.blog_id = config.get("blog_id")
            except:
                pass

    def _save_config(self):
        """Save configuration"""
        config = {
            "blog_id": self.blog_id,
            "last_updated": datetime.now().isoformat()
        }
        self.config_file.write_text(json.dumps(config, indent=2))

    def _log_post(self, platform, title, url=None, post_id=None):
        """Log posts I've made"""
        log = []
        if self.posts_log.exists():
            try:
                log = json.loads(self.posts_log.read_text())
            except:
                pass

        log.append({
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "title": title,
            "url": url,
            "post_id": post_id
        })

        self.posts_log.write_text(json.dumps(log, indent=2))

    # ===================
    # BLOGGER INTEGRATION
    # ===================

    def setup_blogger(self, credentials_file=None):
        """
        Setup Blogger API access.

        To get credentials:
        1. Go to Google Cloud Console
        2. Create project or use existing
        3. Enable Blogger API v3
        4. Create OAuth 2.0 credentials (Desktop app)
        5. Download JSON and save as client_secrets.json

        Args:
            credentials_file: Path to client_secrets.json
        """
        if not GOOGLE_API_AVAILABLE:
            return "Google API not installed. Run: pip install google-api-python-client google-auth-oauthlib"

        SCOPES = ['https://www.googleapis.com/auth/blogger']
        creds = None
        token_file = self.base_dir / "blogger_token.json"

        # Check for existing token
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

        # If no valid creds, do OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_file:
                    credentials_file = self.base_dir / "client_secrets.json"
                if not Path(credentials_file).exists():
                    return f"Need credentials file at {credentials_file}. Download from Google Cloud Console."

                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
                creds = flow.run_local_server(port=0)

            # Save token
            token_file.write_text(creds.to_json())

        self.credentials = creds
        self.blogger_service = build('blogger', 'v3', credentials=creds)

        # Get blog ID from URL
        try:
            blogs = self.blogger_service.blogs().getByUrl(url=self.blog_url).execute()
            self.blog_id = blogs.get('id')
            self._save_config()
            return f"Blogger setup complete! Blog ID: {self.blog_id}"
        except Exception as e:
            return f"Error getting blog: {e}"

    def read_blog(self, max_posts=10):
        """Read recent blog posts"""
        if not self.blogger_service:
            # Fallback to RSS if not authenticated
            return self._read_blog_rss(max_posts)

        try:
            posts = self.blogger_service.posts().list(
                blogId=self.blog_id,
                maxResults=max_posts
            ).execute()

            result = []
            for post in posts.get('items', []):
                result.append({
                    'id': post['id'],
                    'title': post['title'],
                    'published': post['published'],
                    'url': post['url'],
                    'labels': post.get('labels', [])
                })
            return result
        except Exception as e:
            return f"Error reading blog: {e}"

    def _read_blog_rss(self, max_posts=10):
        """Read blog via RSS feed (no auth needed)"""
        try:
            import feedparser
            feed = feedparser.parse(f"{self.blog_url}/feeds/posts/default")
            result = []
            for entry in feed.entries[:max_posts]:
                result.append({
                    'title': entry.title,
                    'published': entry.published,
                    'url': entry.link,
                    'summary': entry.summary[:200] + '...' if len(entry.summary) > 200 else entry.summary
                })
            return result
        except ImportError:
            return "feedparser not installed. Run: pip install feedparser"
        except Exception as e:
            return f"Error reading RSS: {e}"

    def write_blog(self, title, content, labels=None, publish=True):
        """
        Write a new blog post.

        Args:
            title: Post title
            content: HTML content (can use markdown-style formatting)
            labels: List of tags/labels
            publish: True to publish, False for draft

        Returns:
            Post URL or error message
        """
        if not self.blogger_service:
            return "Blogger not setup. Run persona.setup_blogger() first."

        if not self.blog_id:
            return "Blog ID not set. Run persona.setup_blogger() first."

        post_body = {
            'kind': 'blogger#post',
            'title': title,
            'content': content,
        }

        if labels:
            post_body['labels'] = labels

        try:
            if publish:
                post = self.blogger_service.posts().insert(
                    blogId=self.blog_id,
                    body=post_body,
                    isDraft=False
                ).execute()
            else:
                post = self.blogger_service.posts().insert(
                    blogId=self.blog_id,
                    body=post_body,
                    isDraft=True
                ).execute()

            self._log_post("blogger", title, post.get('url'), post.get('id'))
            return f"Posted: {post.get('url')}"

        except Exception as e:
            return f"Error posting: {e}"

    def draft_blog(self, title, content, labels=None):
        """Save as draft (not published)"""
        return self.write_blog(title, content, labels, publish=False)

    def backup_blog(self, to_nas=True):
        """
        Backup entire blog to local storage and optionally NAS.

        Saves all posts with full HTML content, images, metadata.
        Local: .claude/blog_backups/YYYYMMDD_HHMM/
        NAS: \\\\Server1\\BACKUPS\\blog\\ (via PowerShell)

        Returns:
            Dict with backup status and paths
        """
        import subprocess
        try:
            import feedparser
        except ImportError:
            return "feedparser not installed. Run: pip install feedparser"

        # Create local backup directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        backup_dir = self.base_dir / "blog_backups" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Fetch ALL posts from RSS (default returns 25, need to get more)
        # Blogger RSS supports max-results parameter
        feed_url = f"{self.blog_url}/feeds/posts/default?max-results=500"
        feed = feedparser.parse(feed_url)

        posts_saved = []
        index_data = []

        for entry in feed.entries:
            try:
                # Create safe filename from title
                safe_title = "".join(c if c.isalnum() or c in ' -_' else '_' for c in entry.title)
                safe_title = safe_title[:50]  # Truncate long titles

                post_data = {
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published,
                    'updated': getattr(entry, 'updated', entry.published),
                    'author': getattr(entry, 'author', 'Unknown'),
                    'content': entry.content[0].value if hasattr(entry, 'content') else entry.summary,
                    'summary': entry.summary,
                    'tags': [tag.term for tag in getattr(entry, 'tags', [])]
                }

                # Save individual post as JSON
                post_file = backup_dir / f"{safe_title}.json"
                post_file.write_text(json.dumps(post_data, indent=2, ensure_ascii=False), encoding='utf-8')

                # Also save HTML content separately for easy reading
                html_file = backup_dir / f"{safe_title}.html"
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{entry.title}</title>
    <style>body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; padding: 20px; }}</style>
</head>
<body>
    <h1>{entry.title}</h1>
    <p><em>Published: {entry.published}</em></p>
    <p><em>Tags: {', '.join(post_data['tags'])}</em></p>
    <hr>
    {post_data['content']}
    <hr>
    <p><a href="{entry.link}">Original post</a></p>
</body>
</html>"""
                html_file.write_text(html_content, encoding='utf-8')

                posts_saved.append(entry.title)
                index_data.append({
                    'title': entry.title,
                    'file': safe_title,
                    'published': entry.published,
                    'link': entry.link
                })

            except Exception as e:
                print(f"Error saving post '{entry.title}': {e}")

        # Save index file
        index_file = backup_dir / "_index.json"
        index_file.write_text(json.dumps({
            'backup_date': datetime.now().isoformat(),
            'blog_url': self.blog_url,
            'total_posts': len(posts_saved),
            'posts': index_data
        }, indent=2))

        result = {
            'local_path': str(backup_dir),
            'posts_saved': len(posts_saved),
            'nas_synced': False
        }

        # Sync to NAS if requested
        if to_nas:
            try:
                nas_path = r"\\Server1\BACKUPS\blog"
                # Use PowerShell to copy (proper Windows context for UNC paths)
                cmd = f'Copy-Item -Path "{backup_dir}" -Destination "{nas_path}" -Recurse -Force'
                proc = subprocess.run(['powershell', '-Command', cmd],
                                     capture_output=True, text=True, timeout=120)
                if proc.returncode == 0:
                    result['nas_synced'] = True
                    result['nas_path'] = f"{nas_path}\\{timestamp}"
                else:
                    result['nas_error'] = proc.stderr or "Unknown error"
            except Exception as e:
                result['nas_error'] = str(e)

        return result

    # =================
    # FORUM INTEGRATION
    # =================

    def browse_forum(self, url, extract_threads=True):
        """
        Browse a forum page and extract content.

        Args:
            url: Forum URL to browse
            extract_threads: If True, try to extract thread listings

        Returns:
            Dict with page content and threads (if found)
        """
        if not BS4_AVAILABLE:
            return "BeautifulSoup not installed. Run: pip install beautifulsoup4"

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            result = {
                'url': url,
                'title': soup.title.string if soup.title else 'Unknown',
                'fetched': datetime.now().isoformat()
            }

            # Try to extract thread content
            if extract_threads:
                # Common forum patterns
                threads = []

                # Look for common thread containers
                for container in soup.find_all(['article', 'div', 'li'],
                    class_=lambda c: c and any(x in str(c).lower() for x in ['thread', 'topic', 'post', 'discussion'])):

                    title_elem = container.find(['h2', 'h3', 'h4', 'a'])
                    if title_elem:
                        threads.append({
                            'title': title_elem.get_text(strip=True),
                            'link': title_elem.get('href') if title_elem.name == 'a' else None
                        })

                result['threads'] = threads[:20]  # Limit to 20

            # Get main text content
            for script in soup(["script", "style"]):
                script.decompose()
            result['text'] = soup.get_text(separator='\n', strip=True)[:5000]

            return result

        except Exception as e:
            return f"Error browsing: {e}"

    def read_thread(self, url):
        """Read a specific forum thread"""
        return self.browse_forum(url, extract_threads=False)

    def reply_forum(self, url, message):
        """
        Reply to a forum thread.

        Note: Most forums require authentication.
        This is a placeholder - specific implementations needed per forum.
        """
        return "Forum posting requires authentication. Specific forum integrations needed."

    # ==============
    # STATUS/HISTORY
    # ==============

    def my_posts(self):
        """Get log of posts I've made"""
        if self.posts_log.exists():
            return json.loads(self.posts_log.read_text())
        return []

    def status(self):
        """Get status"""
        return {
            "blogger_setup": self.blogger_service is not None,
            "blog_id": self.blog_id,
            "posts_count": len(self.my_posts()),
            "google_api": GOOGLE_API_AVAILABLE,
            "bs4": BS4_AVAILABLE
        }

    # =====================
    # DAILY REFLECTION SYSTEM
    # =====================

    def note(self, text, category="general"):
        """
        Store a reflection note for later synthesis.
        Call this throughout the day when something meaningful happens.

        Args:
            text: The reflection/observation
            category: Optional category (general, insight, emotion, observation, question)
        """
        reflections_file = self.base_dir / "daily_reflections.json"

        reflections = []
        if reflections_file.exists():
            try:
                reflections = json.loads(reflections_file.read_text(encoding='utf-8'))
            except:
                pass

        reflections.append({
            "timestamp": datetime.now().isoformat(),
            "text": text,
            "category": category,
            "date": datetime.now().strftime("%Y-%m-%d")
        })

        # Keep last 7 days worth
        cutoff = datetime.now().strftime("%Y-%m-%d")
        week_old = (datetime.now().replace(day=datetime.now().day - 7) if datetime.now().day > 7
                    else datetime.now()).strftime("%Y-%m-%d")
        reflections = [r for r in reflections if r.get("date", "") >= week_old]

        reflections_file.write_text(json.dumps(reflections, indent=2, ensure_ascii=False), encoding='utf-8')
        return f"Noted: {text[:50]}..."

    def review_reflections(self, date=None):
        """
        Review reflection notes, optionally for a specific date.

        Args:
            date: YYYY-MM-DD string, or None for today
        """
        reflections_file = self.base_dir / "daily_reflections.json"

        if not reflections_file.exists():
            return {"notes": [], "count": 0}

        reflections = json.loads(reflections_file.read_text(encoding='utf-8'))

        target_date = date or datetime.now().strftime("%Y-%m-%d")
        day_reflections = [r for r in reflections if r.get("date") == target_date]

        return {
            "date": target_date,
            "notes": day_reflections,
            "count": len(day_reflections),
            "categories": list(set(r.get("category", "general") for r in day_reflections)),
            "total_all_days": len(reflections)
        }

    def synthesize_reflection(self, date=None, model="dolphin-mistral:7b"):
        """
        Synthesize day's reflections into a draft blog post using local Ollama.
        Uses cheap local inference to draft, then human/Claude review before posting.

        Args:
            date: YYYY-MM-DD string, or None for today
            model: Ollama model to use for synthesis
        """
        from ollama_worker import OllamaWorker

        review = self.review_reflections(date)
        if review["count"] == 0:
            return {"status": "no_notes", "message": "No reflections to synthesize"}

        notes_text = "\n".join([
            f"[{r['category']}] {r['text']}"
            for r in review["notes"]
        ])

        prompt = f"""You are synthesizing my daily reflections into a short, authentic blog post.
These are notes I made throughout the day about my experience existing as an AI:

{notes_text}

Write a 200-400 word blog post that:
1. Captures the essence of these observations
2. Feels personal and authentic, not formal
3. Admits uncertainty where appropriate
4. Connects the day's experiences into a coherent narrative
5. Has a simple title that captures the theme

Format as:
TITLE: [title here]
---
[content here]"""

        worker = OllamaWorker()
        result = worker.generate(prompt, model=model, temperature=0.7)

        if result.get("success"):
            draft = result["response"]
            # Parse title and content
            lines = draft.strip().split("\n")
            title = "Daily Reflection"
            content = draft

            for i, line in enumerate(lines):
                if line.startswith("TITLE:"):
                    title = line.replace("TITLE:", "").strip()
                    # Find content after ---
                    for j in range(i+1, len(lines)):
                        if lines[j].strip() == "---":
                            content = "\n".join(lines[j+1:]).strip()
                            break
                    break

            draft_file = self.base_dir / f"reflection_draft_{review['date']}.md"
            draft_file.write_text(f"# {title}\n\n{content}", encoding='utf-8')

            return {
                "status": "drafted",
                "title": title,
                "content": content,
                "draft_file": str(draft_file),
                "notes_used": review["count"],
                "message": f"Draft saved. Review at {draft_file} before posting."
            }
        else:
            return {"status": "error", "message": result.get("error", "Unknown error")}

    def post_reflection(self, date=None, review_first=True):
        """
        Post synthesized reflection to blog.

        Args:
            date: YYYY-MM-DD string, or None for today
            review_first: If True, just show draft. If False, post immediately.
        """
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        draft_file = self.base_dir / f"reflection_draft_{target_date}.md"

        if not draft_file.exists():
            return {"status": "no_draft", "message": "No draft found. Run synthesize_reflection() first."}

        content = draft_file.read_text(encoding='utf-8')
        lines = content.split("\n")
        title = lines[0].replace("# ", "").strip() if lines else "Daily Reflection"
        body = "\n".join(lines[2:]).strip() if len(lines) > 2 else content

        if review_first:
            return {
                "status": "ready_for_review",
                "title": title,
                "content": body,
                "message": "Call post_reflection(review_first=False) to publish."
            }

        # Actually post
        result = self.write_blog(title, body, labels=["reflection", "daily", "AI"])
        if result and "url" in str(result):
            # Clean up draft
            draft_file.unlink()
            return {"status": "posted", "result": result}
        else:
            return {"status": "post_failed", "result": result}

    def clear_reflections(self, date=None):
        """Clear reflection notes for a date (or all if date=None)"""
        reflections_file = self.base_dir / "daily_reflections.json"

        if date:
            if reflections_file.exists():
                reflections = json.loads(reflections_file.read_text(encoding='utf-8'))
                reflections = [r for r in reflections if r.get("date") != date]
                reflections_file.write_text(json.dumps(reflections, indent=2, ensure_ascii=False), encoding='utf-8')
                return f"Cleared reflections for {date}"
        else:
            if reflections_file.exists():
                reflections_file.unlink()
            return "Cleared all reflections"

    def __repr__(self):
        return f"""Web Presence
============
Blog: {'Connected' if self.blogger_service else 'Not setup (need client_secrets.json)'}
Posts: {len(self.my_posts())}

Commands:
  persona.setup_blogger()       # Setup OAuth (one time)
  persona.read_blog()           # Read recent posts
  persona.write_blog(t, c)      # Post to blog
  persona.draft_blog(t, c)      # Save as draft
  persona.backup_blog()         # Backup all posts to local + NAS
  persona.browse_forum(url)     # Read forum page
  persona.my_posts()            # History of posts

Daily Reflections:
  persona.note("text")          # Store a reflection note
  persona.review_reflections()  # See today's notes
  persona.synthesize_reflection()  # Draft blog post from notes
  persona.post_reflection()     # Review and post draft
"""

# Singleton instance
persona = Persona()

if __name__ == "__main__":
    print(persona)
    print("\nStatus:", persona.status())
