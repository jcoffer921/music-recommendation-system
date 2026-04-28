from services.recommendation_service import rank_tracks
from services.spotify_service import SpotifyService, build_spotify_query, build_spotify_queries
from src.ollama.interviewer import OllamaInterviewer
from utils.input_parser import normalize_form_data


# Legacy CLI entrypoint for quickly exercising the recommendation pipeline
# without running the Flask web app
def main():
    print("AI Music Recommendation System")

    # Step 1: Interview
    interviewer = OllamaInterviewer()
    responses = interviewer.ask_questions()

    # Step 2: Normalize input, then summarize the cleaned preferences
    normalized_preferences = normalize_form_data({
        "selected_moods": [],
        "custom_mood": responses.get("mood", ""),
        "selected_genres": [],
        "custom_genre": responses.get("genre", ""),
        "artist": responses.get("artists", ""),
        "vibe": responses.get("discovery", ""),
        "natural_language_request": " ".join(
            filter(
                None,
                [
                    responses.get("mood", ""),
                    responses.get("genre", ""),
                    responses.get("artists", ""),
                    responses.get("discovery", ""),
                ],
            )
        ),
    })

    summary = interviewer.summarize(normalized_preferences)
    print("\n--- AI Summary ---")
    print(summary)

    # Step 3: Search Spotify, then rank the returned tracks
    spotify_query = build_spotify_query(normalized_preferences)
    spotify_queries = build_spotify_queries(normalized_preferences)
    spotify_service = SpotifyService()
    candidate_tracks, audio_features = spotify_service.search_tracks_with_features(
        spotify_query,
        limit=40,
        fallback_queries=spotify_queries[1:],
    )

    recommendations = rank_tracks(
        candidate_tracks,
        normalized_preferences,
        audio_features_list=audio_features,
    )

    # CLI output intentionally stays compact for terminal demos
    print("\n--- Recommendations ---")
    for i, track in enumerate(recommendations, 1):
        print(f"{i}. {track['name']} - {track['artists'][0]['name']}")


if __name__ == "__main__":
    main()
