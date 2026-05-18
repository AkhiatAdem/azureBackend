import json
import logging
from django.conf import settings
from core.models import Movie, Screening

logger = logging.getLogger(__name__)


def _build_context():
    """Fetch movies and screenings from DB and format as readable text."""
    movies = list(Movie.objects.prefetch_related('genres').all())
    screenings = Screening.objects.select_related('movie', 'room').all()

    movies_context = "\n".join([
        f"- {m.title} ({m.duration_minutes}m, {', '.join([g.name for g in m.genres.all()])}): {m.description}"
        for m in movies
    ]) or "No movies available."

    screenings_context = "\n".join([
        f"- {s.movie.title} in {s.room.name} on {s.date} at {s.start_time}"
        for s in screenings
    ]) or "No screenings available."

    return movies_context, screenings_context, movies


def _build_system_prompt(movies_context, screenings_context):
    return f"""You are a cinema assistant. Help users discover movies, check schedules, and guide them to book tickets. Only use provided data. Do not invent information. Be concise and helpful.

Available Movies:
{movies_context}

Available Screenings:
{screenings_context}

CRITICAL: If the user indicates they want to book, reserve, or buy tickets for a specific movie, you MUST respond with a JSON object in this exact format:
{{
  "reply": "Your conversational response",
  "action": "redirect_booking",
  "movie": "Exact Movie Title"
}}
Otherwise, respond with a JSON object in this exact format:
{{
  "reply": "Your conversational response",
  "action": "none",
  "movie": null
}}

ALWAYS respond in valid JSON. Never output raw text outside the JSON.
"""


def _mock_response(user_message, movies, reason="Offline mode"):
    """Fallback response when AI is unavailable."""
    reply_text = f"I'm your cinema assistant (currently in offline mode: {reason}). I can still help with basic questions!"
    action = "none"
    movie_title = None

    lower_msg = user_message.lower()
    if any(word in lower_msg for word in ["book", "reserve", "ticket"]):
        for m in movies:
            if m.title.split(':')[0].lower() in lower_msg or m.title.lower() in lower_msg:
                action = "redirect_booking"
                movie_title = m.title
                reply_text = f"Taking you to book tickets for {m.title}!"
                break
        if action == "none":
            reply_text = "Which movie would you like to book tickets for?"

    return {"reply": reply_text, "action": action, "movie": movie_title}


def get_chatbot_response(user_message):
    """Main entry point. Returns a dict with 'reply', 'action', and 'movie'."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()

    if api_key:
        logger.info(f"Gemini key loaded: {api_key[:8]}...")
    else:
        logger.warning("GEMINI_API_KEY is empty or not set in settings.")

    movies_context, screenings_context, movies = _build_context()

    if not api_key:
        return _mock_response(user_message, movies, reason="Missing GEMINI_API_KEY")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        system_prompt = _build_system_prompt(movies_context, screenings_context)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )

        content = response.text.strip()
        result = json.loads(content)

        return {
            "reply": result.get("reply", "I'm sorry, I couldn't understand that."),
            "action": result.get("action", "none"),
            "movie": result.get("movie", None),
        }

    except ImportError as e:
        logger.error(f"google-genai import failed: {e}")
        return _mock_response(user_message, movies, reason="google-genai package missing")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        return {"reply": "Sorry, I had trouble processing the AI response.", "action": "none", "movie": None}

    except Exception as e:
        error_str = str(e)
        logger.error(f"Gemini API call failed: {error_str}")

        if '429' in error_str or 'quota' in error_str.lower() or 'RESOURCE_EXHAUSTED' in error_str:
            return _mock_response(user_message, movies, reason="API quota exceeded")

        if '403' in error_str or 'API_KEY_INVALID' in error_str or 'auth' in error_str.lower():
            return _mock_response(user_message, movies, reason="Invalid API key")

        if 'SAFETY' in error_str or 'safety' in error_str.lower():
            return {"reply": "I'm sorry, I can't answer that. Please ask me about movies or schedules!", "action": "none", "movie": None}

        return _mock_response(user_message, movies, reason=f"API error: {error_str[:80]}")
