import logging
import base64
import httpx
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class InferenceAgent:
    """Agent responsible for AI-powered visual attribute inference."""

    def __init__(self):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def infer_attributes(self, images: List[str], extracted_data: Dict) -> Optional[Dict[str, Any]]:
        """
        Infer visual attributes from product images using AI.

        Args:
            images: List of image URLs
            extracted_data: Previously extracted data for context

        Returns:
            Dictionary with inferred attributes, or None if product should be skipped
        """
        if not self.client or not images:
            logger.warning("No OpenAI client or images available for inference")
            return self._fallback_inference(extracted_data)

        try:
            # Use the first image for inference
            image_url = images[0]
            logger.info(f"Inferring attributes from image: {image_url}")

            # Download image and encode to base64 if it's a local file
            if image_url.startswith("http"):
                image_content = image_url
            else:
                # For local files, read and encode
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url)
                    image_bytes = response.content
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    image_content = f"data:image/jpeg;base64,{image_base64}"

            # Create prompt for vision model
            prompt = self._create_inference_prompt(extracted_data)

            # Call OpenAI Vision API
            response = await self.client.chat.completions.create(
                model=self.settings.ai_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_content}},
                        ],
                    }
                ],
                max_tokens=self.settings.ai_max_tokens,
                temperature=self.settings.ai_temperature,
            )

            # Parse response
            result_text = response.choices[0].message.content
            inferred = self._parse_inference_result(result_text)

            # Check if this is a valid specific product
            if inferred and inferred.get("is_valid_product") == False:
                logger.info(f"Product validation failed: {inferred.get('skip_reason', 'Generic product name')}")
                return None

            logger.info(f"Successfully inferred attributes: {inferred}")
            return inferred

        except Exception as e:
            logger.error(f"Error during AI inference: {str(e)}")
            return self._fallback_inference(extracted_data)

    def _create_inference_prompt(self, extracted_data: Dict) -> str:
        """Create a prompt for the vision model that combines inference and summarization."""
        product_name = extracted_data.get("name", "this jewelry item")
        metal = extracted_data.get("metal", "")
        price = extracted_data.get("price_amount", "")

        prompt = f"""First, validate if this is a SPECIFIC jewelry product by checking the product name: "{product_name}"

IMPORTANT - Product Name Validation:
- If the product name contains generic category terms like "all jewelry", "chains", "rings", "necklaces", "bracelets", "earrings", "collection", "shop all", "view all", etc., mark as INVALID
- Only SPECIFIC product names with unique identifiers, model numbers, or descriptive details should be marked as VALID
- Examples of INVALID names: "All Jewelry", "Shop Chains", "View All Rings", "Necklace Collection"
- Examples of VALID names: "Diamond Solitaire Ring 14K", "Vintage Pearl Necklace #12345", "Rose Gold Band with Sapphires"

If the product name is INVALID (too generic), respond with EXACTLY:
Valid Product: No
Skip Reason: Generic category name, not a specific product

If the product name is VALID (specific product), analyze this jewelry image and provide ALL of the following information:

Product Information:
- Name: {product_name}
- Metal: {metal if metal else 'unknown'}
- Price: {price if price else 'unknown'}

Please provide:
1. Valid Product: Yes
2. Jewelry Type: Identify the type (ring, necklace, earring, bracelet, etc.)
3. Gemstone: Identify the primary gemstone if visible (diamond, ruby, sapphire, emerald, pearl, etc.)
4. Gemstone Color: Describe the gemstone color (white, blue, red, green, etc.)
5. Metal Color: Identify the metal color (yellow gold, white gold, rose gold, silver, platinum, etc.)
6. Summary: A concise 1-2 sentence product summary that highlights the key features and appeal
7. Vibe: Classification from ONE of: wedding, engagement, casual, festive, formal, date-night, everyday, party

Please respond in this exact format:
Valid Product: [Yes or No]
Skip Reason: [reason if No, otherwise omit this line]
Jewelry Type: [type]
Gemstone: [gemstone or "none visible"]
Gemstone Color: [color or "n/a"]
Metal Color: [color]
Summary: [1-2 sentence summary]
Vibe: [single vibe word]

Be specific and concise."""

        return prompt

    def _parse_inference_result(self, result_text: str) -> Dict[str, Any]:
        """Parse the AI response into structured data including summary and vibe."""
        inferred = {
            "is_valid_product": True,
            "skip_reason": None,
            "jewelry_type": None,
            "gemstone": None,
            "gemstone_color": None,
            "metal_color": None,
            "summary": None,
            "vibe": "casual",
            "confidence": {}
        }

        try:
            lines = result_text.strip().split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()

                    # Check for product validation
                    if "valid product" in key:
                        value_lower = value.lower()
                        if "no" in value_lower:
                            inferred["is_valid_product"] = False
                        continue

                    # Check for skip reason
                    if "skip reason" in key:
                        inferred["skip_reason"] = value
                        continue

                    # Check for summary
                    if "summary" in key:
                        inferred["summary"] = value
                        continue

                    # Check for vibe
                    if "vibe" in key:
                        vibe_words = ["wedding", "engagement", "casual", "festive",
                                     "formal", "date-night", "everyday", "party"]
                        value_lower = value.lower()
                        for vibe in vibe_words:
                            if vibe in value_lower:
                                inferred["vibe"] = vibe
                                break
                        continue

                    value_lower = value.lower()
                    if value_lower and value_lower not in ["none visible", "n/a", "none", "unknown"]:
                        if "jewelry type" in key or ("type" in key and "valid" not in key and "vibe" not in key):
                            inferred["jewelry_type"] = value_lower
                            inferred["confidence"]["jewelry_type"] = 0.85
                        elif "gemstone" in key and "color" not in key:
                            inferred["gemstone"] = value_lower
                            inferred["confidence"]["gemstone"] = 0.80
                        elif "gemstone color" in key or "stone color" in key:
                            inferred["gemstone_color"] = value_lower
                            inferred["confidence"]["gemstone_color"] = 0.75
                        elif "metal color" in key or ("metal" in key and "color" not in key):
                            inferred["metal_color"] = value_lower
                            inferred["confidence"]["metal_color"] = 0.85

        except Exception as e:
            logger.error(f"Error parsing inference result: {str(e)}")

        return inferred

    def _fallback_inference(self, extracted_data: Dict) -> Dict[str, Any]:
        """
        Fallback inference using rule-based approach when AI is unavailable.

        Args:
            extracted_data: Extracted data to use for inference

        Returns:
            Dictionary with inferred attributes including summary and vibe
        """
        inferred = {
            "jewelry_type": extracted_data.get("jewel_type"),
            "gemstone": extracted_data.get("gemstone"),
            "gemstone_color": None,
            "metal_color": None,
            "summary": None,
            "vibe": "casual",
            "confidence": {}
        }

        # Try to infer metal color from metal type
        metal = extracted_data.get("metal", "")
        if metal:
            metal_lower = metal.lower()
            if "white" in metal_lower:
                inferred["metal_color"] = "white gold"
            elif "yellow" in metal_lower:
                inferred["metal_color"] = "yellow gold"
            elif "rose" in metal_lower or "pink" in metal_lower:
                inferred["metal_color"] = "rose gold"
            elif "silver" in metal_lower:
                inferred["metal_color"] = "silver"
            elif "platinum" in metal_lower:
                inferred["metal_color"] = "platinum"

        # Try to infer gemstone color from gemstone type
        gemstone = extracted_data.get("gemstone", "")
        if gemstone:
            gemstone_lower = gemstone.lower()
            gemstone_colors = {
                "diamond": "white",
                "ruby": "red",
                "sapphire": "blue",
                "emerald": "green",
                "pearl": "white",
                "amethyst": "purple",
                "topaz": "blue",
                "garnet": "red",
            }
            inferred["gemstone_color"] = gemstone_colors.get(gemstone_lower)

        # Generate simple summary
        name = extracted_data.get("name", "jewelry piece")
        jewel_type = inferred.get("jewelry_type", "jewelry")
        parts = []
        if jewel_type:
            parts.append(f"A beautiful {jewel_type}")
        else:
            parts.append("A beautiful jewelry piece")
        if metal:
            parts.append(f"crafted in {metal}")
        if gemstone:
            parts.append(f"featuring {gemstone}")
        inferred["summary"] = " ".join(parts) + "."

        # Determine vibe using rule-based approach
        name_lower = name.lower()
        jewel_type_lower = (jewel_type or "").lower()
        gemstone_lower = (gemstone or "").lower()

        # Wedding/Engagement indicators
        if any(word in name_lower for word in ["wedding", "bridal", "engagement"]):
            inferred["vibe"] = "wedding" if "wedding" in name_lower else "engagement"
        # Ring with diamond is likely engagement
        elif jewel_type_lower == "ring" and "diamond" in gemstone_lower:
            inferred["vibe"] = "engagement"
        # Festive indicators
        elif any(word in name_lower for word in ["festive", "celebration", "festival"]):
            inferred["vibe"] = "festive"
        # Formal indicators
        elif any(word in name_lower for word in ["formal", "gala", "elegant", "luxury"]):
            inferred["vibe"] = "formal"
        # Party indicators
        elif any(word in name_lower for word in ["party", "cocktail", "evening"]):
            inferred["vibe"] = "party"
        # Date night indicators
        elif any(word in name_lower for word in ["romantic", "date", "evening"]):
            inferred["vibe"] = "date-night"
        # Everyday/casual as default
        elif any(word in name_lower for word in ["everyday", "daily", "simple", "minimalist"]):
            inferred["vibe"] = "everyday"

        # Set lower confidence for fallback
        for key in inferred:
            if key != "confidence" and key not in ["summary", "vibe"] and inferred[key]:
                inferred["confidence"][key] = 0.50

        logger.info("Using fallback inference (rule-based)")
        return inferred
