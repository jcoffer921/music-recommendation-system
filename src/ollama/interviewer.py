import requests
from src.configs import OLLAMA_URL, OLLAMA_MODEL


class OllamaInterviewer:

    def ask_questions(self):
        print("\n--- Music Interview ---")

        mood = input("What mood are you in? ")
        artists = input("Favorite artists? ")
        genre = input("Preferred genre? ")
        energy = input("Energy level (low, medium, high)? ")
        discovery = input("Discover new music or stick to familiar? ")

        return {
            "mood": mood,
            "artists": artists,
            "genre": genre,
            "energy": energy,
            "discovery": discovery
        }

    def summarize(self, responses):
        prompt = f"""
        Convert this into structured music preferences:

        {responses}

        Return:
        mood:
        genres:
        energy:
        artist_style:
        """

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=payload)
        return response.json()["response"]