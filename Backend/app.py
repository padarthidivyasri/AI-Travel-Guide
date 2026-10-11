from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai.errors import APIError
import requests
import base64
import os

app = Flask(__name__)
CORS(app)

PROMPTS = {
    "Summary": """
You are a professional tourist guide.
Provide a high-level overview of "{place}" in {language}.

Focus on:
- The historical significance
- Why the place is famous
- Key architectural or cultural highlights

Keep the explanation concise, engaging, and easy to follow.
Avoid excessive details and dates.
Limit the response to around 200 words.
s
Respond ONLY in {language}.
""",

    "Detailed": """
You are a professional tourist guide.
Provide a detailed and immersive explanation of "{place}" in {language}.

Cover:
- Historical background and timeline
- Architectural design and unique features
- Cultural importance and notable events
- Interesting facts and visitor insights

Explain concepts clearly and in a storytelling manner.
Include relevant details and examples to create a rich experience.
Limit the response to around 400 words.

Respond ONLY in {language}.
"""
}

def generate_speech(text, voice_id, locale):
    url = "https://global.api.murf.ai/v1/speech/stream"
    headers = {
        "api-key": os.environ["MURF_API_KEY"],
        "Content-Type": "application/json"
    }
    data = {
    "voice_id": voice_id,
    "text": text,
    "locale": locale,
    "model": "FALCON",
    "format": "MP3",
    "sampleRate": 24000,
    "channelType": "MONO"
    }

    response = requests.post(url, headers=headers, json=data, timeout=60)
    response.raise_for_status()
    return response.content


def generate_description(place, answer_type, language):
    prompt = PROMPTS[answer_type].format(place=place, language=language)
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )
    return response.text
    
@app.route("/api/generate-audio-guide", methods=["POST"])
@app.route("/generate-audio-guide", methods=["POST"])
def generate_audio_guide():
    data = request.get_json(silent=True)
    required_fields = ("place", "answerType", "language", "voiceId", "locale")
    if not isinstance(data, dict) or any(
        not isinstance(data.get(field), str) or not data[field].strip()
        for field in required_fields
    ):
        return jsonify(error="Provide place, answerType, language, voiceId, and locale."), 400

    if data["answerType"] not in PROMPTS:
        return jsonify(error="answerType must be Summary or Detailed."), 400

    missing_keys = [
        key for key in ("GOOGLE_API_KEY", "MURF_API_KEY")
        if not os.environ.get(key)
    ]
    if missing_keys:
        app.logger.error("Missing required environment variables: %s", ", ".join(missing_keys))
        return jsonify(
            error=f"Server configuration is missing: {', '.join(missing_keys)}. "
            "Add them in Vercel Project Settings > Environment Variables."
        ), 503

    try:
        text_description = generate_description(
            data["place"], data["answerType"], data["language"]
        )
    except APIError:
        app.logger.exception("Google Gemini request failed")
        return jsonify(
            error="Google Gemini could not generate the guide. Check GOOGLE_API_KEY "
            "and the model's availability."
        ), 502

    if not text_description:
        app.logger.error("Google Gemini returned an empty description")
        return jsonify(error="Google Gemini returned an empty guide. Please try again."), 502

    try:
        audio_bytes = generate_speech(
            text_description, data["voiceId"], data["locale"]
        )
    except requests.RequestException:
        app.logger.exception("Murf speech generation request failed")
        return jsonify(
            error="Murf could not generate audio. Check MURF_API_KEY and the selected voice."
        ), 502

    if not audio_bytes:
        app.logger.error("Murf returned an empty audio response")
        return jsonify(error="Murf returned empty audio. Please try again."), 502

    encoded_audio = base64.b64encode(audio_bytes).decode("utf-8")
    return jsonify(description=text_description, audioBase64=encoded_audio)

if __name__ == "__main__":
    app.run(debug=True)