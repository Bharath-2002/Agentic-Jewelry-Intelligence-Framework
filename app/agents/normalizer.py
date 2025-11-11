import logging
import re
from typing import Dict, Any
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NormalizerAgent:
    """Agent responsible for normalizing extracted data."""

    def __init__(self):
        self.settings = settings

    def normalize(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize extracted data to canonical formats.

        Args:
            extracted_data: Raw extracted data

        Returns:
            Normalized data dictionary
        """
        normalized = {
            "name": extracted_data.get("name", "Unknown Product"),
            "metal": self._normalize_metal(extracted_data.get("metal")),
            "gemstone": self._normalize_gemstone(extracted_data.get("gemstone")),
            "jewel_type": self._normalize_jewel_type(extracted_data.get("jewel_type")),
            "color": self._normalize_color(extracted_data.get("color")),
            "price_amount": extracted_data.get("price", {}).get("amount"),
            "price_currency": self._normalize_currency(extracted_data.get("price", {}).get("currency")),
            "description": extracted_data.get("description"),
            "raw_metadata": extracted_data.get("raw_metadata", {}),
        }

        logger.info(f"Normalized data for: {normalized['name']}")
        return normalized

    def _normalize_metal(self, metal: str) -> str:
        """Normalize metal type to canonical format."""
        if not metal:
            return None

        metal_lower = metal.lower()

        # Normalize karat notation
        if "k" in metal_lower or "kt" in metal_lower or "karat" in metal_lower:
            # Extract karat number
            karat_match = re.search(r'(\d+)\s*k', metal_lower)
            if karat_match:
                karat = karat_match.group(1)

                # Determine gold type
                if "white" in metal_lower:
                    return f"{karat}kt white gold"
                elif "rose" in metal_lower or "pink" in metal_lower:
                    return f"{karat}kt rose gold"
                elif "yellow" in metal_lower:
                    return f"{karat}kt yellow gold"
                else:
                    return f"{karat}kt gold"

        # Normalize other metals
        metal_map = {
            "platinum": "platinum",
            "palladium": "palladium",
            "silver": "silver",
            "sterling silver": "sterling silver",
            "titanium": "titanium",
            "stainless steel": "stainless steel",
            "white gold": "white gold",
            "yellow gold": "yellow gold",
            "rose gold": "rose gold",
            "pink gold": "rose gold",
            "gold": "gold",
        }

        for key, value in metal_map.items():
            if key in metal_lower:
                return value

        return metal

    def _normalize_gemstone(self, gemstone: str) -> str:
        """Normalize gemstone type."""
        if not gemstone:
            return None

        gemstone_lower = gemstone.lower()

        # Normalize common gemstones
        gemstone_map = {
            "diamond": "diamond",
            "ruby": "ruby",
            "sapphire": "sapphire",
            "emerald": "emerald",
            "pearl": "pearl",
            "amethyst": "amethyst",
            "topaz": "topaz",
            "garnet": "garnet",
            "opal": "opal",
            "turquoise": "turquoise",
            "aquamarine": "aquamarine",
            "peridot": "peridot",
            "citrine": "citrine",
            "tanzanite": "tanzanite",
            "cubic zirconia": "cubic zirconia",
            "cz": "cubic zirconia",
            "moissanite": "moissanite",
        }

        for key, value in gemstone_map.items():
            if key in gemstone_lower:
                return value

        return gemstone

    def _normalize_jewel_type(self, jewel_type: str) -> str:
        """Normalize jewelry type."""
        if not jewel_type:
            return None

        jewel_type_lower = jewel_type.lower()

        # Normalize jewelry types
        type_map = {
            "ring": "ring",
            "band": "ring",
            "necklace": "necklace",
            "pendant": "necklace",
            "chain": "necklace",
            "earring": "earring",
            "stud": "earring",
            "hoop": "earring",
            "bracelet": "bracelet",
            "bangle": "bracelet",
            "cuff": "bracelet",
            "brooch": "brooch",
            "pin": "brooch",
            "anklet": "anklet",
            "watch": "watch",
        }

        for key, value in type_map.items():
            if key in jewel_type_lower:
                return value

        return jewel_type

    def _normalize_color(self, color: str) -> str:
        """Normalize color."""
        if not color:
            return None

        color_lower = color.lower().strip()

        # Normalize common color variations
        color_map = {
            "white": "white",
            "yellow": "yellow",
            "rose": "rose",
            "pink": "rose",
            "black": "black",
            "blue": "blue",
            "green": "green",
            "red": "red",
            "purple": "purple",
            "silver": "silver",
            "gold": "gold",
        }

        for key, value in color_map.items():
            if key in color_lower:
                return value

        return color

    def _normalize_currency(self, currency: str) -> str:
        """Normalize currency code."""
        if not currency:
            return None

        currency_upper = currency.upper().strip()

        # Common currency codes
        valid_currencies = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "CHF"]

        if currency_upper in valid_currencies:
            return currency_upper

        # Try to map common variations
        currency_map = {
            "$": "USD",
            "DOLLAR": "USD",
            "DOLLARS": "USD",
            "€": "EUR",
            "EURO": "EUR",
            "EUROS": "EUR",
            "£": "GBP",
            "POUND": "GBP",
            "POUNDS": "GBP",
            "₹": "INR",
            "RUPEE": "INR",
            "RUPEES": "INR",
            "¥": "JPY",
            "YEN": "JPY",
        }

        for key, value in currency_map.items():
            if key in currency_upper:
                return value

        return currency
