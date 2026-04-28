"""Spotify service helpers for building safe search queries and fetching tracks."""

# Spotify search and audio feature usage follows Spotify Web API documentation
# Reference: Spotify Developer site Search and Audio Features guides

# Ai was used to help identify and filter out non-song results that can appear in 
# Spotify search, especially when the user prompt includes radio/podcast-style language

from __future__ import annotations

import re

from src.api.spotify_client import SpotifyClient


# These terms describe media containers, not songs Removing them keeps search
# focused on tracks even when the AI interview mentions radio-style language
NON_MUSIC_SEARCH_TERMS = {
    "broadcast",
    "channel",
    "dj set",
    "episode",
    "fm",
    "playlist",
    "playlists",
    "podcast",
    "radio",
    "show",
    "station",
    "stations",
}

NON_SONG_RESULT_PATTERNS = [
    r"\bradio\s+station\b",
    r"\bstation\s+id\b",
    r"\bplaylist\b",
    r"\bpodcast\b",
    r"\bepisode\b",
    r"\btalk\s+show\b",
    r"\bnews\b",
    r"\binterview\b",
]

NON_MUSIC_AUDIO_RESULT_PATTERNS = [
    r"\bambient\s+sounds?\b",
    r"\bbinaural\s+beats?\b",
    r"\bbrown\s+noise\b",
    r"\bcalming\s+sounds?\b",
    r"\bdeep\s+sleep\s+sounds?\b",
    r"\bforest\s+sounds?\b",
    r"\bnature\s+sounds?\b",
    r"\bocean\s+(sounds?|waves?)\b",
    r"\brain\s+sounds?\b",
    r"\brelaxing\s+sounds?\b",
    r"\briver\s+sounds?\b",
    r"\bsleep\s+sounds?\b",
    r"\bsound\s+effects?\b",
    r"\bthunderstorm\s+sounds?\b",
    r"\bwater\s+sounds?\b",
    r"\bwhite\s+noise\b",
    r"\bwaves?\s+sounds?\b",
]

LOFI_RESULT_PATTERNS = [
    r"\blo[\s-]?fi\s+beats?\b",
    r"\blo[\s-]?fi\s+hip[\s-]?hop\b",
    r"\bbeats?\s+to\s+(relax|study|sleep|chill)\b",
]


def _append_unique(query_parts, seen_parts, value):
    """Append a normalized query part once, preserving user-readable casing."""
    cleaned = " ".join(str(value).split()).strip()
    if not cleaned:
        return

    key = cleaned.lower()
    if key in seen_parts:
        return

    query_parts.append(cleaned)
    seen_parts.add(key)


def _join_query_parts(*parts):
    """Build a deduped Spotify query from nested strings and lists."""
    seen_parts = set()
    query_parts = []

    for part in parts:
        if isinstance(part, list):
            for item in part:
                _append_unique(query_parts, seen_parts, item)
        else:
            _append_unique(query_parts, seen_parts, part)

    return " ".join(query_parts).strip()


def _remove_non_music_search_terms(value):
    """Remove radio/podcast wording that can pull Spotify search away from songs."""
    cleaned = " ".join(str(value or "").lower().split())
    if not cleaned:
        return ""

    for term in sorted(NON_MUSIC_SEARCH_TERMS, key=len, reverse=True):
        cleaned = re.sub(rf"\b{re.escape(term)}\b", " ", cleaned)

    return " ".join(cleaned.split()).strip()


def _explicitly_requests_lofi(*values):
    """Return True only when the user directly asks for lo-fi."""
    for value in values:
        if isinstance(value, list):
            if _explicitly_requests_lofi(*value):
                return True
            continue

        text = " ".join(str(value or "").lower().split())
        if re.search(r"\blo[\s-]?fi\b|\blofi\b", text):
            return True

    return False


def _extract_searchable_descriptors(*values):
    """Convert free-form vibe phrases into safe Spotify search descriptors."""
    allow_lofi = _explicitly_requests_lofi(*values)
    # Phrase mappings keep common activities searchable without sending full prose
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
        "focus": ["focus"],
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
            cleaned = _remove_non_music_search_terms(item)
            if not cleaned:
                continue

            mapped_terms = []
            for phrase, replacements in phrase_map.items():
                if phrase in cleaned:
                    # Replace natural phrases with terms Spotify search understands well
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
                if not allow_lofi and re.search(r"\blo[\s-]?fi\b|\blofi\b", normalized):
                    continue
                if not normalized or normalized in seen:
                    continue
                descriptors.append(normalized)
                seen.add(normalized)

    return descriptors


def _looks_like_non_song_result(track, allow_lofi=False):
    """Reject obvious station/show/podcast tracks while preserving normal songs."""
    name = str(track.get("name", "") or "").lower()
    album_name = str((track.get("album") or {}).get("name", "") or "").lower()
    artist_names = " ".join(
        str(artist.get("name", "") or "").lower()
        for artist in track.get("artists", [])
        if isinstance(artist, dict)
    )
    haystack = " ".join([name, album_name, artist_names])

    if not artist_names.strip():
        return True

    # Avoid filtering the band Radiohead just because their name contains "radio"
    if "radiohead" in haystack:
        return False

    if any(re.search(pattern, haystack) for pattern in NON_SONG_RESULT_PATTERNS):
        return True

    if any(re.search(pattern, haystack) for pattern in NON_MUSIC_AUDIO_RESULT_PATTERNS):
        return True

    if not allow_lofi and any(re.search(pattern, haystack) for pattern in LOFI_RESULT_PATTERNS):
        return True

    return False


def build_spotify_queries(normalized_data):
    """Build progressively broader Spotify queries so recommendations are not artist-locked."""
    # This is the structured recommender query builder: it uses form fields directly
    artist = normalized_data.get("artist", "")
    genres = normalized_data.get("genre", [])
    primary_genre = genres[0] if genres else ""
    mood_terms = normalized_data.get("mood", [])
    primary_mood = mood_terms[0] if mood_terms else ""
    vibe_terms = normalized_data.get("vibe_terms", [])
    primary_vibe = vibe_terms[0] if vibe_terms else normalized_data.get("vibe", "")
    intent_terms = normalized_data.get("intent_terms", [])
    natural_language_request = normalized_data.get("natural_language_request", "")

    # Start constrained, then broaden if Spotify returns too few candidates
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
    # AI mode searches using sanitized intent tags instead of the original prompt
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

    # AI queries use sanitized tags from Ollama rather than the raw chat transcript
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
    # The first query is the most specific one and is useful for debugging/display
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

    def search_tracks_with_features(
        self,
        query,
        limit=20,
        fallback_queries=None,
        max_tracks_per_artist=2,
        allow_lofi=False,
    ):
        """Search tracks and return aligned audio features for ranking."""
        # Fallback queries let the app recover when a precise search has sparse results
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
            # Each query contributes a few unique tracks until the candidate pool is full
            search_results = self.search_tracks(search_query, limit=per_query_limit)

            for track in search_results:
                # Spotify search type=track can still surface station-like audio assets
                if _looks_like_non_song_result(
                    track,
                    allow_lofi=allow_lofi,
                ):
                    continue

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
                    # Cap each artist before ranking so the pool is not dominated early
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
