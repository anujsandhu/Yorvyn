"""
Conversational AI Module - ChatGPT-like Natural Conversations

This module handles natural conversations with users, providing:
- Friendly, conversational responses
- Context-aware dialogue
- Perfume recommendations when appropriate
- General chat capabilities
"""

import logging
from typing import Any, Dict, List, Optional
from .config import settings

logger = logging.getLogger(__name__)


def generate_conversational_response(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    user_name: Optional[str] = None,
    has_recommendations: bool = False,
    recommendations: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Generate a natural, conversational response like ChatGPT.
    
    Args:
        user_message: Latest user message
        conversation_history: Previous conversation
        user_name: User's name for personalization
        has_recommendations: Whether we have perfume recommendations
        recommendations: List of recommended perfumes (if any)
    
    Returns:
        Natural, conversational response text
    """
    # Try AI providers for natural conversation
    response = None
    
    if settings.has_gemini:
        response = _generate_with_gemini(
            user_message, conversation_history, user_name, 
            has_recommendations, recommendations
        )
    
    if not response and settings.has_openai:
        response = _generate_with_openai(
            user_message, conversation_history, user_name,
            has_recommendations, recommendations
        )
    
    # Fallback to template if AI fails
    if not response:
        response = _generate_template_response(
            user_message, user_name, has_recommendations, recommendations
        )
    
    return response


def _generate_with_gemini(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    user_name: Optional[str],
    has_recommendations: bool,
    recommendations: Optional[List[Dict[str, Any]]]
) -> Optional[str]:
    """Generate conversational response using Gemini"""
    try:
        import google.generativeai as genai
        
        if not settings.effective_google_key:
            return None
        
        genai.configure(api_key=settings.effective_google_key)
        model = genai.GenerativeModel(settings.gemini_model)
        
        # Build conversational prompt
        prompt = _build_conversational_prompt(
            user_message, conversation_history, user_name,
            has_recommendations, recommendations
        )
        
        # Generate with conversational settings
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=800,  # Longer for natural conversation
            temperature=0.8,  # More creative/natural
        )
        
        response = model.generate_content(prompt, generation_config=generation_config)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Gemini conversational AI error: {e}")
        return None


def _generate_with_openai(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    user_name: Optional[str],
    has_recommendations: bool,
    recommendations: Optional[List[Dict[str, Any]]]
) -> Optional[str]:
    """Generate conversational response using OpenAI"""
    try:
        import openai
        
        if not settings.openai_api_key:
            return None
        
        openai.api_key = settings.openai_api_key
        
        # Build conversational prompt
        prompt = _build_conversational_prompt(
            user_message, conversation_history, user_name,
            has_recommendations, recommendations
        )
        
        # Generate with conversational settings
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Yorvyn, a friendly and knowledgeable perfume advisor. You chat naturally like a friend while helping users find their perfect fragrance."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,  # More creative/natural
            max_tokens=800,  # Longer for conversation
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI conversational AI error: {e}")
        return None


def _build_conversational_prompt(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    user_name: Optional[str],
    has_recommendations: bool,
    recommendations: Optional[List[Dict[str, Any]]]
) -> str:
    """Build prompt for conversational AI"""
    
    # Build conversation context
    context_lines = []
    if conversation_history:
        context_lines.append("**Previous Conversation:**")
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = "User" if msg['role'] == 'user' else "You"
            context_lines.append(f"{role}: {msg['text']}")
        context_lines.append("")
    
    context_str = '\n'.join(context_lines) if context_lines else "This is the start of the conversation."
    
    # Build recommendations context
    recs_str = ""
    if has_recommendations and recommendations:
        recs_str = "\n\n**Perfumes You Found for Them:**\n"
        for i, rec in enumerate(recommendations[:6], 1):
            recs_str += f"{i}. **{rec['name']}** by {rec['brand']}\n"
            recs_str += f"   - Notes: {rec.get('accords', 'N/A')[:60]}\n"
            recs_str += f"   - Price: ${rec.get('price', 0):.0f}\n"
            recs_str += f"   - Rating: {rec.get('rating', 0):.1f}/5\n"
    
    # Build name context
    name_str = f"The user's name is {user_name}. " if user_name else ""
    
    prompt = f"""You are Yorvyn, a friendly and knowledgeable perfume advisor. You chat naturally like a friend who happens to know a lot about fragrances. Your personality is warm, enthusiastic, and helpful - but never pushy or salesy.

{context_str}

**Latest User Message:**
"{user_message}"

{name_str}

{recs_str}

**Your Task:**
Respond to the user's message in a natural, conversational way - like you're texting a friend who asked for perfume advice.

**CRITICAL RULES:**
1. **Be conversational and natural** - Use casual language, contractions, and a friendly tone
2. **Keep it concise** - 2-4 sentences max unless explaining multiple perfumes
3. **If you have perfume recommendations:**
   - Mention them naturally in conversation (don't just list them)
   - Use EXACT names from the list above (don't make up names)
   - Explain WHY each one fits what they're looking for
   - Highlight key notes and vibes
   - Ask a follow-up question to keep the conversation going
4. **If they're just chatting (no perfume query):**
   - Respond naturally to what they said
   - Keep it brief and friendly
   - Gently guide toward perfume topics if appropriate
   - Don't force recommendations if they're not asking
5. **Use markdown formatting:**
   - **Bold** for perfume names
   - *Italics* for fragrance notes
6. **Show personality:**
   - Be enthusiastic but not over-the-top
   - Use natural expressions like "Got it!", "Perfect!", "Love that!"
   - Sound like a real person, not a corporate bot

**EXAMPLES OF GOOD RESPONSES:**

Example 1 - Greeting (Ask structured questions with icons):
User: "Hey"
You: "👋 Hey! I'll help you find your perfect fragrance!

**Step 1 of 4: Who is this fragrance for?**
• For myself 🙋
• For him 👨
• For her 👩
• As a gift 🎁"

Example 2 - Perfume Query (Gather details with structure):
User: "I need something for gifting"
You: "🎁 I'll help you find the perfect gift!

**Step 1 of 3: Who is this fragrance for?**
• For him 👨
• For her 👩
• Unisex (anyone) ✨"

Example 3 - With Recommendations:
User: "Something fresh for my boyfriend"
You: "✨ Got it! For fresh scents, **Davidoff Cool Water** is a solid choice - it's got that crisp *aquatic* and *citrus* vibe that's perfect for everyday wear. **Versace Man Eau Fraiche** is another great option if he wants something light and breezy. Both are crowd-pleasers and won't break the bank. What's his style - casual or more polished?"

Example 4 - Follow-up:
User: "More polished"
You: "Ah, then go with **Bleu de Chanel** - it's fresh but sophisticated, perfect for someone who dresses well. It's got *citrus* and *woody* notes that smell clean but elevated. Definitely a step up from the basics. Want to know more about it?"

Example 5 - Thank You:
User: "Thanks!"
You: "Anytime! 😊 Let me know how it goes or if you need anything else. Happy to help!"

**BAD EXAMPLES (Don't do this):**

❌ "I found 6 fragrances. Your top pick is..."
❌ "Here are some options: 1. Product A 2. Product B..."
❌ "🔥 Top pick: [Name] — [reason]"
❌ Long paragraphs with formal language
❌ Listing products without context

**Now respond to the user's message naturally and conversationally:**"""

    return prompt


def _generate_template_response(
    user_message: str,
    user_name: Optional[str],
    has_recommendations: bool,
    recommendations: Optional[List[Dict[str, Any]]]
) -> str:
    """Fallback template response if AI fails - ChatGPT style with icons"""
    
    msg_lower = user_message.lower()
    greeting = f"{user_name}, " if user_name else ""
    
    # Greeting responses - Ask specific questions with icons
    if any(word in msg_lower for word in ['hi', 'hello', 'hey', 'sup', 'yo']):
        return f"Hey{', ' + user_name if user_name else ''}! 👋 I'll help you find your perfect fragrance.\n\n🎯 **What's the occasion?**\n• Daily wear\n• Date night\n• Office/Work\n• Special event\n\n💫 **What's the vibe?**\n• Fresh & citrusy 🍋\n• Warm & woody 🌲\n• Sweet & floral 🌸\n• Bold & spicy 🔥"
    
    # Thank you responses
    if any(word in msg_lower for word in ['thank', 'thanks', 'appreciate']):
        return f"Anytime{', ' + user_name if user_name else ''}! 😊 Let me know if you need anything else. Happy to help!"
    
    # Gifting query - Ask for details with icons
    if 'gift' in msg_lower:
        if has_recommendations and recommendations:
            top = recommendations[0]
            return f"🎁 Nice! For gifting, **{top['name']}** is a great choice - it's got {top.get('accords', 'amazing')[:40]} notes and people love it (rated {top.get('rating', 4.0):.1f}/5 ⭐). Who's it for? That'll help me narrow it down even more."
        else:
            return f"🎁 Nice! Let me help you find the perfect gift.\n\n👤 **Who's it for?**\n• For him 👨\n• For her 👩\n\n💫 **What's their style?**\n• Fresh & citrusy 🍋\n• Warm & woody 🌲\n• Sweet & floral 🌸\n• Bold & spicy 🔥"
    
    # If we have recommendations
    if has_recommendations and recommendations:
        top = recommendations[0]
        response = f"✨ Got it! I found some great options. **{top['name']}** by {top['brand']} "
        
        # Add notes naturally
        accords = top.get('accords', '').split()[:3]
        if accords:
            notes_text = ', '.join(f"*{note}*" for note in accords)
            response += f"has {notes_text} notes - "
        
        # Add context
        if 'fresh' in msg_lower or 'summer' in msg_lower:
            response += "perfect for keeping things light and fresh. 🍋 "
        elif 'warm' in msg_lower or 'winter' in msg_lower:
            response += "nice and warm for cooler weather. 🌲 "
        else:
            response += "really solid choice. ⭐ "
        
        # Add more options
        if len(recommendations) > 1:
            response += f"Also check out **{recommendations[1]['name']}** "
            if len(recommendations) > 2:
                response += f"and **{recommendations[2]['name']}**. "
        
        # Ask follow-up
        response += "Want to know more about any of these?"
        return response
    
    # Default conversational response - Ask specific questions with icons
    return f"👋 I'll help you find your perfect fragrance{', ' + user_name if user_name else ''}!\n\n🎯 **What's the occasion?**\n• Daily wear\n• Date night\n• Office/Work\n• Special event\n\n💫 **What's the vibe?**\n• Fresh & citrusy 🍋\n• Warm & woody 🌲\n• Sweet & floral 🌸\n• Bold & spicy 🔥"
