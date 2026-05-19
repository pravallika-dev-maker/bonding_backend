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


async def evaluate_love_letter(letter_content: str) -> int:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = f"""Read the following letter written by someone to their partner during a separation.
Give it a 'love_score' from 0 to 100 based on how loving, constructive, forgiving, and emotionally safe it is.
- High score (80-100): Full of love, hope, appreciation, taking responsibility, emotional warmth.
- Medium score (40-79): Neutral, confused, or expressing hurt but willing to try.
- Low score (0-39): Blaming, toxic, angry, manipulative, or emotionally unsafe.

Letter: "{letter_content}"

Return ONLY valid JSON:
{{"love_score": 85}}"""
    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip().strip("```json").strip("```").strip()
        data = json.loads(text)
        return data.get("love_score", 0)
    except Exception as e:
        print(f"Error in Gemini AI Love Scoring: {e}")
        return 0

async def generate_journey_insights(partner_a_name: str, partner_b_name: str, data: dict) -> dict:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""You are an emotionally intelligent relationship guide — warm, caring, wise, and deeply human. 
You are reviewing the full emotional journey of a couple who just completed a separation period to grow and heal.

COUPLE: {partner_a_name} & {partner_b_name}

DATA COLLECTED DURING THEIR SEPARATION:

{partner_a_name}'s Reflection Answers & Emotions:
{json.dumps(data.get("partner_a_reflections", []), indent=2)}

{partner_b_name}'s Reflection Answers & Emotions:
{json.dumps(data.get("partner_b_reflections", []), indent=2)}

{partner_a_name}'s Mood History: {data.get("partner_a_moods", [])}
{partner_b_name}'s Mood History: {data.get("partner_b_moods", [])}

Days Both Completed Reflections Together: {data.get("shared_days", 0)}
Total Reflection Days Completed: {partner_a_name}: {data.get("partner_a_total_days", 0)}, {partner_b_name}: {data.get("partner_b_total_days", 0)}
Letters Written: {partner_a_name}: {data.get("partner_a_letters", 0)}, {partner_b_name}: {data.get("partner_b_letters", 0)}

---

Generate relationship insights by deeply analyzing all of the above. The insights should identify:
- emotional strengths in the relationship
- areas where both partners connect well
- recurring emotional gaps or misunderstandings
- unhealthy patterns if visible
- what {partner_a_name} can improve emotionally
- what {partner_b_name} can improve emotionally
- how both can better support each other

The response should feel emotionally intelligent, transparent, caring like a close best friend, wise and comforting. Never sound robotic, harsh, blaming, or clinical. Guide gently. Leave the couple with clarity, emotional awareness, encouragement, and a feeling that growth and healing are still possible.

Return ONLY valid JSON in exactly this format:
{{
  "coupleInsight": "One warm, deeply observant sentence about what you see between them as a couple.",
  "personalGrowths": [
    "An observation about {partner_a_name}'s emotional growth (positive, specific, genuine)",
    "An observation about {partner_b_name}'s emotional growth (positive, specific, genuine)",
    "Something both have shown together"
  ],
  "partnerAImprovement": "One gentle, wise suggestion for {partner_a_name} — caring, not blaming.",
  "partnerBImprovement": "One gentle, wise suggestion for {partner_b_name} — caring, not blaming.",
  "reflection": "A 2-3 sentence closing reflection that summarizes their journey with hope, warmth, and wisdom."
}}"""

    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        text = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(text)
    except Exception as e:
        print(f"Error in Gemini Journey Insights: {e}")
        return {
            "coupleInsight": "You both showed up — and that alone says something beautiful.",
            "personalGrowths": [
                "You've been honest with your emotions throughout this journey.",
                "You've been consistently present and thoughtful.",
                "Together, you are both choosing growth over comfort."
            ],
            "partnerAImprovement": "Try sharing your feelings a little earlier — before they become too heavy to carry alone.",
            "partnerBImprovement": "Try to listen without thinking about your response — just receive what they share.",
            "reflection": "Your relationship is slowly shifting from reaction to understanding. Even the smallest pauses you took created space for something better to grow between you."
        }
