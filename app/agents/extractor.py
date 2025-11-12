import logging
import re
from typing import Dict, Optional, Any
from bs4 import BeautifulSoup
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ExtractorAgent:
    """Agent responsible for extracting metadata from product pages."""

    def __init__(self):
        self.settings = settings

    def extract(self, product_data: Dict) -> Dict[str, Any]:
        """
        Extract structured metadata from raw product data.

        Args:
            product_data: Raw product data from crawler

        Returns:
            Dictionary with extracted metadata
        """
        html = product_data.get("html", "")
        soup = BeautifulSoup(html, 'lxml')

        extracted = {
            "name": self._extract_name(soup, product_data),
            "price": self._extract_price(soup),
            "metal": self._extract_metal(soup),
            "gemstone": self._extract_gemstone(soup),
            "jewel_type": self._extract_jewel_type(soup),
            "color": self._extract_color(soup),
            "description": self._extract_description(soup),
            "raw_metadata": self._extract_raw_metadata(soup),
        }

        logger.info(f"Extracted metadata for: {extracted['name']}")
        return extracted

    def _extract_name(self, soup: BeautifulSoup, product_data: Dict) -> str:
        """Extract product name."""
        # Try multiple strategies
        strategies = [
            # Schema.org
            lambda: soup.find(attrs={"itemprop": "name"}),
            # Common meta tags
            lambda: soup.find("meta", property="og:title"),
            lambda: soup.find("meta", attrs={"name": "title"}),
            # Common HTML elements
            lambda: soup.find("h1", class_=re.compile(r"product|title", re.I)),
            lambda: soup.find("h1"),
            # Page title as fallback
            lambda: product_data.get("title"),
        ]

        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    text = result.get("content") if hasattr(result, "get") and result.get("content") else result.get_text()
                    if text:
                        return text.strip()
            except:
                continue

        return "Unknown Product"

    def _extract_price(self, soup: BeautifulSoup) -> Dict[str, Optional[Any]]:
        """Extract price information including sale and original prices."""
        price_data = {
            "amount": None,
            "currency": None,
            "original_price": None,
            "sale_price": None
        }

        # First, try to find the main price container
        price_container = None
        price_container_selectors = [
            soup.find(class_=re.compile(r"product[_-]price|price[_-]wrapper", re.I)),
            soup.find("div", class_=re.compile(r"price", re.I)),
            soup.find("span", class_=re.compile(r"price", re.I)),
        ]

        for elem in price_container_selectors:
            if elem:
                price_container = elem
                break

        if price_container:
            # Extract sale price (look for <ins> tags or sale-related classes)
            sale_elem = (
                price_container.find("ins") or
                price_container.find(class_=re.compile(r"sale[_-]price|discount[_-]price|special[_-]price", re.I)) or
                price_container.find("span", class_=re.compile(r"sale|discount|special", re.I))
            )

            if sale_elem:
                sale_text = sale_elem.get_text()
                price_data["sale_price"] = self._parse_price_amount(sale_text)
                if not price_data["currency"]:
                    price_data["currency"] = self._extract_currency(sale_text)

            # Extract original/MRP price (look for <del> tags or mrp/original-related classes)
            original_elem = (
                price_container.find("del") or
                price_container.find(class_=re.compile(r"mrp|original[_-]price|regular[_-]price|was[_-]price", re.I)) or
                price_container.find("span", class_=re.compile(r"mrp|original|regular", re.I))
            )

            if original_elem:
                original_text = original_elem.get_text()
                price_data["original_price"] = self._parse_price_amount(original_text)
                if not price_data["currency"]:
                    price_data["currency"] = self._extract_currency(original_text)

            # Set the main amount (prefer sale price if available)
            price_data["amount"] = price_data["sale_price"] or price_data["original_price"]

        # Fallback: Try Schema.org
        if not price_data["amount"]:
            price_elem = soup.find(attrs={"itemprop": "price"})
            if price_elem:
                price_data["amount"] = self._parse_price_amount(price_elem.get("content") or price_elem.get_text())

        # Fallback: Try to extract from any price element
        if not price_data["amount"]:
            price_elem = soup.find(class_=re.compile(r"price|cost|amount", re.I))
            if price_elem:
                # Find the first span/div with money class or direct text
                money_elem = price_elem.find(class_=re.compile(r"money", re.I))
                if money_elem:
                    price_text = money_elem.get_text()
                else:
                    price_text = price_elem.get_text()

                price_data["amount"] = self._parse_price_amount(price_text)
                price_data["currency"] = self._extract_currency(price_text)

        # Try to get currency from schema
        if not price_data["currency"]:
            currency_elem = soup.find(attrs={"itemprop": "priceCurrency"})
            if currency_elem:
                price_data["currency"] = currency_elem.get("content") or currency_elem.get_text()

        return price_data

    def _parse_price_amount(self, price_str: str) -> Optional[float]:
        """Parse price amount from string, extracting the first valid number."""
        if not price_str:
            return None

        try:
            # Remove extra whitespace
            price_str = price_str.strip()

            # Look for number patterns (handles formats like: 1,234.56 or 1234.56 or 1.234,56)
            # Match patterns: optional digits with comma/dot separators
            patterns = [
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # US format: 1,234.56
                r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # EU format: 1.234,56
                r'(\d+(?:\.\d{2})?)',                  # Simple: 1234.56
                r'(\d+(?:,\d{2})?)',                   # Simple with comma: 1234,56
            ]

            for pattern in patterns:
                match = re.search(pattern, price_str)
                if match:
                    cleaned = match.group(1)
                    # Determine if comma is decimal separator or thousands separator
                    if ',' in cleaned and '.' in cleaned:
                        # Both present: assume comma is thousands separator (US format)
                        cleaned = cleaned.replace(',', '')
                    elif ',' in cleaned and cleaned.count(',') == 1 and len(cleaned.split(',')[1]) == 2:
                        # Single comma with 2 digits after: decimal separator (EU format)
                        cleaned = cleaned.replace(',', '.')
                    elif ',' in cleaned:
                        # Multiple commas or other: thousands separator
                        cleaned = cleaned.replace(',', '')

                    return float(cleaned)

            # Fallback: remove all non-numeric except first dot/comma
            cleaned = re.sub(r'[^\d.,]', '', price_str)
            cleaned = cleaned.replace(',', '')
            if cleaned:
                return float(cleaned)

        except Exception as e:
            logger.debug(f"Failed to parse price: {price_str}, error: {e}")
            return None

        return None

    def _extract_currency(self, text: str) -> Optional[str]:
        """Extract currency from text."""
        currency_symbols = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "₹": "INR",
            "¥": "JPY",
        }

        for symbol, code in currency_symbols.items():
            if symbol in text:
                return code

        # Check for currency codes
        currency_match = re.search(r'\b(USD|EUR|GBP|INR|JPY|AUD|CAD)\b', text, re.I)
        if currency_match:
            return currency_match.group(1).upper()

        return None

    def _extract_metal(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract metal type."""
        text = soup.get_text()

        # Common metal keywords
        metal_patterns = [
            r'\b(white\s+gold|yellow\s+gold|rose\s+gold|pink\s+gold)\b',
            r'\b(\d+K|\d+kt|\d+\s*karat)\s*(gold|white gold|yellow gold|rose gold)\b',
            r'\b(platinum|palladium|silver|sterling\s+silver)\b',
            r'\b(titanium|stainless\s+steel)\b',
        ]

        for pattern in metal_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(0).strip()

        return None

    def _extract_gemstone(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract gemstone type."""
        text = soup.get_text()

        # Common gemstone keywords
        gemstone_patterns = [
            r'\b(diamond|ruby|sapphire|emerald|pearl)\b',
            r'\b(amethyst|topaz|garnet|opal|turquoise)\b',
            r'\b(aquamarine|peridot|citrine|tanzanite)\b',
            r'\b(cubic\s+zirconia|CZ|moissanite)\b',
        ]

        for pattern in gemstone_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(0).strip()

        return None

    def _extract_jewel_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract jewelry type."""
        text = soup.get_text().lower()

        # Jewelry type keywords
        types = {
            "ring": ["ring", "band"],
            "necklace": ["necklace", "pendant", "chain"],
            "earring": ["earring", "stud", "hoop"],
            "bracelet": ["bracelet", "bangle", "cuff"],
            "brooch": ["brooch", "pin"],
            "anklet": ["anklet"],
            "watch": ["watch"],
        }

        for jewel_type, keywords in types.items():
            if any(keyword in text for keyword in keywords):
                return jewel_type

        return None

    def _extract_color(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract color information."""
        text = soup.get_text()

        # Common color keywords
        color_pattern = r'\b(white|yellow|rose|pink|black|blue|green|red|purple|silver|gold)\b'
        match = re.search(color_pattern, text, re.I)

        if match:
            return match.group(0).strip()

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product description."""
        # Try multiple strategies
        strategies = [
            lambda: soup.find(attrs={"itemprop": "description"}),
            lambda: soup.find("meta", property="og:description"),
            lambda: soup.find("meta", attrs={"name": "description"}),
            lambda: soup.find(class_=re.compile(r"description|details", re.I)),
        ]

        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    text = result.get("content") if hasattr(result, "get") and result.get("content") else result.get_text()
                    if text and len(text.strip()) > 20:
                        return text.strip()
            except:
                continue

        return None

    def _extract_raw_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract all available metadata for reference."""
        metadata = {}

        # Schema.org metadata
        for item in soup.find_all(attrs={"itemprop": True}):
            prop = item.get("itemprop")
            value = item.get("content") or item.get_text()
            if prop and value:
                metadata[f"schema_{prop}"] = value.strip()

        # Open Graph metadata
        for meta in soup.find_all("meta", property=re.compile(r"og:")):
            prop = meta.get("property")
            value = meta.get("content")
            if prop and value:
                metadata[prop] = value

        return metadata
