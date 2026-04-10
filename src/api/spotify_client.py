import spotipy
from spotipy.exceptions import SpotifyException
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

    def search_tracks(self, query, limit=20):
        cleaned_query = " ".join(str(query).split()).strip()
        if not cleaned_query:
            return []

        try:
            safe_limit = int(limit)
        except (TypeError, ValueError):
            safe_limit = 20

        safe_limit = max(1, min(safe_limit, 50))

        try:
            results = self.client.search(
                q=cleaned_query,
                type="track",
                limit=safe_limit,
                market="US",
            )
        except SpotifyException as exc:
            print(f"Spotify track search failed: {exc}")
            fallback_limit = min(safe_limit, 10)
            if fallback_limit == safe_limit:
                return []
            try:
                results = self.client.search(
                    q=cleaned_query,
                    type="track",
                    limit=fallback_limit,
                    market="US",
                )
            except SpotifyException as fallback_exc:
                print(f"Spotify fallback search failed: {fallback_exc}")
                return []

        return results.get("tracks", {}).get("items", [])

    def get_audio_features(self, track_ids):
        if not track_ids:
            return []

        try:
            audio_features = self.client.audio_features(track_ids)
            return [features or {} for features in audio_features]
        except SpotifyException as exc:
            # New/dev-mode Spotify apps can receive 403 for Audio Features.
            # Fall back to metadata-only ranking instead of failing the request.
            print(f"Spotify audio-features unavailable: {exc}")
            return [{} for _ in track_ids]

    def print_track_results(self, track_name):
        tracks = self.search_tracks(track_name)

        if not tracks:
            print("No tracks found.")
            return

        print(f"\n--- Spotify Results for '{track_name}' ---")
        for i, track in enumerate(tracks, start=1):
            name = track["name"]
            artist = track["artists"][0]["name"]
            album = track["album"]["name"]
            print(f"{i}. {name} - {artist} ({album})")
