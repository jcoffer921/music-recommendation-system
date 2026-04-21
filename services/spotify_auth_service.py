"""Helpers for Spotify Authorization Code flow and token refresh."""

from __future__ import annotations

import secrets
import time
from urllib.parse import urlencode

import requests

from src.configs import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, SPOTIFY_SCOPES

SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


def _require_auth_config():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise ValueError(
            "Spotify OAuth is not configured. Set SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET in your .env file."
        )


def build_login_url():
    """Return the Spotify authorize URL and generated state value."""
    return build_login_url_for_redirect(SPOTIFY_REDIRECT_URI)


def resolve_redirect_uri(current_origin=None):
    """Use configured redirect URI or derive it from the current host."""
    if SPOTIFY_REDIRECT_URI:
        return SPOTIFY_REDIRECT_URI

    if not current_origin:
        raise ValueError(
            "Spotify redirect URI is missing. Set SPOTIFY_REDIRECT_URI or use the login route from the running app."
        )

    base_origin = current_origin.rstrip("/")
    return f"{base_origin}/auth/callback"


def build_login_url_for_redirect(redirect_uri):
    """Return the Spotify authorize URL and generated state value for the provided redirect URI."""
    _require_auth_config()
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SPOTIFY_SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    return f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(params)}", state


def _token_request(payload):
    _require_auth_config()
    response = requests.post(
        SPOTIFY_TOKEN_URL,
        data=payload,
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _normalize_token_payload(token_data, previous_refresh_token=None):
    expires_in = int(token_data.get("expires_in", 3600))
    return {
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token") or previous_refresh_token or "",
        "scope": token_data.get("scope", ""),
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": int(time.time()) + max(expires_in - 30, 0),
    }


def exchange_code_for_token(code, redirect_uri=None):
    """Exchange an authorization code for Spotify tokens."""
    resolved_redirect_uri = redirect_uri or SPOTIFY_REDIRECT_URI
    token_data = _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": resolved_redirect_uri,
        }
    )
    return _normalize_token_payload(token_data)


def refresh_access_token(refresh_token):
    """Refresh the Spotify access token using a stored refresh token."""
    if not refresh_token:
        raise ValueError("Spotify refresh token is missing.")

    token_data = _token_request(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    )
    return _normalize_token_payload(token_data, previous_refresh_token=refresh_token)


def token_is_expired(token_payload):
    """Return True when the current session token should be refreshed."""
    if not token_payload:
        return True

    expires_at = token_payload.get("expires_at", 0)
    return int(time.time()) >= int(expires_at)
