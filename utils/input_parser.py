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
        "vibe": normalize_text(form_data.get("vibe", ""), lowercase=True),
    }

    return normalized
