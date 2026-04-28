import os
from dotenv import load_dotenv

# Load local env values before module-level configuration constants are read
load_dotenv()

# Flask and Spotify settings are intentionally centralized so services can stay
# framework-agnostic and read simple constants
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_ACCESS_TOKEN = os.getenv("SPOTIFY_ACCESS_TOKEN")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "")
SPOTIFY_SCOPES = os.getenv(
    "SPOTIFY_SCOPES",
    "streaming user-read-email user-read-private user-modify-playback-state user-read-playback-state",
)

# Ollama defaults target the local development server
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
