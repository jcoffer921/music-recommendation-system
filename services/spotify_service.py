"""Spotify service helpers for building safe search queries and fetching tracks."""

from __future__ import annotations

from src.api.spotify_client import SpotifyClient


def _append_unique(query_parts, seen_parts, value):
    cleaned = " ".join(str(value).split()).strip()
    if not cleaned:
        return

    key = cleaned.lower()
    if key in seen_parts:
        return

    query_parts.append(cleaned)
    seen_parts.add(key)


def _join_query_parts(*parts):
    seen_parts = set()
    query_parts = []

    for part in parts:
        if isinstance(part, list):
            for item in part:
                _append_unique(query_parts, seen_parts, item)
        else:
            _append_unique(query_parts, seen_parts, part)

    return " ".join(query_parts).strip()


def _extract_searchable_descriptors(*values):
    """Convert free-form vibe phrases into safe Spotify search descriptors."""
    phrase_map = {
        "late night": ["late night", "night"],
        "night drive": ["driving", "late night"],
        "late night drive": ["driving", "late night"],
        "drive": ["driving", "road trip"],
        "driving": ["driving", "road trip"],
        "road trip": ["road trip", "driving"],
        "workout": ["workout", "energetic"],
        "gym": ["workout", "energetic"],
        "study": ["study", "focus"],
        "focus": ["focus", "instrumental"],
        "party": ["party", "dance"],
        "chill": ["chill", "calm"],
    }
    stop_words = {"music", "songs", "song", "recommendations", "tracks", "playlist", "playlists"}
    descriptors = []
    seen = set()

    for value in values:
        if not value:
            continue

        items = value if isinstance(value, list) else [value]
        for item in items:
            cleaned = " ".join(str(item).lower().split()).strip()
            if not cleaned:
                continue

            mapped_terms = []
            for phrase, replacements in phrase_map.items():
                if phrase in cleaned:
                    mapped_terms.extend(replacements)

            if not mapped_terms:
                if len(cleaned.split()) <= 2 and cleaned not in stop_words:
                    mapped_terms.append(cleaned)
                else:
                    mapped_terms.extend(
                        token for token in cleaned.replace("/", " ").split()
                        if token not in stop_words and len(token) > 2
                    )

            for term in mapped_terms:
                normalized = " ".join(term.split()).strip()
                if not normalized or normalized in seen:
                    continue
                descriptors.append(normalized)
                seen.add(normalized)

    return descriptors


def build_spotify_queries(normalized_data):
    """Build progressively broader Spotify queries so recommendations are not artist-locked."""
    artist = normalized_data.get("artist", "")
    genres = normalized_data.get("genre", [])
    primary_genre = genres[0] if genres else ""
    mood_terms = normalized_data.get("mood", [])
    primary_mood = mood_terms[0] if mood_terms else ""
    vibe_terms = normalized_data.get("vibe_terms", [])
    primary_vibe = vibe_terms[0] if vibe_terms else normalized_data.get("vibe", "")
    intent_terms = normalized_data.get("intent_terms", [])
    natural_language_request = normalized_data.get("natural_language_request", "")

    query_candidates = [
        _join_query_parts(
            f'genre:"{primary_genre}"' if primary_genre else "",
            primary_mood,
            primary_vibe,
        ),
        _join_query_parts(
            primary_genre,
            primary_mood,
            primary_vibe,
            artist,
        ),
        _join_query_parts(primary_genre, primary_mood, primary_vibe, *intent_terms[:2]),
        _join_query_parts(primary_genre, primary_mood, primary_vibe),
        _join_query_parts(artist, primary_genre),
        _join_query_parts(artist, natural_language_request[:80]),
        _join_query_parts(artist),
    ]

    queries = []
    seen_queries = set()

    for query in query_candidates:
        key = query.lower()
        if not query or key in seen_queries:
            continue
        queries.append(query)
        seen_queries.add(key)

    return queries


def build_ai_spotify_queries(normalized_data):
    """Build safer Spotify queries for MusicMe AI without using raw prompt text."""
    artist = normalized_data.get("artist", "")
    genres = normalized_data.get("genre", [])
    mood_terms = _extract_searchable_descriptors(normalized_data.get("mood", []))
    vibe_terms = _extract_searchable_descriptors(
        normalized_data.get("vibe_terms", []),
        normalized_data.get("intent_terms", []),
    )
    genre_terms = _extract_searchable_descriptors(genres)

    primary_genre = genre_terms[0] if genre_terms else ""
    primary_mood = mood_terms[0] if mood_terms else ""
    primary_vibe = vibe_terms[0] if vibe_terms else ""

    query_candidates = [
        _join_query_parts(
            f'genre:"{primary_genre}"' if primary_genre else "",
            primary_mood,
            primary_vibe,
        ),
        _join_query_parts(primary_genre, primary_mood, primary_vibe, artist),
        _join_query_parts(primary_genre, *mood_terms[:2], *vibe_terms[:2]),
        _join_query_parts(*genre_terms[:2], *mood_terms[:2], *vibe_terms[:2]),
        _join_query_parts(artist, primary_genre, primary_mood),
        _join_query_parts(artist, *vibe_terms[:2]),
        _join_query_parts(artist),
    ]

    queries = []
    seen_queries = set()

    for query in query_candidates:
        key = query.lower()
        if not query or key in seen_queries:
            continue
        queries.append(query)
        seen_queries.add(key)

    return queries


def build_spotify_query(normalized_data):
    """Return the primary Spotify query shown in API responses."""
    queries = build_spotify_queries(normalized_data)
    return queries[0] if queries else ""


class SpotifyService:
    """Wrap Spotify API access so app routes do not talk to Spotipy directly."""

    def __init__(self):
        self.client = SpotifyClient()

    def search_tracks(self, query, limit=20):
        """Search Spotify tracks using a cleaned query string."""
        return self.client.search_tracks(query, limit=limit, market="US")

    def get_audio_features(self, track_ids):
        """Fetch Spotify audio features when available, otherwise return blanks."""
        return self.client.get_audio_features(track_ids)

    def search_tracks_with_features(self, query, limit=20, fallback_queries=None, max_tracks_per_artist=2):
        """Search tracks and return aligned audio features for ranking."""
        search_queries = [query]
        if fallback_queries:
            for fallback_query in fallback_queries:
                if fallback_query and fallback_query not in search_queries:
                    search_queries.append(fallback_query)

        tracks = []
        seen_track_ids = set()
        artist_counts = {}

        per_query_limit = max(1, min(limit, 10))

        for search_query in search_queries:
            search_results = self.search_tracks(search_query, limit=per_query_limit)

            for track in search_results:
                track_id = track.get("id")
                dedupe_key = track_id or f"{track.get('name','')}::{track.get('spotify_url','')}"
                if dedupe_key in seen_track_ids:
                    continue

                primary_artist = ""
                if track.get("artists"):
                    primary_artist = track["artists"][0].get("name", "").strip().lower()

                if primary_artist:
                    current_count = artist_counts.get(primary_artist, 0)
                    if current_count >= max_tracks_per_artist:
                        continue
                    artist_counts[primary_artist] = current_count + 1

                seen_track_ids.add(dedupe_key)
                tracks.append(track)

                if len(tracks) >= limit:
                    break

            if len(tracks) >= limit:
                break

        track_ids = [track.get("id") for track in tracks]
        audio_features = self.get_audio_features(track_ids)
        return tracks, audio_features
