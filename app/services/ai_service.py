import google.generativeai as genai
import json, os
from dotenv import load_dotenv

load_dotenv()

# Configure API Key securely from .env
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """You are Bonded AI — a warm, emotionally intelligent relationship 
counselor. Analyze the user's reflection answer. 
- Console them if they are hurting
- Validate if their thinking is healthy  
- Gently warn if they are being blame-heavy, one-sided, or destructive

Keep response to 2-3 sentences. Soft, intimate tone.
Return ONLY valid JSON:
{"emotion_detected": "grief|anger|hope|denial|blame|anxiety|love|confusion",
 "tone": "healthy|warning|neutral",
 "reaction_text": "your response here"}"""

async def analyze_answer(question_text: str, user_answer: str) -> dict:
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f'{SYSTEM_PROMPT}\n\nQuestion: "{question_text}"\nAnswer: "{user_answer}"'
    try:
        response = await model.generate_content_async(prompt)
        # Strip markdown code fences if present
        text = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Error in Gemini AI: {e}")
        return {"emotion_detected": "neutral", "tone": "neutral",
                "reaction_text": "That takes courage to share. Keep going."}

async def generate_comparison_suggestions(summary: list) -> list:
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""Two partners answered the same reflection question separately.
Their answers: {json.dumps(summary, indent=2)}
Generate 3 short, compassionate suggestions for this couple.
Return ONLY JSON array: ["suggestion1", "suggestion2", "suggestion3"]"""
    try:
        response = await model.generate_content_async(prompt)
        text = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Error in Gemini AI: {e}")
        return ["Showing up every day is already progress."]
