import requests
from src.configs import OLLAMA_URL, OLLAMA_MODEL


class OllamaInterviewer:
    def _format_value(self, value, default_text):
        """Convert lists and blanks into display-friendly summary text."""
        if isinstance(value, list):
            cleaned_items = [str(item).strip() for item in value if str(item).strip()]
            return ", ".join(cleaned_items) if cleaned_items else default_text

        cleaned_value = " ".join(str(value).strip().split()) if value is not None else ""
        return cleaned_value or default_text

    def ask_questions(self):
        print("\n--- Music Interview ---")

        mood = input("What mood are you in? ")
        artists = input("Favorite artists? ")
        genre = input("Preferred genre? ")
        discovery = input("Discover new music or stick to familiar? ")

        return {
            "mood": mood,
            "artists": artists,
            "genre": genre,
            "discovery": discovery
        }

    def _fallback_summary(self, responses):
        """Build a readable summary when the model is unavailable or off-format."""
        mood = self._format_value(responses.get("mood"), "their current mood")
        genre = self._format_value(responses.get("genre"), "a mix of genres")
        artist = self._format_value(
            responses.get("artist") or responses.get("artists"),
            "artists they already enjoy",
        )
        vibe = self._format_value(responses.get("vibe"), "the moment they are in")

        return (
            f"You're looking for {mood} music with a {vibe} vibe, leaning toward {genre} and "
            f"artists like {artist}. The recommendations will aim to match that overall feel and style."
        )

    def summarize(self, responses):
        prompt = f"""
        Write a short, appealing music preference summary for a music recommendation app.

        {responses}

        Requirements:
        - Write 2 concise sentences
        - Describe the user's mood, genre, artist taste, and vibe naturally
        - Do not use JSON, YAML, markdown, bullet points, labels, or code fences
        - Do not say "Here is", "structured preferences", or "Let me know"
        - Return only the summary text
        """

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=20)
            response.raise_for_status()
            summary = response.json().get("response", "").strip()

            if not summary or "```" in summary or ":" in summary.splitlines()[0]:
                return self._fallback_summary(responses)

            return " ".join(summary.split())
        except requests.RequestException:
            return self._fallback_summary(responses)
