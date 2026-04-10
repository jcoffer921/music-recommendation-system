from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class MusicRecommender:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')

    def _build_user_profile(self, responses: dict) -> str:
        """Flatten interview responses into a single text profile"""
        return " ".join(str(v) for v in responses.values())
    
    def _build_track_profile(self, track: dict, audio_features: dict) -> str:
        """
        Convert a Spotify track + its audio features into a text description
        that can be vectorized alongside user profile
        """
        parts = []

        # add genre/artist hints from track metadata
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

        # translate numeric audio features into descriptive text
        if audio_features:
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

    def recommend(self, user_profile, spotify):
        """
        - build text profile from interview responses
        - search spotify for candidate tracks
        - fetch audio features for each candidate
        - vectorize everything with TF-IDF
        - rank candidates by cosine similarity to user profile
        - return top tracks
        """

        # user profile as text
        user_profile_text = self._build_user_profile(user_profile)

        # pull candidate tracks based on keywords
        query = user_profile_text[:100] # spotify search length limit
        candidates = spotify.search_tracks(query, limit=20)

        if not candidates:
            return []
        
        # fetch audio features for all candidates in one batch call
        track_ids = [t["id"] for t in candidates]
        audio_features_list = spotify.get_audio_features(track_ids) # returns list

        # build text profiles for each track
        track_profiles = [
            self._build_track_profile(track, features)
            for track, features in zip(candidates, audio_features_list)
        ]
        
        # tf-idf vectorize user profile and all track profiles together
        all_texts = [user_profile_text] + track_profiles
        tfidf_matrix = self.vectorizer.fit_transform(all_texts)

        user_vector = tfidf_matrix[0] # first row is user profile
        track_vectors = tfidf_matrix[1:] # remaining rows are tracks

        scores = cosine_similarity(user_vector, track_vectors).flatten()

        # sort by score descending and return top 10 tracks
        ranked_indices = np.argsort(scores)[::-1][:10]
        return [candidates[i] for i in ranked_indices]
