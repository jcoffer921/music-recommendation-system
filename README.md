# Music Recommendation System

<!-- Project overview for setup, architecture, and local development. -->

This app collects music preferences, queries Spotify, and ranks tracks against the user's stated mood, genre, artist, vibe, and natural-language request.

## Stack
- Flask
- Spotipy / Spotify Web API
- Scikit-learn
- Ollama for preference summarization and intent extraction

## MusicMe AI

The natural-language recommendation flow is a separate premium feature, not part of the default recommender.

On the homepage, users can switch between:
- `Regular Recommender` for the existing mood/genre/artist/vibe workflow
- `MusicMe AI` for a premium Ollama-assisted natural-language request flow

Only the `MusicMe AI` tab sends free-text requests through Ollama intent extraction and audio-profile targeting.

## NLP Integration

The premium `MusicMe AI` tab includes a dedicated free-text prompt so users can describe what they want in plain language instead of relying only on fixed fields.

Ollama is used in two places:
- summarizing the final preference profile for the recommendations workspace
- extracting structured intent from the free-text request, including mood, genre, vibe, and audio-profile targets such as energy, valence, danceability, acousticness, and tempo

That parsed intent is merged with the existing form selections before Spotify search and ranking. This gives the system more context and improves recommendation accuracy when a user asks for something nuanced like "upbeat late-night driving music with a little nostalgia."

## Spotify SDK Integration

The project now uses a reusable Spotify client in [`src/api/spotify_client.py`](/mnt/c/musicRecommendationSystem/src/api/spotify_client.py) and a higher-level service in [`services/spotify_service.py`](/mnt/c/musicRecommendationSystem/services/spotify_service.py).

Returned Spotify results are normalized before they reach the app, including:
- track name and artists
- album metadata and artwork
- preview URL
- Spotify deep link
- audio feature lookup for scoring when available

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file from `.env.example` and add Spotify app credentials:
```env
FLASK_SECRET_KEY=change-me
SPOTIFY_ACCESS_TOKEN=
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=
SPOTIFY_SCOPES=streaming user-read-email user-read-private user-modify-playback-state user-read-playback-state
```

Use `SPOTIFY_ACCESS_TOKEN` only for short-lived local testing. For a stable backend setup, use `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`.
For Spotify Web Playback SDK testing, register the exact callback URI you are using in your browser, for example:
- `http://127.0.0.1:5000/auth/callback`
- `http://localhost:5000/auth/callback`

Spotify requires an exact match. `localhost` and `127.0.0.1` are different values.

3. Run the Flask app:
```bash
python app.py
```

4. Open `http://localhost:5000`
