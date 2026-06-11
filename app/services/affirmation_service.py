import logging
from .ai_service import generate_personalized_affirmation

logger = logging.getLogger("bonded.affirmations")

async def get_personalized_affirmation(
    user_name: str,
    mood_history: list,
    reflection_history: list,
    in_separation: bool
) -> str:
    try:
        logger.info(f"Generating personalized affirmation for {user_name}")
        new_text = await generate_personalized_affirmation(
            user_name=user_name,
            mood_history=mood_history,
            reflection_history=reflection_history,
            in_separation=in_separation
        )
        return new_text
        
    except Exception as e:
        logger.error(f"Error in get_personalized_affirmation: {e}")
        # Fallback return in case of failure to still serve user
        import random
        return random.choice([
            "Love grows stronger when you choose understanding every day.",
            "Growth begins with small moments of honesty. Be patient with yourself."
        ])
