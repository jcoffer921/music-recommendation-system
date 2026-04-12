"""Spotify service helpers for building safe search queries and fetching tracks."""

from __future__ import annotations

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials

from src.configs import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET


def build_spotify_query(normalized_data):
    """Build a small, safe Spotify query using only artist and genre signals."""
    query_parts = []

    artist = normalized_data.get("artist", "")
    if artist:
        query_parts.append(artist)

    genres = normalized_data.get("genre", [])
    if genres:
        query_parts.append(genres[0])

    return " ".join(part for part in query_parts if part).strip()


class SpotifyService:
    """Wrap Spotify API access so app routes do not talk to Spotipy directly."""

    def __init__(self):
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            raise ValueError("Spotify credentials are missing in the .env file.")

        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        )
        self.client = spotipy.Spotify(auth_manager=auth_manager)

    def search_tracks(self, query, limit=20):
        """Search Spotify tracks using a cleaned query string."""
        cleaned_query = " ".join(str(query).split()).strip()
        if not cleaned_query:
            return []

        try:
            safe_limit = int(limit)
        except (TypeError, ValueError):
            safe_limit = 20

        safe_limit = max(1, min(safe_limit, 50))

        # Some Spotify app modes reject larger limits unexpectedly.
        # Retry with smaller values instead of failing the whole request.
        attempted_limits = []
        fallback_limits = [safe_limit, 10, 5, 1]

        for current_limit in fallback_limits:
            if current_limit in attempted_limits:
                continue

            attempted_limits.append(current_limit)

            try:
                results = self.client.search(
                    q=cleaned_query,
                    type="track",
                    limit=current_limit,
                    market="US",
                )
                return results.get("tracks", {}).get("items", [])
            except SpotifyException as exc:
                print(f"Spotify track search failed with limit={current_limit}: {exc}")

        return []

    def get_audio_features(self, track_ids):
        """Fetch Spotify audio features when available, otherwise return blanks."""
        if not track_ids:
            return []

        try:
            audio_features = self.client.audio_features(track_ids)
            return [features or {} for features in audio_features]
        except SpotifyException as exc:
            print(f"Spotify audio-features unavailable: {exc}")
            return [{} for _ in track_ids]
