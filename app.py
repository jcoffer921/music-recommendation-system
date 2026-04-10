from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from src.ollama.interviewer import OllamaInterviewer
from src.api.spotify_client import SpotifyClient
from src.ai.recommender import MusicRecommender

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)


@app.route('/', methods=['GET'])
def home():
    """Render the main recommendation page"""
    return render_template('index.html')


@app.route('/recommend', methods=['POST'])
def get_recommendations():
    """
    Get music recommendations based on user responses
    Expected JSON body: { "responses": { "question1": "answer1", ... } }
    """
    try:
        data = request.get_json()
        
        if not data or 'responses' not in data:
            return jsonify({
                'error': 'Missing required field: responses'
            }), 400
        
        responses = data['responses']
        
        # Get AI summary
        interviewer = OllamaInterviewer()
        summary = interviewer.summarize(responses)
        
        # Get recommendations
        spotify = SpotifyClient()
        recommender = MusicRecommender()
        recommendations = recommender.recommend(responses, spotify)
        
        return jsonify({
            'summary': summary,
            'recommendations': recommendations
        }), 200
    
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
