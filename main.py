from services.recommendation_service import rank_tracks
from services.spotify_service import SpotifyService, build_spotify_query
from src.ollama.interviewer import OllamaInterviewer
from utils.input_parser import normalize_form_data


def main():
    print("AI Music Recommendation System")

    # Step 1: Interview
    interviewer = OllamaInterviewer()
    responses = interviewer.ask_questions()

    # Step 2: Normalize input, then summarize the cleaned preferences.
    normalized_preferences = normalize_form_data({
        "selected_moods": [],
        "custom_mood": responses.get("mood", ""),
        "selected_genres": [],
        "custom_genre": responses.get("genre", ""),
        "artist": responses.get("artists", ""),
        "vibe": responses.get("discovery", ""),
    })

    summary = interviewer.summarize(normalized_preferences)
    print("\n--- AI Summary ---")
    print(summary)

    # Step 3: Search Spotify, then rank the returned tracks.
    spotify_query = build_spotify_query(normalized_preferences)
    spotify_service = SpotifyService()
    candidate_tracks = spotify_service.search_tracks(spotify_query, limit=20)
    track_ids = [track.get("id") for track in candidate_tracks if track.get("id")]
    fetched_audio_features = spotify_service.get_audio_features(track_ids)
    audio_features_by_id = {
        track_id: feature_set
        for track_id, feature_set in zip(track_ids, fetched_audio_features)
    }

    recommendations = rank_tracks(
        candidate_tracks,
        normalized_preferences,
        audio_features_list=[
            audio_features_by_id.get(track.get("id"), {})
            for track in candidate_tracks
        ],
    )

    print("\n--- Recommendations ---")
    for i, track in enumerate(recommendations, 1):
        print(f"{i}. {track['name']} - {track['artists'][0]['name']}")


if __name__ == "__main__":
    main()
