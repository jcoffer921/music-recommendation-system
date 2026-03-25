from src.ollama.interviewer import OllamaInterviewer
from src.api.spotify_client import SpotifyClient
from src.ai.recommender import MusicRecommender


def main():
    print("AI Music Recommendation System")

    # Step 1: Interview
    interviewer = OllamaInterviewer()
    responses = interviewer.ask_questions()

    # Step 2: AI Summary
    summary = interviewer.summarize(responses)
    print("\n--- AI Summary ---")
    print(summary)

    # Step 3: Recommendation
    spotify = SpotifyClient()
    recommender = MusicRecommender()

    recommendations = recommender.recommend(responses, spotify)

    print("\n--- Recommendations ---")
    for i, track in enumerate(recommendations, 1):
        print(f"{i}. {track['name']} - {track['artists'][0]['name']}")


if __name__ == "__main__":
    main()