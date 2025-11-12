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

        # First, try to find the main price container with more flexible patterns
        price_container = None
        price_container_selectors = [
            soup.find(class_=re.compile(r"product[_-]price|price[_-]wrapper|price[_-]widget|price[_-]container|price[_-]box", re.I)),
            soup.find("div", class_=re.compile(r"price", re.I)),
            soup.find("span", class_=re.compile(r"price", re.I)),
        ]

        for elem in price_container_selectors:
            if elem:
                price_container = elem
                break

        if price_container:
            # Extract sale price (look for <ins> tags or sale-related classes)
            # Enhanced patterns to include: final, current, selling, offer, now
            sale_elem = (
                price_container.find("ins") or
                price_container.find(class_=re.compile(r"sale[_-]?price|discount[_-]?price|special[_-]?price|final[_-]?price|current[_-]?price|selling[_-]?price|offer[_-]?price|now[_-]?price", re.I)) or
                price_container.find("span", class_=re.compile(r"sale|discount|special|final|current|selling|offer|now", re.I))
            )

            if sale_elem:
                sale_text = sale_elem.get_text()
                price_data["sale_price"] = self._parse_price_amount(sale_text)
                if not price_data["currency"]:
                    price_data["currency"] = self._extract_currency(sale_text)

            # Extract original/MRP price (look for <del> tags, strike-through, or mrp-related classes)
            # Enhanced patterns to include: strike, strikethrough, was, compare
            original_elem = (
                price_container.find("del") or
                price_container.find("s") or
                price_container.find(class_=re.compile(r"mrp|original[_-]?price|regular[_-]?price|was[_-]?price|strike|compare[_-]?price", re.I)) or
                price_container.find("span", class_=re.compile(r"mrp|original|regular|strike|was|compare", re.I))
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

        # Last resort: Extract all numeric values from price-related elements
        if not price_data["amount"]:
            all_prices = self._extract_all_prices_fallback(soup)
            if all_prices:
                # Use the first valid price found
                price_data["amount"] = all_prices[0]["amount"]
                price_data["currency"] = all_prices[0]["currency"]
                # If we found multiple prices, assume first is sale/final, second is original
                if len(all_prices) > 1:
                    price_data["sale_price"] = all_prices[0]["amount"]
                    price_data["original_price"] = all_prices[1]["amount"]

        # Try to get currency from schema
        if not price_data["currency"]:
            currency_elem = soup.find(attrs={"itemprop": "priceCurrency"})
            if currency_elem:
                price_data["currency"] = currency_elem.get("content") or currency_elem.get_text()

        return price_data

    def _parse_price_amount(self, price_str: str) -> Optional[float]:
        """Parse price amount from string, extracting the first valid number.

        Handles various formats:
        - With spaces: "1 37 606" -> 137606
        - Indian format: "1,32,222" -> 132222
        - Western format: "1,234.56" -> 1234.56
        - EU format: "1.234,56" -> 1234.56
        """
        if not price_str:
            return None

        try:
            # Remove extra whitespace and normalize
            price_str = price_str.strip()

            # First, try to extract just the numeric part with separators
            # This pattern captures numbers with optional spaces, commas, and dots
            number_pattern = r'([\d\s.,]+)'
            match = re.search(number_pattern, price_str)

            if not match:
                return None

            cleaned = match.group(1).strip()

            # Remove spaces between digits (handles "1 37 606" -> "137606")
            cleaned = re.sub(r'\s+', '', cleaned)

            # Now determine the format and parse accordingly

            # Case 1: Both comma and dot present
            if ',' in cleaned and '.' in cleaned:
                # Determine which comes last (that's the decimal separator)
                last_comma_pos = cleaned.rfind(',')
                last_dot_pos = cleaned.rfind('.')

                if last_dot_pos > last_comma_pos:
                    # Dot is decimal separator (US/Indian format): 1,234.56
                    cleaned = cleaned.replace(',', '')
                else:
                    # Comma is decimal separator (EU format): 1.234,56
                    cleaned = cleaned.replace('.', '').replace(',', '.')

                return float(cleaned)

            # Case 2: Only comma present
            elif ',' in cleaned:
                # Check if it's decimal separator or thousands separator
                comma_split = cleaned.split(',')

                # If last part has exactly 2 digits, likely decimal (1234,56)
                if len(comma_split) == 2 and len(comma_split[1]) == 2:
                    cleaned = cleaned.replace(',', '.')
                # Multiple commas or Indian format (1,32,222) - remove all commas
                else:
                    cleaned = cleaned.replace(',', '')

                return float(cleaned)

            # Case 3: Only dot present
            elif '.' in cleaned:
                # Check if it's decimal separator or thousands separator
                dot_split = cleaned.split('.')

                # If last part has exactly 2 digits, likely decimal (1234.56)
                if len(dot_split) == 2 and len(dot_split[1]) == 2:
                    return float(cleaned)
                # Multiple dots or EU thousands format - remove all dots
                else:
                    cleaned = cleaned.replace('.', '')
                    return float(cleaned)

            # Case 4: No separators, just digits
            else:
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

    def _extract_all_prices_fallback(self, soup: BeautifulSoup) -> list:
        """
        Last resort: Extract all numeric values from any elements with price-related classes.
        Returns a list of dicts with amount and currency.
        """
        prices = []

        # Find all elements with price-related classes
        price_elements = soup.find_all(class_=re.compile(r"price|cost|amount|money", re.I))

        for elem in price_elements:
            # Skip elements that contain other price elements (to avoid duplicates)
            if elem.find(class_=re.compile(r"price|cost|amount|money", re.I)):
                continue

            text = elem.get_text()
            amount = self._parse_price_amount(text)

            if amount:
                currency = self._extract_currency(text)
                prices.append({
                    "amount": amount,
                    "currency": currency
                })

        # Also try finding elements with specific price-related attributes
        if not prices:
            for elem in soup.find_all(["span", "div", "p"], class_=True):
                classes = elem.get("class", [])
                class_str = " ".join(classes) if isinstance(classes, list) else classes

                # Check if any class contains price-related keywords
                if re.search(r"price|cost|amount|money", class_str, re.I):
                    text = elem.get_text()
                    amount = self._parse_price_amount(text)

                    if amount:
                        currency = self._extract_currency(text)
                        prices.append({
                            "amount": amount,
                            "currency": currency
                        })

        return prices

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
