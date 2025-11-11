import logging
from typing import Dict, Optional, Any
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SummarizerAgent:
    """Agent responsible for generating summaries and vibe classifications."""

    def __init__(self):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def generate_summary_and_vibe(
        self,
        normalized_data: Dict[str, Any],
        inferred_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate product summary and vibe classification.

        Args:
            normalized_data: Normalized product data
            inferred_data: AI-inferred attributes

        Returns:
            Dictionary with summary and vibe
        """
        if not self.client:
            logger.warning("No OpenAI client available, using rule-based summarization")
            return self._fallback_summarization(normalized_data, inferred_data)

        try:
            # Create prompt
            prompt = self._create_summary_prompt(normalized_data, inferred_data)

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model="gpt-4",  # Use regular GPT-4 for text generation
                messages=[
                    {
                        "role": "system",
                        "content": "You are a jewelry expert who creates concise, appealing product descriptions and classifies jewelry by occasion."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=200,
                temperature=0.7,
            )

            # Parse response
            result_text = response.choices[0].message.content
            parsed = self._parse_summary_result(result_text)

            logger.info(f"Generated summary and vibe: {parsed['vibe']}")
            return parsed

        except Exception as e:
            logger.error(f"Error during summarization: {str(e)}")
            return self._fallback_summarization(normalized_data, inferred_data)

    def _create_summary_prompt(self, normalized_data: Dict, inferred_data: Dict) -> str:
        """Create a prompt for summary generation."""
        name = normalized_data.get("name", "Unknown")
        jewel_type = inferred_data.get("jewelry_type") or normalized_data.get("jewel_type", "jewelry")
        metal = normalized_data.get("metal") or inferred_data.get("metal_color", "")
        gemstone = inferred_data.get("gemstone") or normalized_data.get("gemstone", "")
        price = normalized_data.get("price_amount")

        prompt = f"""Given this jewelry product information:
- Name: {name}
- Type: {jewel_type}
- Metal: {metal}
- Gemstone: {gemstone}
- Price: {price}

Please provide:
1. A concise 1-2 sentence product summary that highlights the key features and appeal
2. A vibe/occasion classification from: wedding, engagement, casual, festive, formal, date-night, everyday, party

Respond in this format:
Summary: [your 1-2 sentence summary]
Vibe: [single vibe word from the list above]"""

        return prompt

    def _parse_summary_result(self, result_text: str) -> Dict[str, str]:
        """Parse the AI response."""
        result = {
            "summary": "",
            "vibe": "casual"
        }

        try:
            lines = result_text.strip().split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()

                    if "summary" in key:
                        result["summary"] = value
                    elif "vibe" in key:
                        # Extract just the vibe word
                        vibe_words = ["wedding", "engagement", "casual", "festive",
                                     "formal", "date-night", "everyday", "party"]
                        value_lower = value.lower()
                        for vibe in vibe_words:
                            if vibe in value_lower:
                                result["vibe"] = vibe
                                break

        except Exception as e:
            logger.error(f"Error parsing summary result: {str(e)}")

        return result

    def _fallback_summarization(
        self,
        normalized_data: Dict[str, Any],
        inferred_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Fallback rule-based summarization when AI is unavailable.

        Args:
            normalized_data: Normalized product data
            inferred_data: Inferred attributes

        Returns:
            Dictionary with summary and vibe
        """
        name = normalized_data.get("name", "jewelry piece")
        jewel_type = inferred_data.get("jewelry_type") or normalized_data.get("jewel_type", "jewelry")
        metal = normalized_data.get("metal") or inferred_data.get("metal_color", "")
        gemstone = inferred_data.get("gemstone") or normalized_data.get("gemstone", "")

        # Generate simple summary
        parts = []

        if jewel_type:
            parts.append(f"A beautiful {jewel_type}")
        else:
            parts.append("A beautiful jewelry piece")

        if metal:
            parts.append(f"crafted in {metal}")

        if gemstone:
            parts.append(f"featuring {gemstone}")

        summary = " ".join(parts) + "."

        # Determine vibe based on rules
        vibe = self._determine_vibe_rule_based(normalized_data, inferred_data)

        logger.info("Using fallback summarization (rule-based)")
        return {
            "summary": summary,
            "vibe": vibe
        }

    def _determine_vibe_rule_based(
        self,
        normalized_data: Dict[str, Any],
        inferred_data: Dict[str, Any]
    ) -> str:
        """Determine vibe using rule-based approach."""
        name = normalized_data.get("name", "").lower()
        jewel_type = (inferred_data.get("jewelry_type") or normalized_data.get("jewel_type", "")).lower()
        gemstone = (inferred_data.get("gemstone") or normalized_data.get("gemstone", "")).lower()

        # Wedding/Engagement indicators
        if any(word in name for word in ["wedding", "bridal", "engagement"]):
            return "wedding" if "wedding" in name else "engagement"

        # Ring with diamond is likely engagement
        if jewel_type == "ring" and "diamond" in gemstone:
            return "engagement"

        # Festive indicators
        if any(word in name for word in ["festive", "celebration", "festival"]):
            return "festive"

        # Formal indicators
        if any(word in name for word in ["formal", "gala", "elegant", "luxury"]):
            return "formal"

        # Party indicators
        if any(word in name for word in ["party", "cocktail", "evening"]):
            return "party"

        # Date night indicators
        if any(word in name for word in ["romantic", "date", "evening"]):
            return "date-night"

        # Everyday/casual as default
        if any(word in name for word in ["everyday", "daily", "simple", "minimalist"]):
            return "everyday"

        return "casual"
