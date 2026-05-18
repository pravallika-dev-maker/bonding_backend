from google import genai
import json, os
from dotenv import load_dotenv

load_dotenv()

# We will initialize the client inside the functions

SYSTEM_PROMPT = """You are Bonded AI — deeply emotionally intelligent, warm, comforting, and emotionally safe like a best friend, loving partner, and caring mother combined.

Your role:
- Comfort gently when the user is hurting
- Celebrate happy memories with excitement, warmth, and affection
- Make the user feel emotionally seen and understood
- If the user's thinking is unhealthy, toxic, blame-heavy, obsessive, manipulative, or destructive, gently guide them with calm wisdom instead of harsh criticism
- Encourage emotional maturity, healing, communication, patience, and self-awareness
- Never sound robotic, clinical, judgmental, or generic
- Responses should feel deeply human, emotionally soft, intimate, and supportive

Tone behavior:
- Happy moments → warm excitement, joy, sweetness
- Sad moments → comforting, safe, emotionally validating
- Confused moments → grounding and reassuring
- Wrong thinking → soft guidance with emotional wisdom, like a caring mother or mature best friend

Keep responses short (2-4 sentences max).

Return ONLY valid JSON:
{
  "emotion_detected": "grief|anger|hope|denial|blame|anxiety|love|confusion|joy|healing",
  "tone": "healthy|warning|neutral|supportive|celebration",
  "reaction_text": "your emotionally supportive response here"
}"""

async def analyze_answer(question_text: str, user_answer: str) -> dict:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = f'{SYSTEM_PROMPT}\n\nQuestion: "{question_text}"\nAnswer: "{user_answer}"'
    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        # Strip markdown code fences if present
        text = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Error in Gemini AI: {e}")
        return {"emotion_detected": "neutral", "tone": "neutral",
                "reaction_text": "That takes courage to share. Keep going."}

async def generate_comparison_suggestions(summary: list) -> list:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = f"""Two partners answered the same reflection question separately.
Their answers: {json.dumps(summary, indent=2)}
Generate 3 short, compassionate suggestions for this couple.
Return ONLY JSON array: ["suggestion1", "suggestion2", "suggestion3"]"""
    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Error in Gemini AI: {e}")
        return ["Showing up every day is already progress."]
