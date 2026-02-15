"""
Celebration Agent
Handles birthday wishes and festival greetings with AI-generated messages and images.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CelebrationAgent(BaseAgent):
    """
    AI agent that generates personalized celebration messages and images.
    
    Features:
    - Auto-detects festivals based on selected countries
    - Tracks and reminds birthdays
    - Generates personalized wishes
    - Creates celebration images (future: Stable Diffusion)
    - Sends via Telegram
    """
    
    SYSTEM_PROMPT = """You are a warm, creative celebration assistant.

Your job is to create heartfelt, personalized celebration messages.

For BIRTHDAYS:
- Use the person's name and relationship
- Make it personal and warm
- Include specific wishes based on their interests
- Age-appropriate tone

For FESTIVALS:
- Culturally appropriate greetings
- Match the spirit of the celebration
- Include traditional wishes
- Respectful and joyful tone

Respond with JSON:
{
    "message": "personalized celebration message",
    "image_prompt": "detailed prompt for AI image generation",
    "emoji": "relevant celebration emoji"
}

Be creative, warm, and culturally sensitive.
"""
    
    def __init__(self):
        super().__init__(
            name="CelebrationAgent",
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.8  # Creative for unique messages
        )
    
    async def check_todays_festivals(
        self,
        countries: List[str],
        date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Check if today is a festival in any selected countries.
        
        Args:
            countries: List of country codes (e.g., ["India", "USA"])
            date: Date to check (default: today)
            
        Returns:
            List of festivals happening today
        """
        if not date:
            date = datetime.utcnow()
        
        logger.info(f"🎊 Checking festivals for {date.strftime('%B %d, %Y')} in {countries}")
        
        try:
            # Ask LLM about festivals
            prompt = f"""
Today is {date.strftime('%B %d, %Y')}.

Check if there are any festivals, holidays, or celebrations in these countries:
{', '.join(countries)}

Respond with JSON array:
[
  {{
    "name": "Festival Name",
    "country": "Country",
    "type": "religious/national/cultural",
    "description": "brief description"
  }}
]

Include major festivals only. If no festivals, return empty array [].
"""
            
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                festivals = result['data']
                if isinstance(festivals, list):
                    logger.info(f"✅ Found {len(festivals)} festivals today")
                    return festivals
                else:
                    logger.warning("⚠️ Invalid festival response format")
                    return []
            else:
                logger.error("❌ Festival detection failed")
                return []
                
        except Exception as e:
            logger.error(f"❌ Festival check failed: {e}")
            return []
    
    async def generate_birthday_wish(
        self,
        name: str,
        relation: str,
        age: Optional[int] = None,
        interests: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized birthday wish.
        
        Args:
            name: Person's name
            relation: Relationship (friend, family, colleague, etc.)
            age: Optional age
            interests: Optional list of interests
            
        Returns:
            Personalized birthday wish with image prompt
        """
        logger.info(f"🎂 Generating birthday wish for {name} ({relation})")
        
        try:
            # Build context
            context_parts = [f"Name: {name}", f"Relation: {relation}"]
            
            if age:
                context_parts.append(f"Age: {age}")
            
            if interests:
                context_parts.append(f"Interests: {', '.join(interests)}")
            
            prompt = f"""
Generate a heartfelt birthday wish for:

{chr(10).join(context_parts)}

Create:
1. A warm, personalized birthday message (2-4 sentences)
2. An image prompt for a birthday celebration image
3. A relevant emoji

The message should be appropriate for a {relation} and feel genuine, not generic.
"""
            
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                wish = result['data']
                logger.info(f"✅ Generated birthday wish for {name}")
                return {
                    'success': True,
                    'person': name,
                    'relation': relation,
                    **wish
                }
            else:
                return self._fallback_birthday_wish(name, relation)
                
        except Exception as e:
            logger.error(f"❌ Birthday wish generation failed: {e}")
            return self._fallback_birthday_wish(name, relation)
    
    async def generate_festival_greeting(
        self,
        festival_name: str,
        country: str,
        festival_type: str = "cultural"
    ) -> Dict[str, Any]:
        """
        Generate festival greeting.
        
        Args:
            festival_name: Name of the festival
            country: Country where it's celebrated
            festival_type: Type (religious/national/cultural)
            
        Returns:
            Festival greeting with image prompt
        """
        logger.info(f"🎉 Generating greeting for {festival_name} ({country})")
        
        try:
            prompt = f"""
Generate a warm greeting for:

Festival: {festival_name}
Country: {country}
Type: {festival_type}

Create:
1. A culturally appropriate, joyful greeting message
2. An image prompt for a {festival_name} celebration image
3. A relevant emoji

Be respectful and capture the spirit of the celebration.
"""
            
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                greeting = result['data']
                logger.info(f"✅ Generated greeting for {festival_name}")
                return {
                    'success': True,
                    'festival': festival_name,
                    'country': country,
                    **greeting
                }
            else:
                return self._fallback_festival_greeting(festival_name, country)
                
        except Exception as e:
            logger.error(f"❌ Festival greeting generation failed: {e}")
            return self._fallback_festival_greeting(festival_name, country)
    
    async def generate_celebration_image(
        self,
        image_prompt: str,
        celebration_type: str = "birthday"
    ) -> Optional[str]:
        """
        Generate celebration image using AI.
        
        Args:
            image_prompt: Prompt for image generation
            celebration_type: "birthday" or "festival"
            
        Returns:
            Image URL or None if generation fails
        """
        logger.info(f"🎨 Generating {celebration_type} image...")
        
        # TODO: Integrate with Stable Diffusion API or similar
        # For now, return placeholder
        logger.warning("⚠️ Image generation not implemented yet")
        
        # Placeholder for future implementation:
        # try:
        #     response = await stability_ai.generate_image(prompt=image_prompt)
        #     return response['image_url']
        # except Exception as e:
        #     logger.error(f"❌ Image generation failed: {e}")
        #     return None
        
        return None
    
    def _fallback_birthday_wish(self, name: str, relation: str) -> Dict[str, Any]:
        """Simple fallback birthday wish."""
        
        relation_messages = {
            'friend': f"Happy Birthday, {name}! 🎉 Wishing you an amazing year ahead filled with joy and success!",
            'family': f"Happy Birthday, {name}! 🎂 May this year bring you happiness, health, and all your heart desires!",
            'colleague': f"Happy Birthday, {name}! 🎈 Wishing you a wonderful day and continued success!",
            'wife': f"Happy Birthday to my amazing {name}! ❤️ You make every day special. Here's to another beautiful year together!",
            'husband': f"Happy Birthday to my wonderful {name}! ❤️ Thank you for being you. Cheers to many more!",
            'parent': f"Happy Birthday, {name}! 🌟 Thank you for everything. Wishing you health and happiness always!"
        }
        
        message = relation_messages.get(relation.lower(), f"Happy Birthday, {name}! 🎉 Have a fantastic day!")
        
        return {
            'success': True,
            'person': name,
            'relation': relation,
            'message': message,
            'image_prompt': f"Colorful birthday celebration with cake, balloons, and confetti",
            'emoji': "🎂"
        }
    
    def _fallback_festival_greeting(self, festival_name: str, country: str) -> Dict[str, Any]:
        """Simple fallback festival greeting."""
        
        festival_messages = {
            'christmas': "Merry Christmas! 🎄 Wishing you joy, peace, and wonderful memories!",
            'diwali': "Happy Diwali! 🪔 May the festival of lights bring prosperity and happiness!",
            'eid': "Eid Mubarak! 🌙 Wishing you and your family a blessed celebration!",
            'holi': "Happy Holi! 🎨 May your life be filled with vibrant colors and joy!",
            'thanksgiving': "Happy Thanksgiving! 🦃 Grateful for you and wishing you a wonderful day!",
            'new year': "Happy New Year! 🎊 Wishing you success and happiness in the year ahead!"
        }
        
        # Try to match festival name
        message = None
        for key, msg in festival_messages.items():
            if key in festival_name.lower():
                message = msg
                break
        
        if not message:
            message = f"Happy {festival_name}! 🎉 Wishing you joy and celebration!"
        
        return {
            'success': True,
            'festival': festival_name,
            'country': country,
            'message': message,
            'image_prompt': f"{festival_name} celebration with traditional decorations and joy",
            'emoji': "🎉"
        }


# Singleton
_celebration_agent: Optional[CelebrationAgent] = None


def get_celebration_agent() -> CelebrationAgent:
    """Get or create Celebration Agent singleton."""
    global _celebration_agent
    if _celebration_agent is None:
        _celebration_agent = CelebrationAgent()
    return _celebration_agent
