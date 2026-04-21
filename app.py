from __future__ import annotations

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
import requests
import time

from services.recommendation_service import rank_tracks
from services.spotify_auth_service import (
    build_login_url_for_redirect,
    exchange_code_for_token,
    refresh_access_token,
    resolve_redirect_uri,
    token_is_expired,
)
from services.spotify_service import (
    SpotifyService,
    build_ai_spotify_queries,
    build_spotify_query,
    build_spotify_queries,
)
from src.configs import FLASK_SECRET_KEY
from src.ollama.interviewer import OllamaInterviewer
from utils.input_parser import merge_nlp_intent, normalize_form_data

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = FLASK_SECRET_KEY
CORS(app)


def _get_valid_spotify_session_token():
    token_payload = session.get("spotify_token")
    if not token_payload:
        return None

    if token_is_expired(token_payload):
        refresh_token = token_payload.get("refresh_token")
        if not refresh_token:
            session.pop("spotify_token", None)
            return None

        refreshed_token = refresh_access_token(refresh_token)
        session["spotify_token"] = refreshed_token
        return refreshed_token

    return token_payload


def _build_standard_recommendation_payload(raw_form_data):
    """Build recommendations using the standard non-AI preference flow."""
    normalized_preferences = normalize_form_data(raw_form_data)
    spotify_query = build_spotify_query(normalized_preferences)
    spotify_queries = build_spotify_queries(normalized_preferences)

    if not spotify_query:
        raise ValueError("Please provide at least one mood, genre, artist, or vibe to search Spotify.")

    interviewer = OllamaInterviewer()
    summary = interviewer.summarize(normalized_preferences)

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
        limit=10,
    )

    return {
        "normalized_preferences": normalized_preferences,
        "spotify_query": spotify_query,
        "spotify_queries": spotify_queries,
        "summary": summary,
        "mode": "standard",
        "mode_label": "Regular Recommender",
        "spotify_sdk": {
            "provider": "Spotify Web API",
            "track_count": len(candidate_tracks),
            "authenticated": bool(_get_valid_spotify_session_token()),
        },
        "recommendations": recommendations,
    }


def _build_ai_recommendation_payload(raw_form_data):
    """Build recommendations using the premium MusicMe AI flow."""
    normalized_preferences = normalize_form_data(
        {
            "selected_moods": raw_form_data.get("selected_moods", ""),
            "custom_mood": raw_form_data.get("custom_mood", ""),
            "selected_genres": raw_form_data.get("selected_genres", ""),
            "custom_genre": raw_form_data.get("custom_genre", ""),
            "artist": raw_form_data.get("artist") or raw_form_data.get("ai_artist", ""),
            "vibe": raw_form_data.get("vibe") or raw_form_data.get("ai_vibe", ""),
            "natural_language_request": raw_form_data.get("natural_language_request", ""),
        }
    )
    interviewer = OllamaInterviewer()
    parsed_intent = interviewer.interpret_intent(normalized_preferences.get("natural_language_request", ""))
    normalized_preferences = merge_nlp_intent(normalized_preferences, parsed_intent)
    spotify_queries = build_ai_spotify_queries(normalized_preferences)
    spotify_query = spotify_queries[0] if spotify_queries else ""

    if not spotify_query:
        raise ValueError("Please describe what you want for MusicMe AI, or add an artist or vibe to guide the search.")

    summary = interviewer.summarize(normalized_preferences)

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
        limit=10,
    )

    return {
        "normalized_preferences": normalized_preferences,
        "spotify_query": spotify_query,
        "spotify_queries": spotify_queries,
        "summary": summary,
        "parsed_intent": parsed_intent,
        "mode": "ai",
        "mode_label": "MusicMe AI",
        "spotify_sdk": {
            "provider": "Spotify Web API",
            "track_count": len(candidate_tracks),
            "authenticated": bool(_get_valid_spotify_session_token()),
        },
        "recommendations": recommendations,
    }


@app.route("/", methods=["GET"])
def home():
    """Render the homepage with the recommendation form."""
    active_tab = request.args.get("tab", "standard")
    if active_tab not in {"standard", "ai"}:
        active_tab = "standard"
    return render_template("index.html", active_tab=active_tab)


@app.route("/about", methods=["GET"])
def about():
    """Render the about page."""
    return render_template("about.html")


@app.route("/auth/login", methods=["GET"])
def spotify_login():
    """Start the Spotify Authorization Code flow."""
    redirect_uri = resolve_redirect_uri(request.url_root)
    login_url, state = build_login_url_for_redirect(redirect_uri)
    next_path = request.args.get("next", "")
    if not next_path.startswith("/"):
        next_path = url_for("home")
    session["spotify_auth_state"] = state
    session["spotify_redirect_uri"] = redirect_uri
    session["spotify_post_auth_redirect"] = next_path
    return redirect(login_url)


@app.route("/auth/callback", methods=["GET"])
def spotify_callback():
    """Handle Spotify OAuth callback and persist the session token."""
    error = request.args.get("error")
    if error:
        return redirect(url_for("home", auth_error=error))

    returned_state = request.args.get("state", "")
    expected_state = session.get("spotify_auth_state", "")
    if not returned_state or returned_state != expected_state:
        return redirect(url_for("home", auth_error="state_mismatch"))

    code = request.args.get("code", "")
    if not code:
        return redirect(url_for("home", auth_error="missing_code"))

    redirect_uri = session.get("spotify_redirect_uri") or resolve_redirect_uri(request.url_root)
    token_payload = exchange_code_for_token(code, redirect_uri=redirect_uri)
    session["spotify_token"] = token_payload
    session.pop("spotify_auth_state", None)
    session.pop("spotify_redirect_uri", None)
    next_path = session.pop("spotify_post_auth_redirect", url_for("home"))
    return redirect(next_path)


@app.route("/auth/token", methods=["GET"])
def spotify_token():
    """Return the active Spotify access token for the Web Playback SDK."""
    token_payload = _get_valid_spotify_session_token()
    if not token_payload:
        return jsonify({"access_token": ""}), 200

    return jsonify(
        {
            "access_token": token_payload.get("access_token", ""),
            "expires_at": token_payload.get("expires_at"),
        }
    ), 200


@app.route("/auth/logout", methods=["POST"])
def spotify_logout():
    """Clear the current Spotify login session."""
    session.pop("spotify_token", None)
    session.pop("spotify_auth_state", None)
    return jsonify({"ok": True}), 200


@app.route("/player/play", methods=["POST"])
def spotify_player_play():
    """Transfer playback to the browser SDK device and play a selected URI."""
    token_payload = _get_valid_spotify_session_token()
    if not token_payload:
        return jsonify({"error": "Spotify login required."}), 401

    payload = request.get_json() or {}
    track_uri = (payload.get("uri") or "").strip()
    device_id = (payload.get("device_id") or "").strip()

    if not track_uri or not device_id:
        return jsonify({"error": "Missing required fields: uri and device_id."}), 400

    headers = {
        "Authorization": f"Bearer {token_payload['access_token']}",
        "Content-Type": "application/json",
    }

    transfer_response = requests.put(
        "https://api.spotify.com/v1/me/player",
        json={"device_ids": [device_id], "play": False},
        headers=headers,
        timeout=15,
    )
    if transfer_response.status_code not in (202, 204):
        return jsonify(
            {
                "error": "Spotify could not activate the browser player.",
                "details": transfer_response.text,
            }
        ), transfer_response.status_code

    # Spotify can acknowledge transfer before the new device is fully ready.
    # Give it a brief moment so the subsequent play request does not race it.
    time.sleep(0.4)

    play_response = requests.put(
        f"https://api.spotify.com/v1/me/player/play?device_id={device_id}",
        json={"uris": [track_uri]},
        headers=headers,
        timeout=15,
    )
    if play_response.status_code not in (202, 204):
        if play_response.status_code == 403:
            message = "Spotify rejected playback. Web Playback SDK requires a Premium account."
        elif play_response.status_code == 404:
            message = "Spotify could not find an active browser player device yet. Wait a second and try again."
        else:
            message = "Spotify could not start playback."
        return jsonify(
            {
                "error": message,
                "details": play_response.text,
            }
        ), play_response.status_code

    return jsonify({"ok": True}), 200


@app.route("/recommendations", methods=["GET"])
def recommendations_page():
    """Render the recommendations page using the most recent recommendation payload."""
    recommendation_data = session.get("latest_recommendations")
    return render_template("recommendations.html", recommendation_data=recommendation_data)


@app.route("/recommendations", methods=["POST"])
def generate_recommendations_page():
    """Handle homepage form submission and redirect to the recommendations page."""
    try:
        raw_form_data = request.form.to_dict(flat=True)
        recommendation_data = _build_standard_recommendation_payload(raw_form_data)
        session["latest_recommendations"] = recommendation_data
        return redirect(url_for("recommendations_page"))
    except ValueError as exc:
        return render_template(
            "index.html",
            form_error=str(exc),
            previous_values=request.form,
            active_tab="standard",
        ), 400
    except PermissionError as exc:
        return render_template(
            "index.html",
            form_error=str(exc),
            previous_values=request.form,
            active_tab="standard",
        ), 401
    except requests.RequestException as exc:
        return render_template(
            "index.html",
            form_error=f"Spotify request failed: {exc}",
            previous_values=request.form,
            active_tab="standard",
        ), 502
    except Exception as exc:
        return render_template(
            "index.html",
            form_error=str(exc),
            previous_values=request.form,
            active_tab="standard",
        ), 500


@app.route("/musicme-ai/recommendations", methods=["POST"])
def generate_ai_recommendations_page():
    """Handle premium MusicMe AI form submission and redirect to the recommendations page."""
    try:
        raw_form_data = request.form.to_dict(flat=True)
        recommendation_data = _build_ai_recommendation_payload(raw_form_data)
        session["latest_recommendations"] = recommendation_data
        return redirect(url_for("recommendations_page"))
    except ValueError as exc:
        return render_template(
            "index.html",
            form_error=str(exc),
            previous_values=request.form,
            active_tab="ai",
        ), 400
    except PermissionError as exc:
        return render_template(
            "index.html",
            form_error=str(exc),
            previous_values=request.form,
            active_tab="ai",
        ), 401
    except requests.RequestException as exc:
        return render_template(
            "index.html",
            form_error=f"Spotify request failed: {exc}",
            previous_values=request.form,
            active_tab="ai",
        ), 502
    except Exception as exc:
        return render_template(
            "index.html",
            form_error=str(exc),
            previous_values=request.form,
            active_tab="ai",
        ), 500


@app.route("/recommend", methods=["POST"])
def get_recommendations():
    """
    Get music recommendations based on user responses.
    Expected JSON body: { "responses": { "question1": "answer1", ... } }
    """
    try:
        data = request.get_json() or {}

        if not data or "responses" not in data:
            return jsonify({"error": "Missing required field: responses"}), 400

        recommendation_payload = _build_standard_recommendation_payload(data["responses"])
        return jsonify(recommendation_payload), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401
    except requests.RequestException as exc:
        return jsonify({"error": f"Spotify request failed: {exc}"}), 502
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/recommend-ai", methods=["POST"])
def get_ai_recommendations():
    """Get premium MusicMe AI recommendations based on natural-language requests."""
    try:
        data = request.get_json() or {}

        if not data or "responses" not in data:
            return jsonify({"error": "Missing required field: responses"}), 400

        recommendation_payload = _build_ai_recommendation_payload(data["responses"])
        return jsonify(recommendation_payload), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401
    except requests.RequestException as exc:
        return jsonify({"error": f"Spotify request failed: {exc}"}), 502
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/interview-questions", methods=["GET"])
def get_questions():
    """Get the interview questions."""
    try:
        interviewer = OllamaInterviewer()
        questions = interviewer.get_questions() if hasattr(interviewer, "get_questions") else []
        return jsonify({"questions": questions}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
