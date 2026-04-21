from __future__ import annotations

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials

from src.configs import SPOTIFY_ACCESS_TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET


class SpotifyClient:
    """Thin SDK wrapper around Spotipy with app-friendly normalized responses."""

    def __init__(self):
        self.using_access_token = False

        if SPOTIFY_ACCESS_TOKEN:
            self.client = spotipy.Spotify(auth=SPOTIFY_ACCESS_TOKEN)
            self.using_access_token = True
            return

        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            raise ValueError(
                "Spotify credentials are missing. Set SPOTIFY_ACCESS_TOKEN for testing "
                "or SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET for server auth."
            )

        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        )
        self.client = spotipy.Spotify(auth_manager=auth_manager)

    @staticmethod
    def _clean_query(query):
        return " ".join(str(query).split()).strip()

    @staticmethod
    def _coerce_limit(limit, default=20, maximum=50):
        try:
            safe_limit = int(limit)
        except (TypeError, ValueError):
            safe_limit = default

        return max(1, min(safe_limit, maximum))

    @staticmethod
    def _normalize_track(track):
        album = track.get("album") or {}
        images = album.get("images") or []
        primary_image = images[0]["url"] if images else None

        return {
            "id": track.get("id"),
            "name": track.get("name", ""),
            "artists": track.get("artists", []),
            "album": {
                "name": album.get("name", ""),
                "release_date": album.get("release_date", ""),
                "images": images,
            },
            "duration_ms": track.get("duration_ms"),
            "explicit": bool(track.get("explicit")),
            "popularity": track.get("popularity", 0),
            "preview_url": track.get("preview_url"),
            "spotify_url": (track.get("external_urls") or {}).get("spotify"),
            "uri": track.get("uri"),
            "image_url": primary_image,
        }

    @staticmethod
    def _is_invalid_limit_error(exc):
        status_code = getattr(exc, "http_status", None)
        message = str(exc).lower()
        return status_code == 400 and "invalid limit" in message

    @staticmethod
    def _is_invalid_access_token_error(exc):
        status_code = getattr(exc, "http_status", None)
        message = str(exc).lower()
        return status_code == 401 and "invalid access token" in message

    @staticmethod
    def _has_client_credentials():
        return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)

    def _switch_to_client_credentials(self):
        if not self._has_client_credentials():
            return False

        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        )
        self.client = spotipy.Spotify(auth_manager=auth_manager)
        self.using_access_token = False
        return True

    def _execute_track_search(self, query, market="US", limit=None):
        search_kwargs = {
            "q": query,
            "type": "track",
            "market": market,
        }
        if limit is not None:
            search_kwargs["limit"] = limit

        results = self.client.search(**search_kwargs)
        items = results.get("tracks", {}).get("items", [])
        return [self._normalize_track(track) for track in items]

    def search_tracks(self, query, limit=20, market="US"):
        cleaned_query = self._clean_query(query)
        if not cleaned_query:
            return []

        safe_limit = self._coerce_limit(limit)
        attempted_limits = []
        fallback_limits = [safe_limit, 10, 5, 1]

        for current_limit in fallback_limits:
            if current_limit in attempted_limits:
                continue

            attempted_limits.append(current_limit)

            try:
                return self._execute_track_search(
                    cleaned_query,
                    market=market,
                    limit=current_limit,
                )
            except SpotifyException as exc:
                print(f"Spotify track search failed with limit={current_limit}: {exc}")
                if self.using_access_token and self._is_invalid_access_token_error(exc):
                    if self._switch_to_client_credentials():
                        return self.search_tracks(cleaned_query, limit=limit, market=market)
                    raise PermissionError(
                        "Spotify access token is invalid or expired. Refresh SPOTIFY_ACCESS_TOKEN "
                        "or configure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
                    ) from exc
                if self._is_invalid_limit_error(exc):
                    try:
                        return self._execute_track_search(
                            cleaned_query,
                            market=market,
                            limit=None,
                        )
                    except SpotifyException as fallback_exc:
                        print(f"Spotify track search failed without explicit limit: {fallback_exc}")

        return []

    def get_audio_features(self, track_ids):
        if not track_ids:
            return []

        normalized_ids = [track_id for track_id in track_ids if track_id]
        if not normalized_ids:
            return []

        feature_map = {track_id: {} for track_id in normalized_ids}

        try:
            for index in range(0, len(normalized_ids), 100):
                batch_ids = normalized_ids[index:index + 100]
                batch_features = self.client.audio_features(batch_ids) or []

                for track_id, features in zip(batch_ids, batch_features):
                    feature_map[track_id] = features or {}
        except SpotifyException as exc:
            if self.using_access_token and self._is_invalid_access_token_error(exc):
                if self._switch_to_client_credentials():
                    return self.get_audio_features(track_ids)
                raise PermissionError(
                    "Spotify access token is invalid or expired. Refresh SPOTIFY_ACCESS_TOKEN "
                    "or configure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
                ) from exc
            # New/dev-mode Spotify apps can receive 403 for Audio Features.
            # Fall back to metadata-only ranking instead of failing the request.
            print(f"Spotify audio-features unavailable: {exc}")
            return [{} for _ in track_ids]

        return [feature_map.get(track_id, {}) for track_id in track_ids]

    def print_track_results(self, track_name):
        tracks = self.search_tracks(track_name)

        if not tracks:
            print("No tracks found.")
            return

        print(f"\n--- Spotify Results for '{track_name}' ---")
        for i, track in enumerate(tracks, start=1):
            artist = track["artists"][0]["name"] if track.get("artists") else "Unknown Artist"
            album_name = track.get("album", {}).get("name", "Unknown Album")
            print(f"{i}. {track['name']} - {artist} ({album_name})")
