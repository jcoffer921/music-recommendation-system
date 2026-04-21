import json
import re

import requests
from src.configs import OLLAMA_URL, OLLAMA_MODEL


class OllamaInterviewer:
    def _generate(self, prompt, timeout=20):
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json().get("response", "").strip()

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

    def _extract_json_object(self, raw_response):
        if not raw_response:
            return {}

        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw_response, flags=re.DOTALL)
        if not match:
            return {}

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    def _fallback_intent(self, free_text):
        text = " ".join(str(free_text or "").lower().split())

        keyword_map = {
            "mood": {
                "happy": ["happy", "joyful", "sunny", "good mood"],
                "sad": ["sad", "heartbreak", "melancholy", "cry"],
                "calm": ["calm", "relax", "peaceful", "quiet"],
                "energetic": ["energetic", "high energy", "hype", "adrenaline"],
                "focused": ["focus", "study", "work", "concentrate"],
                "romantic": ["romantic", "date night", "love"],
                "nostalgic": ["nostalgic", "throwback", "old school"],
                "moody": ["moody", "dark", "late night"],
            },
            "genre": {
                "pop": ["pop"],
                "hip-hop": ["hip-hop", "rap", "trap"],
                "r&b": ["r&b", "rnb", "soul"],
                "rock": ["rock", "alternative rock", "indie rock"],
                "jazz": ["jazz"],
                "electronic": ["electronic", "edm", "house", "techno"],
                "indie": ["indie"],
                "afrobeats": ["afrobeats", "afrobeat"],
                "lo-fi": ["lofi", "lo-fi"],
            },
            "vibe": {
                "workout": ["workout", "gym", "run", "lifting"],
                "party": ["party", "club", "dance floor"],
                "study": ["study", "focus", "deep work"],
                "late night": ["late night", "midnight", "night drive"],
                "road trip": ["road trip", "drive", "driving"],
                "chill": ["chill", "laid back", "easygoing"],
            },
        }

        extracted = {"mood": [], "genre": [], "vibe": []}
        for bucket, mapping in keyword_map.items():
            for label, phrases in mapping.items():
                if any(phrase in text for phrase in phrases):
                    extracted[bucket].append(label)

        energy = 0.82 if any(word in text for word in ["workout", "gym", "hype", "party"]) else None
        if energy is None and any(word in text for word in ["calm", "study", "late night", "chill"]):
            energy = 0.3

        valence = 0.75 if "happy" in text else None
        if valence is None and any(word in text for word in ["sad", "dark", "moody"]):
            valence = 0.28

        danceability = 0.8 if any(word in text for word in ["dance", "party", "club"]) else None
        acousticness = 0.72 if any(word in text for word in ["acoustic", "unplugged", "soft"]) else None
        tempo = 132 if any(word in text for word in ["run", "gym", "workout"]) else None
        if tempo is None and any(word in text for word in ["chill", "study", "calm"]):
            tempo = 84

        terms = extracted["mood"] + extracted["genre"] + extracted["vibe"]
        return {
            "mood": extracted["mood"],
            "genre": extracted["genre"],
            "vibe": extracted["vibe"],
            "artist": "",
            "energy": energy,
            "valence": valence,
            "danceability": danceability,
            "acousticness": acousticness,
            "tempo": tempo,
            "intent_terms": terms,
        }

    def interpret_intent(self, free_text):
        """Use Ollama to convert a natural-language music request into structured features."""
        if not str(free_text or "").strip():
            return {
                "mood": [],
                "genre": [],
                "vibe": [],
                "artist": "",
                "energy": None,
                "valence": None,
                "danceability": None,
                "acousticness": None,
                "tempo": None,
                "intent_terms": [],
            }

        prompt = f"""
        Convert the user's music request into JSON for a recommendation system.

        User request:
        {free_text}

        Return only valid JSON with this exact schema:
        {{
          "mood": ["lowercase strings"],
          "genre": ["lowercase strings"],
          "vibe": ["lowercase strings"],
          "artist": "string or empty",
          "energy": "number from 0 to 1 or null",
          "valence": "number from 0 to 1 or null",
          "danceability": "number from 0 to 1 or null",
          "acousticness": "number from 0 to 1 or null",
          "tempo": "integer bpm or null",
          "intent_terms": ["short lowercase terms"]
        }}

        Rules:
        - Infer listening intent from the language
        - Use concise tags
        - Do not add explanation
        - Prefer null over guessing when the request is ambiguous
        """

        try:
            raw_response = self._generate(prompt, timeout=25)
            parsed = self._extract_json_object(raw_response)
            if not parsed:
                return self._fallback_intent(free_text)

            fallback = self._fallback_intent(free_text)
            return {
                "mood": [str(item).strip().lower() for item in parsed.get("mood", []) if str(item).strip()],
                "genre": [str(item).strip().lower() for item in parsed.get("genre", []) if str(item).strip()],
                "vibe": [str(item).strip().lower() for item in parsed.get("vibe", []) if str(item).strip()],
                "artist": " ".join(str(parsed.get("artist", "")).split()),
                "energy": parsed.get("energy") if isinstance(parsed.get("energy"), (int, float)) else fallback.get("energy"),
                "valence": parsed.get("valence") if isinstance(parsed.get("valence"), (int, float)) else fallback.get("valence"),
                "danceability": parsed.get("danceability") if isinstance(parsed.get("danceability"), (int, float)) else fallback.get("danceability"),
                "acousticness": parsed.get("acousticness") if isinstance(parsed.get("acousticness"), (int, float)) else fallback.get("acousticness"),
                "tempo": int(parsed.get("tempo")) if isinstance(parsed.get("tempo"), (int, float)) else fallback.get("tempo"),
                "intent_terms": [
                    str(item).strip().lower() for item in parsed.get("intent_terms", []) if str(item).strip()
                ] or fallback.get("intent_terms", []),
            }
        except requests.RequestException:
            return self._fallback_intent(free_text)

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

        try:
            summary = self._generate(prompt, timeout=20)

            if not summary or "```" in summary or ":" in summary.splitlines()[0]:
                return self._fallback_summary(responses)

            return " ".join(summary.split())
        except requests.RequestException:
            return self._fallback_summary(responses)
