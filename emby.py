"""
Emby Media Control - Standalone module for any Claude instance to use
Extracted from claude_daemon.py for easy importing

Usage:
    from emby import emby
    emby.search_and_play("chill music")
    emby.now_playing()
    emby.control("Pause")
    emby.list_playlists()
"""
import os
import requests

EMBY_SERVER = "192.168.4.101"
EMBY_PORT = "8096"
EMBY_API_KEY = os.getenv('EMBY_API_BOT_KEY')

class EmbyControl:
    """Control Emby media server - play, pause, search, etc."""

    def __init__(self):
        self.base_url = f"http://{EMBY_SERVER}:{EMBY_PORT}/emby"
        self.api_key = EMBY_API_KEY
        self.headers = {'X-Emby-Token': self.api_key} if self.api_key else {}

    def get_sessions(self):
        """Get active Emby sessions"""
        try:
            response = requests.get(f"{self.base_url}/../Sessions", headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"EMBY: Error getting sessions: {e}")
        return []

    def get_controllable_session(self):
        """Find a session that supports remote control"""
        sessions = self.get_sessions()
        for session in sessions:
            if session.get('SupportsRemoteControl', False):
                return session['Id'], session.get('DeviceName', 'Unknown')
        return None, None

    def get_user_id(self, prefer_user='tim'):
        """Get user ID for API calls. Prefers Tim by default for playlists."""
        try:
            user_response = requests.get(f"{self.base_url}/Users", headers=self.headers, timeout=10)
            if user_response.status_code != 200:
                return None
            users = user_response.json()
            # Prefer specified user (Tim has the playlists)
            for user in users:
                if user.get('Name', '').lower() == prefer_user.lower():
                    return user['Id']
            # Fallback to discordbot, then first user
            for user in users:
                if user.get('Name', '').lower() == 'discordbot':
                    return user['Id']
            return users[0]['Id'] if users else None
        except:
            return None

    def search(self, query, media_type=None, limit=10):
        """Search Emby library"""
        user_id = self.get_user_id()
        if not user_id:
            return []
        try:
            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'SearchTerm': query,
                'Recursive': 'true',
                'Limit': limit,
                'Fields': 'PrimaryImageAspectRatio,Overview',
                'api_key': self.api_key
            }
            if media_type:
                params['IncludeItemTypes'] = media_type
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get('Items', [])
        except Exception as e:
            print(f"EMBY: Search error: {e}")
        return []

    def play(self, item_id):
        """Play an item by ID"""
        session_id, device = self.get_controllable_session()
        if not session_id:
            return False, "No controllable Emby session found"
        try:
            url = f"{self.base_url}/../Sessions/{session_id}/Playing"
            data = {'ItemIds': item_id, 'PlayCommand': 'PlayNow'}
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            if response.status_code == 204:
                return True, f"Playing on {device}"
            return False, f"Failed: HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)

    def control(self, command):
        """Control playback: Pause, Unpause, Stop, NextTrack, PreviousTrack"""
        session_id, device = self.get_controllable_session()
        if not session_id:
            return False, "No controllable session"
        try:
            url = f"{self.base_url}/../Sessions/{session_id}/Playing/{command}"
            response = requests.post(url, headers=self.headers, timeout=10)
            return response.status_code == 204, device
        except Exception as e:
            return False, str(e)

    def now_playing(self):
        """Get what's currently playing"""
        sessions = self.get_sessions()
        for session in sessions:
            if session.get('NowPlayingItem'):
                item = session['NowPlayingItem']
                name = item.get('Name', 'Unknown')
                item_type = item.get('Type', '')
                artist = item.get('Artists', [''])[0] if item.get('Artists') else ''
                is_paused = session.get('PlayState', {}).get('IsPaused', False)
                status = "Paused" if is_paused else "Playing"
                if artist:
                    return f"{status}: {artist} - {name}"
                return f"{status}: {name} ({item_type})"
        return "Nothing playing"

    def search_and_play(self, query, media_type="Audio"):
        """Search and play first result"""
        results = self.search(query, media_type)
        if not results:
            return False, f"No results for '{query}'"
        item = results[0]
        item_id = item['Id']
        name = item.get('Name', 'Unknown')
        artist = item.get('Artists', [''])[0] if item.get('Artists') else ''
        success, msg = self.play(item_id)
        if success:
            if artist:
                return True, f"Playing: {artist} - {name}"
            return True, f"Playing: {name}"
        return False, msg

    def list_playlists(self, limit=50):
        """List available playlists"""
        user_id = self.get_user_id()
        if not user_id:
            return []
        try:
            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'Playlist',
                'Recursive': 'true',
                'Limit': limit,
                'SortBy': 'SortName',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{'name': i.get('Name'), 'id': i['Id'], 'song_count': i.get('ChildCount', 0)} for i in items]
        except Exception as e:
            print(f"EMBY: List playlists error: {e}")
        return []

    def play_playlist(self, playlist_id, shuffle=False):
        """Play a playlist by ID"""
        session_id, device = self.get_controllable_session()
        if not session_id:
            return False, "No controllable session"
        try:
            url = f"{self.base_url}/../Sessions/{session_id}/Playing"
            data = {'ItemIds': playlist_id, 'PlayCommand': 'PlayNow'}
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            if response.status_code == 204:
                return True, f"Playing playlist on {device}"
            return False, f"Failed: HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)

    def list_albums(self, limit=50):
        """List available albums"""
        user_id = self.get_user_id()
        if not user_id:
            return []
        try:
            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'MusicAlbum',
                'Recursive': 'true',
                'Limit': limit,
                'SortBy': 'SortName',
                'SortOrder': 'Ascending',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{'name': i.get('Name'), 'artist': i.get('AlbumArtist', ''), 'id': i['Id']} for i in items]
        except Exception as e:
            print(f"EMBY: List albums error: {e}")
        return []

    def list_artists(self, limit=50):
        """List available artists"""
        try:
            url = f"{self.base_url}/Artists"
            params = {
                'Limit': limit,
                'SortBy': 'SortName',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{'name': i.get('Name'), 'id': i['Id']} for i in items]
        except Exception as e:
            print(f"EMBY: List artists error: {e}")
        return []

    # === TV SHOWS ===

    def list_shows(self, limit=50, status=None):
        """List TV shows. status='Continuing' for active shows."""
        user_id = self.get_user_id()
        if not user_id:
            return []
        try:
            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'Series',
                'Recursive': 'true',
                'Limit': limit,
                'SortBy': 'DateCreated',
                'SortOrder': 'Descending',
                'Fields': 'Overview,DateCreated,Status',
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                shows = [{'name': i.get('Name'), 'id': i['Id'],
                         'status': i.get('Status', 'unknown'),
                         'added': i.get('DateCreated', '')[:10]} for i in items]
                if status:
                    shows = [s for s in shows if s['status'] == status]
                return shows
        except Exception as e:
            print(f"EMBY: List shows error: {e}")
        return []

    def recent_episodes(self, limit=20, days=7):
        """Get episodes from the last N days."""
        from datetime import datetime, timedelta
        user_id = self.get_user_id()
        if not user_id:
            return []
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'Episode',
                'Recursive': 'true',
                'Limit': limit,
                'SortBy': 'PremiereDate',
                'SortOrder': 'Descending',
                'Fields': 'PremiereDate,SeriesName',
                'MinPremiereDate': cutoff,
                'api_key': self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                items = response.json().get('Items', [])
                return [{
                    'series': i.get('SeriesName', '?'),
                    'name': i.get('Name', '?'),
                    'season': i.get('ParentIndexNumber'),
                    'episode': i.get('IndexNumber'),
                    'date': i.get('PremiereDate', '')[:10] if i.get('PremiereDate') else None,
                    'id': i['Id']
                } for i in items]
        except Exception as e:
            print(f"EMBY: Recent episodes error: {e}")
        return []

    def new_today(self):
        """Get episodes that premiered today."""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        eps = self.recent_episodes(limit=50, days=1)
        return [e for e in eps if e.get('date') == today]

    def whats_new(self):
        """Human-readable summary of new episodes."""
        eps = self.recent_episodes(days=3)
        if not eps:
            return "No new episodes in the last 3 days"
        lines = []
        for e in eps[:10]:
            s = e.get('season', '?')
            ep = e.get('episode', '?')
            lines.append(f"{e['series']} S{s}E{ep}: {e['name']} [{e['date']}]")
        return "\n".join(lines)


# Global instance - ready to use
emby = EmbyControl()


if __name__ == "__main__":
    # Quick test
    print("Now playing:", emby.now_playing())
    print("\nPlaylists:")
    for p in emby.list_playlists()[:5]:
        print(f"  - {p['name']} ({p['song_count']} tracks)")
