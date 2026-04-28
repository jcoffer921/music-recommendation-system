import json
import re

# Ollama-facing helper It keeps model prompts, fallback behavior, and response
# cleanup in one place so Flask routes do not need prompt-specific logic
import requests
from src.configs import OLLAMA_URL, OLLAMA_MODEL


class OllamaInterviewer:
    # Keep non-song media terms out of structured intent before Spotify search
    NON_MUSIC_INTENT_TERMS = {
        "broadcast",
        "channel",
        "episode",
        "fm",
        "playlist",
        "playlists",
        "podcast",
        "radio",
        "show",
        "station",
        "stations",
    }

    LOFI_INTENT_TERMS = {
        "lo-fi",
        "lofi",
        "lo-fi beats",
        "lofi beats",
        "lo-fi hip-hop",
        "lofi hip hop",
    }

    # Deterministic fallbacks keep the chat usable when Ollama is not running
    FALLBACK_QUESTIONS = [
        {
            "id": "moment",
            "question": "What kind of mood should this have?",
            "placeholder": "e.g., working late, driving, getting ready to go out",
        },
        {
            "id": "feeling",
            "question": "Should it stay close to that sound or branch into similar artists?",
            "placeholder": "e.g., focused, confident, calm, nostalgic, energized",
        },
        {
            "id": "sound",
            "question": "Any sounds or genres you want included or avoided?",
            "placeholder": "e.g., glossy synth pop, SZA, mellow R&B, 90s rock",
        },
    ]

    def _generate(self, prompt, timeout=20):
        """Send a non-streaming prompt to the configured local Ollama model."""
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
        """Legacy command-line interview used by main.py."""
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

    def get_questions(self):
        """Use Ollama to generate a short music interview, with stable fallback questions."""
        prompt = """
        Create a concise music recommendation interview.

        Return only valid JSON in this exact shape:
        {
          "questions": [
            {
              "id": "short_snake_case_id",
              "question": "one clear user-facing question",
              "placeholder": "short example answer"
            }
          ]
        }

        Requirements:
        - Ask exactly 3 questions
        - Cover listening context, desired feeling, and sound or artist direction
        - Do not ask for private personal data
        - Do not include markdown or explanation
        """

        try:
            raw_response = self._generate(prompt, timeout=6)
            parsed = self._extract_json_object(raw_response)
            questions = parsed.get("questions", []) if isinstance(parsed, dict) else []
            cleaned_questions = []
            seen_ids = set()

            # Validate model output before sending it to the browser
            for index, question in enumerate(questions):
                if not isinstance(question, dict):
                    continue

                raw_id = str(question.get("id") or f"question_{index + 1}").strip().lower()
                question_id = re.sub(r"[^a-z0-9_]+", "_", raw_id).strip("_") or f"question_{index + 1}"
                question_text = " ".join(str(question.get("question", "")).split())
                placeholder = " ".join(str(question.get("placeholder", "")).split())

                if not question_text or question_id in seen_ids:
                    continue

                cleaned_questions.append(
                    {
                        "id": question_id,
                        "question": question_text,
                        "placeholder": placeholder,
                    }
                )
                seen_ids.add(question_id)

                if len(cleaned_questions) == 3:
                    break

            return cleaned_questions if len(cleaned_questions) == 3 else self.FALLBACK_QUESTIONS
        except requests.RequestException:
            return self.FALLBACK_QUESTIONS

    def get_next_question(self, history, initial_request=""):
        """Ask Ollama for the next conversational interview question."""
        initial_request = " ".join(str(initial_request or "").split())
        # Only complete question/answer turns are included in the model context
        cleaned_history = []
        for item in history or []:
            question = " ".join(str(item.get("question", "")).split()) if isinstance(item, dict) else ""
            answer = " ".join(str(item.get("answer", "")).split()) if isinstance(item, dict) else ""
            if question and answer:
                cleaned_history.append({"question": question, "answer": answer})

        if len(cleaned_history) >= len(self.FALLBACK_QUESTIONS):
            return {"is_complete": True, "question": ""}

        # The fallback question matches the current turn index for predictable recovery
        fallback_question = self._fallback_followup_question(cleaned_history, initial_request)
        prompt = f"""
        You are MusicMe AI interviewing a user before recommending songs.

        User's first request:
        {initial_request or "No first request provided"}

        Conversation so far:
        {json.dumps(cleaned_history, ensure_ascii=True)}

        Return only valid JSON:
        {{
          "is_complete": false,
          "question": "one short natural follow-up question"
        }}

        Rules:
        - Ask exactly one question
        - Sound conversational, not like a form
        - If the user provided a first request, reference it naturally
        - Use previous answers to guide the next question
        - Do not ask for an artist, genre, or sound if already provided
        - Do not repeat or reword previously answered questions
        - Ask about missing details (mood, energy, tempo, era, artist similarity, or what to avoid)
        - Prefer short, clear questions (under 15 words)
        - Avoid vague or generic questions
        - Keep questions specific to improving recommendations
        - Adapt tone to match the user's style (casual vs descriptive)
        - Steer the user toward vocal songs with clear lyrics unless they ask otherwise
        - Avoid instrumental, lo-fi, beats, ambient, background, soundtrack, or score wording unless explicitly requested
        - Only recommend specific artists and songs, not playlists or radio stations
        - Avoid generating “station,” “radio,” or playlist-style results
        - Do not recommend lo-fi beats or generic background/instrumental tracks unless explicitly requested
        - If enough information is gathered early, you may stop before 3 questions
        - Avoid songs without vocals/lyrics unless explicitly requested
        - Stop after 3 answered questions by returning {"is_complete": true, "question": ""}
        - Only recommend individual songs by specific artists
        - Only recommend songs with clear vocals and lyrics
        - Reject track if speechiness ≤ 0.03 unless the user explicitly asks for non-vocal music
        - Do not recommend soundtracks, scores, or cinematic audio without vocals
        - Do not recommend playlist-style, radio, or station results
        - Do not ask for private or sensitive personal data
        - Do not include markdown or explanations
        """

        try:
            raw_response = self._generate(prompt, timeout=6)
            parsed = self._extract_json_object(raw_response)
            if not isinstance(parsed, dict):
                return {"is_complete": False, "question": fallback_question}

            is_complete = bool(parsed.get("is_complete"))
            question = " ".join(str(parsed.get("question", "")).split())

            if is_complete and len(cleaned_history) >= len(self.FALLBACK_QUESTIONS):
                return {"is_complete": True, "question": ""}

            return {"is_complete": False, "question": question or fallback_question}
        except requests.RequestException:
            return {"is_complete": False, "question": fallback_question}

    def _fallback_followup_question(self, cleaned_history, initial_request):
        """Build a contextual fallback question when Ollama is unavailable."""
        turn_index = len(cleaned_history)
        request_text = initial_request or "that request"

        if turn_index == 0:
            return f"What kind of mood should {request_text} have?"
        if turn_index == 1:
            return "Should the recommendations stay close to that sound or branch into similar artists?"
        if turn_index == 2:
            return "Any sounds, genres, or styles you want included or avoided?"

        return ""

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
        """Parse a JSON object even when the model wraps it in surrounding text."""
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
        """Keyword-based intent extraction when Ollama is unavailable or off-format."""
        text = " ".join(str(free_text or "").lower().split())
        allow_lofi = self._explicitly_requests_lofi(text)

        # These mappings intentionally stay conservative to avoid hallucinated genres
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
                    if label == "lo-fi" and not allow_lofi:
                        continue
                    extracted[bucket].append(label)

        # Audio targets give the ranker useful numeric hints even with sparse tags
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

    def _explicitly_requests_lofi(self, value):
        """Return True when the user directly asks for lo-fi."""
        text = " ".join(str(value or "").lower().split())
        return bool(re.search(r"\blo[\s-]?fi\b|\blofi\b", text))

    def _clean_intent_terms(self, values, allow_lofi=False):
        """Deduplicate model tags and strip terms that are not song descriptors."""
        cleaned_terms = []
        seen_terms = set()

        for value in values or []:
            cleaned = " ".join(str(value).strip().lower().split())
            if not cleaned or cleaned in self.NON_MUSIC_INTENT_TERMS or cleaned in seen_terms:
                continue
            if not allow_lofi and cleaned in self.LOFI_INTENT_TERMS:
                continue

            cleaned_terms.append(cleaned)
            seen_terms.add(cleaned)

        return cleaned_terms

    # AI-Assistance 
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

        allow_lofi = self._explicitly_requests_lofi(free_text)
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
        - Recommend songs or tracks only
        - Ignore requests for radio stations, broadcasts, podcasts, shows, episodes, channels, or playlists
        - Do not include "radio", "station", "podcast", "show", "episode", "broadcast", "channel", "playlist", "playlists", or "fm" in any output field
        - Do not include lo-fi, lofi, beats, instrumental, ambient, background, soundtrack, or score unless the user explicitly asks for that content
        - Prefer vocal songs with clear lyrics
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
            # Preserve model-provided numeric cues, but use fallback values if they are absent
            artist = " ".join(str(parsed.get("artist", "")).split())
            if artist.lower() in self.NON_MUSIC_INTENT_TERMS:
                artist = ""
            if not allow_lofi and artist.lower() in self.LOFI_INTENT_TERMS:
                artist = ""

            return {
                "mood": self._clean_intent_terms(parsed.get("mood", []), allow_lofi=allow_lofi),
                "genre": self._clean_intent_terms(parsed.get("genre", []), allow_lofi=allow_lofi),
                "vibe": self._clean_intent_terms(parsed.get("vibe", []), allow_lofi=allow_lofi),
                "artist": artist,
                "energy": parsed.get("energy") if isinstance(parsed.get("energy"), (int, float)) else fallback.get("energy"),
                "valence": parsed.get("valence") if isinstance(parsed.get("valence"), (int, float)) else fallback.get("valence"),
                "danceability": parsed.get("danceability") if isinstance(parsed.get("danceability"), (int, float)) else fallback.get("danceability"),
                "acousticness": parsed.get("acousticness") if isinstance(parsed.get("acousticness"), (int, float)) else fallback.get("acousticness"),
                "tempo": int(parsed.get("tempo")) if isinstance(parsed.get("tempo"), (int, float)) else fallback.get("tempo"),
                "intent_terms": self._clean_intent_terms(parsed.get("intent_terms", []), allow_lofi=allow_lofi)
                or fallback.get("intent_terms", []),
            }
        except requests.RequestException:
            return self._fallback_intent(free_text)

    def summarize(self, responses):
        """Generate a short human-readable explanation of the cleaned preferences."""
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
