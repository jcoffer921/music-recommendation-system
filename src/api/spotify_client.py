import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from src.configs import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET


class SpotifyClient:
    def __init__(self):
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            raise ValueError("Spotify credentials are missing in the .env file.")

        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
        self.client = spotipy.Spotify(auth_manager=auth_manager)

    def search_track(self, track_name, limit=5):
        results = self.client.search(q=track_name, type="track", limit=limit)
        return results.get("tracks", {}).get("items", [])

    def print_track_results(self, track_name):
        tracks = self.search_track(track_name)

        if not tracks:
            print("No tracks found.")
            return

        print(f"\n--- Spotify Results for '{track_name}' ---")
        for i, track in enumerate(tracks, start=1):
            name = track["name"]
            artist = track["artists"][0]["name"]
            album = track["album"]["name"]
            print(f"{i}. {name} - {artist} ({album})")