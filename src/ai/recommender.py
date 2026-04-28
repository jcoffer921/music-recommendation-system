from __future__ import annotations

# TF-IDF scorer used as one component of the final recommendation ranking blend
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class MusicRecommender:
    def __init__(self):
        # TF-IDF turns user and track text into comparable vectors
        self.vectorizer = TfidfVectorizer(stop_words="english")

    def _build_user_profile(self, responses: dict) -> str:
        """Flatten interview responses into a single text profile."""
        profile_parts = []

        # Preferences contain strings, lists, and nested audio targets; flatten only
        # values that help compare the user profile against track metadata
        for value in responses.values():
            if isinstance(value, list):
                profile_parts.extend(str(item) for item in value if str(item).strip())
            elif isinstance(value, dict):
                profile_parts.extend(
                    str(item) for item in value.values()
                    if isinstance(item, (str, int, float)) and str(item).strip()
                )
            elif str(value).strip():
                profile_parts.append(str(value))

        return " ".join(profile_parts)

    def _build_track_profile(self, track: dict, audio_features: dict) -> str:
        """
        Convert a Spotify track + its audio features into a text description
        that can be vectorized alongside the user profile.
        """
        parts = []

        # Text metadata anchors similarity to the actual track, album, and artist
        parts.append(track.get("name", ""))
        parts.append(track.get("album", {}).get("name", ""))
        for artist in track.get("artists", []):
            parts.append(artist.get("name", ""))

        popularity = track.get("popularity", 0)
        if popularity >= 75:
            parts.append("popular mainstream")
        elif popularity <= 25:
            parts.append("niche lesser-known")

        if track.get("explicit"):
            parts.append("explicit")

        if audio_features:
            # Convert numeric audio features into plain-language descriptors
            if audio_features.get("energy", 0) > 0.7:
                parts.append("energetic intense")
            elif audio_features.get("energy", 0) < 0.4:
                parts.append("calm relaxed")

            if audio_features.get("valence", 0) > 0.6:
                parts.append("happy upbeat positive")
            elif audio_features.get("valence", 0) < 0.4:
                parts.append("sad melancholic dark")

            if audio_features.get("danceability", 0) > 0.7:
                parts.append("danceable groovy rhythmic")

            if audio_features.get("acousticness", 0) > 0.7:
                parts.append("acoustic mellow unplugged")

            if audio_features.get("instrumentalness", 0) > 0.5:
                parts.append("instrumental no vocals")

            if audio_features.get("tempo", 0) > 140:
                parts.append("fast tempo upbeat")
            elif audio_features.get("tempo", 0) < 80:
                parts.append("slow tempo")

        return " ".join(parts)

    def score_candidates(self, user_profile: dict, tracks: list[dict], audio_features_list: list[dict] | None = None) -> list[float]:
        """Return cosine-similarity scores aligned to the provided candidate tracks."""
        if not tracks:
            return []

        audio_features_list = audio_features_list or [{} for _ in tracks]
        user_profile_text = self._build_user_profile(user_profile)

        if not user_profile_text.strip():
            # Without a user profile, every track gets neutral similarity
            return [0.0 for _ in tracks]

        track_profiles = [
            self._build_track_profile(track, features or {})
            for track, features in zip(tracks, audio_features_list)
        ]

        if not any(profile.strip() for profile in track_profiles):
            # Spotify can return sparse metadata, so keep ranking functional
            return [0.0 for _ in tracks]

        # Fit per request so the vocabulary matches the current user and candidate set
        all_texts = [user_profile_text] + track_profiles
        tfidf_matrix = self.vectorizer.fit_transform(all_texts)

        # Cosine similarity measures how close each track profile is to the user profile
        user_vector = tfidf_matrix[0]
        track_vectors = tfidf_matrix[1:]
        scores = cosine_similarity(user_vector, track_vectors).flatten()
        return [float(score) for score in scores]
