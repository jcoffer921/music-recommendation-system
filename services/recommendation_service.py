"""Recommendation scoring helpers for ranking Spotify search results."""

# Portions of this ranking logic were developed with AI assistance

from __future__ import annotations

from src.ai.recommender import MusicRecommender


TFIDF_BLEND_WEIGHT = 4.0


def build_track_signals(track, audio_features=None):
    """Convert Spotify metadata and optional audio features into simple score signals."""
    audio_features = audio_features or {}

    # Signals translate numeric Spotify audio features into words that can align
    # with mood, vibe, and AI intent tags
    signal_words = []
    artist_names = [artist.get("name", "") for artist in track.get("artists", [])]
    popularity = track.get("popularity", 0)

    if popularity >= 70:
        signal_words.extend(["popular", "mainstream"])

    energy_value = audio_features.get("energy")
    valence_value = audio_features.get("valence")
    danceability = audio_features.get("danceability")
    acousticness = audio_features.get("acousticness")
    instrumentalness = audio_features.get("instrumentalness")
    tempo = audio_features.get("tempo")

    # Spotify audio features are numeric, so each range is translated into words
    # that can be matched against user moods, vibes, and AI intent terms
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

    if isinstance(instrumentalness, (int, float)) and instrumentalness >= 0.5:
        signal_words.extend(["instrumental", "study", "focus"])

    if isinstance(tempo, (int, float)):
        if tempo >= 130:
            signal_words.extend(["fast", "workout", "driving"])
        elif tempo <= 90:
            signal_words.extend(["slow", "late night", "mellow"])

    return {
        "artist_names": artist_names,
        "popularity": popularity,
        "signal_words": {word.lower() for word in signal_words},
        "has_preview": bool(track.get("preview_url")),
        "audio_features": audio_features,
    }


def score_audio_alignment(target_profile, audio_features):
    """Reward tracks whose audio features align with NLP-inferred targets."""
    if not target_profile or not audio_features:
        return 0

    # Closer audio-feature matches get more credit, but no single field dominates
    weighted_fields = {
        "energy": 2.0,
        "valence": 1.5,
        "danceability": 1.5,
        "acousticness": 1.0,
    }

    score = 0
    for field_name, weight in weighted_fields.items():
        target_value = target_profile.get(field_name)
        actual_value = audio_features.get(field_name)
        if not isinstance(target_value, (int, float)) or not isinstance(actual_value, (int, float)):
            continue

        # A perfect match gets full weight; farther values receive less credit
        distance = abs(float(target_value) - float(actual_value))
        score += max(0, (1 - distance)) * weight

    target_tempo = target_profile.get("tempo")
    actual_tempo = audio_features.get("tempo")
    if isinstance(target_tempo, (int, float)) and isinstance(actual_tempo, (int, float)):
        tempo_distance = abs(float(target_tempo) - float(actual_tempo))
        score += max(0, 1 - (tempo_distance / 80)) * 1.5

    return round(score, 2)


def score_track(track, preferences, audio_features=None):
    """Score a single track using user preferences that should not be in the search query."""
    signals = build_track_signals(track, audio_features=audio_features)
    score = 0

    # Artist matches are useful but intentionally limited so results can still diversify
    preferred_artist = preferences.get("artist", "").lower()
    if preferred_artist and any(preferred_artist in artist.lower() for artist in signals["artist_names"]):
        score += 2

    for mood in preferences.get("mood", []):
        if mood in signals["signal_words"]:
            score += 2

    vibe_terms = preferences.get("vibe_terms", [])
    if not vibe_terms and preferences.get("vibe"):
        # Older/standard payloads may only have a single vibe string
        vibe_terms = [preferences.get("vibe")]

    for vibe in vibe_terms:
        if vibe in signals["signal_words"]:
            score += 1.75

    for intent_term in preferences.get("intent_terms", []):
        if intent_term in signals["signal_words"]:
            score += 1.25

    if signals["has_preview"]:
        score += 1.5

    # A small popularity bump helps stable recommendations when signals are limited
    score += min(signals["popularity"] / 25, 3)
    score += score_audio_alignment(preferences.get("target_audio_profile"), audio_features or {})

    return round(score, 2)


def rank_tracks(tracks, preferences, audio_features_list=None, limit=10, max_tracks_per_artist=2):
    """Rank Spotify tracks from best to worst match for the current user."""
    if not tracks:
        return []

    audio_features_list = audio_features_list or [{} for _ in tracks]
    # Blend handcrafted scoring with text similarity for better behavior on sparse metadata
    tfidf_recommender = MusicRecommender()
    tfidf_scores = tfidf_recommender.score_candidates(
        preferences,
        tracks,
        audio_features_list=audio_features_list,
    )
    scored_tracks = []

    for index, (track, audio_features) in enumerate(zip(tracks, audio_features_list)):
        # The final match score combines direct rule matches with TF-IDF similarity
        heuristic_score = score_track(track, preferences, audio_features=audio_features)
        tfidf_score = tfidf_scores[index] if index < len(tfidf_scores) else 0.0
        blended_score = round(heuristic_score + (tfidf_score * TFIDF_BLEND_WEIGHT), 2)
        scored_tracks.append(
            {
                **track,
                "has_preview": bool(track.get("preview_url")),
                "heuristic_score": heuristic_score,
                "tfidf_score": round(tfidf_score, 4),
                "match_score": blended_score,
            }
        )

    ranked_tracks = sorted(
        scored_tracks,
        key=lambda track: (
            # Playable previews are ranked first, then tracks are ordered by score
            1 if track.get("has_preview") else 0,
            track.get("match_score", 0),
        ),
        reverse=True,
    )

    final_tracks = []
    artist_counts = {}

    # Limit repeated artists in the final list even if Spotify returns many matches
    for track in ranked_tracks:
        primary_artist = ""
        if track.get("artists"):
            primary_artist = track["artists"][0].get("name", "").strip().lower()

        if primary_artist:
            current_count = artist_counts.get(primary_artist, 0)
            if current_count >= max_tracks_per_artist:
                continue
            artist_counts[primary_artist] = current_count + 1

        final_tracks.append(track)
        if len(final_tracks) >= limit:
            break

    return final_tracks
