"""Recommendation scoring helpers for ranking Spotify search results."""

from __future__ import annotations


def build_track_signals(track, audio_features=None):
    """Convert Spotify metadata and optional audio features into simple score signals."""
    audio_features = audio_features or {}

    signal_words = []
    artist_names = [artist.get("name", "") for artist in track.get("artists", [])]
    popularity = track.get("popularity", 0)

    if popularity >= 70:
        signal_words.extend(["popular", "mainstream"])

    energy_value = audio_features.get("energy")
    valence_value = audio_features.get("valence")
    danceability = audio_features.get("danceability")
    acousticness = audio_features.get("acousticness")

    if isinstance(energy_value, (int, float)):
        if energy_value >= 0.7:
            signal_words.extend(["energetic", "hype", "party"])
        elif energy_value <= 0.4:
            signal_words.extend(["calm", "chill", "focused"])

    if isinstance(valence_value, (int, float)):
        if valence_value >= 0.65:
            signal_words.extend(["happy", "bright", "romantic"])
        elif valence_value <= 0.35:
            signal_words.extend(["sad", "moody"])

    if isinstance(danceability, (int, float)) and danceability >= 0.7:
        signal_words.extend(["dance", "groovy"])

    if isinstance(acousticness, (int, float)) and acousticness >= 0.6:
        signal_words.extend(["soft", "acoustic"])

    return {
        "artist_names": artist_names,
        "popularity": popularity,
        "signal_words": {word.lower() for word in signal_words},
    }


def score_track(track, preferences, audio_features=None):
    """Score a single track using user preferences that should not be in the search query."""
    signals = build_track_signals(track, audio_features=audio_features)
    score = 0

    preferred_artist = preferences.get("artist", "").lower()
    if preferred_artist and any(preferred_artist in artist.lower() for artist in signals["artist_names"]):
        score += 4

    for mood in preferences.get("mood", []):
        if mood in signals["signal_words"]:
            score += 2

    vibe = preferences.get("vibe", "")
    if vibe and vibe in signals["signal_words"]:
        score += 2

    # A small popularity bump helps stable recommendations when signals are limited.
    score += min(signals["popularity"] / 25, 3)

    return round(score, 2)


def rank_tracks(tracks, preferences, audio_features_list=None, limit=10):
    """Rank Spotify tracks from best to worst match for the current user."""
    if not tracks:
        return []

    audio_features_list = audio_features_list or [{} for _ in tracks]
    scored_tracks = []

    for track, audio_features in zip(tracks, audio_features_list):
        scored_tracks.append(
            {
                **track,
                "match_score": score_track(track, preferences, audio_features=audio_features),
            }
        )

    ranked_tracks = sorted(
        scored_tracks,
        key=lambda track: track.get("match_score", 0),
        reverse=True,
    )

    return ranked_tracks[:limit]
