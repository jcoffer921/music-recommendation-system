"""Helpers for cleaning and normalizing form input before recommendation logic."""

from __future__ import annotations


def normalize_text(value, lowercase=False):
    """Trim whitespace and optionally lowercase a text value."""
    if value is None:
        return ""

    cleaned = " ".join(str(value).strip().split())
    return cleaned.lower() if lowercase else cleaned


def normalize_list(values, lowercase=True):
    """Normalize a list of values or a comma-separated string into unique items."""
    if not values:
        return []

    if isinstance(values, str):
        raw_items = values.split(",")
    else:
        raw_items = values

    normalized_items = []
    seen = set()

    for item in raw_items:
        cleaned = normalize_text(item, lowercase=lowercase)
        if not cleaned or cleaned in seen:
            continue

        normalized_items.append(cleaned)
        seen.add(cleaned)

    return normalized_items


def combine_inputs(selected_values, custom_value, lowercase=True):
    """Combine pill selections with free-text input while removing duplicates."""
    selected_items = normalize_list(selected_values, lowercase=lowercase)
    custom_items = normalize_list(custom_value, lowercase=lowercase)

    combined = []
    seen = set()

    for item in selected_items + custom_items:
        if item in seen:
            continue
        combined.append(item)
        seen.add(item)

    return combined


def normalize_form_data(form_data):
    """Return a clean, structured version of the submitted MusicMe form data."""
    vibe = normalize_text(form_data.get("vibe", ""), lowercase=True)
    normalized = {
        "mood": combine_inputs(
            form_data.get("selected_moods", []),
            form_data.get("custom_mood", ""),
            lowercase=True,
        ),
        "genre": combine_inputs(
            form_data.get("selected_genres", []),
            form_data.get("custom_genre", ""),
            lowercase=True,
        ),
        "artist": normalize_text(form_data.get("artist", ""), lowercase=False),
        "vibe": vibe,
        "vibe_terms": [vibe] if vibe else [],
        "natural_language_request": normalize_text(
            form_data.get("natural_language_request", ""),
            lowercase=False,
        ),
        "intent_terms": [],
        "target_audio_profile": {},
    }

    return normalized


def merge_nlp_intent(normalized_preferences, intent):
    """Merge NLP-extracted intent into the normalized form preferences."""
    merged = dict(normalized_preferences or {})
    intent = intent or {}

    merged["mood"] = combine_inputs(
        merged.get("mood", []),
        intent.get("mood", []),
        lowercase=True,
    )
    merged["genre"] = combine_inputs(
        merged.get("genre", []),
        intent.get("genre", []),
        lowercase=True,
    )

    vibe_terms = combine_inputs(
        [merged.get("vibe", "")] if merged.get("vibe") else [],
        intent.get("vibe", []),
        lowercase=True,
    )
    merged["vibe_terms"] = vibe_terms
    if not merged.get("vibe") and vibe_terms:
        merged["vibe"] = vibe_terms[0]

    if not merged.get("artist") and intent.get("artist"):
        merged["artist"] = normalize_text(intent.get("artist", ""), lowercase=False)

    merged["intent_terms"] = normalize_list(intent.get("intent_terms", []), lowercase=True)
    merged["target_audio_profile"] = {
        "energy": intent.get("energy"),
        "valence": intent.get("valence"),
        "danceability": intent.get("danceability"),
        "acousticness": intent.get("acousticness"),
        "tempo": intent.get("tempo"),
    }
    merged["nlp_interpretation"] = intent
    return merged
