from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from services.recommendation_service import rank_tracks
from services.spotify_service import SpotifyService, build_spotify_query
from src.ollama.interviewer import OllamaInterviewer
from utils.input_parser import normalize_form_data

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)


@app.route('/', methods=['GET'])
def home():
    """Render the main recommendation page"""
    return render_template('index.html')


@app.route('/about', methods=['GET'])
def about():
    """Render the about page"""
    return render_template('about.html')


@app.route('/recommend', methods=['POST'])
def get_recommendations():
    """
    Get music recommendations based on user responses
    Expected JSON body: { "responses": { "question1": "answer1", ... } }
    """
    try:
        data = request.get_json() or {}

        if not data or 'responses' not in data:
            return jsonify({
                'error': 'Missing required field: responses'
            }), 400

        raw_form_data = data['responses']
        normalized_preferences = normalize_form_data(raw_form_data)
        spotify_query = build_spotify_query(normalized_preferences)

        if not spotify_query:
            return jsonify({
                'error': 'Please provide at least an artist or genre to search Spotify.'
            }), 400

        # Build a readable summary from normalized user preferences.
        interviewer = OllamaInterviewer()
        summary = interviewer.summarize(normalized_preferences)

        # Search Spotify with only the fields that work well as a search query.
        spotify_service = SpotifyService()
        candidate_tracks = spotify_service.search_tracks(spotify_query, limit=20)
        track_ids = [track.get('id') for track in candidate_tracks if track.get('id')]
        fetched_audio_features = spotify_service.get_audio_features(track_ids)
        audio_features_by_id = {
            track_id: feature_set
            for track_id, feature_set in zip(track_ids, fetched_audio_features)
        }
        audio_features = [
            audio_features_by_id.get(track.get('id'), {})
            for track in candidate_tracks
        ]

        # Rank the returned tracks using the remaining preference signals.
        recommendations = rank_tracks(
            candidate_tracks,
            normalized_preferences,
            audio_features_list=audio_features,
            limit=10,
        )

        return jsonify({
            'normalized_preferences': normalized_preferences,
            'spotify_query': spotify_query,
            'summary': summary,
            'recommendations': recommendations
        }), 200

    except ValueError as exc:
        return jsonify({
            'error': str(exc)
        }), 400
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/interview-questions', methods=['GET'])
def get_questions():
    """Get the interview questions"""
    try:
        interviewer = OllamaInterviewer()
        # Note: add a method to retrieve questions from interviewer
        questions = interviewer.get_questions() if hasattr(interviewer, 'get_questions') else []
        
        return jsonify({
            'questions': questions
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
