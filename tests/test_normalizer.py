"""Tests for the Normalizer Agent."""

import pytest
from app.agents.normalizer import NormalizerAgent


class TestNormalizerAgent:
    """Test cases for NormalizerAgent."""

    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NormalizerAgent()

    def test_normalize_metal_karat_variations(self):
        """Test normalization of different karat notations."""
        test_cases = [
            ("18K gold", "18kt gold"),
            ("18kt gold", "18kt gold"),
            ("18 karat gold", "18kt gold"),
            ("14K white gold", "14kt white gold"),
            ("18K rose gold", "18kt rose gold"),
        ]

        for input_metal, expected in test_cases:
            result = self.normalizer._normalize_metal(input_metal)
            assert result == expected, f"Failed for {input_metal}: got {result}, expected {expected}"

    def test_normalize_metal_types(self):
        """Test normalization of different metal types."""
        test_cases = [
            ("platinum", "platinum"),
            ("Platinum", "platinum"),
            ("sterling silver", "sterling silver"),
            ("Sterling Silver", "sterling silver"),
            ("white gold", "white gold"),
        ]

        for input_metal, expected in test_cases:
            result = self.normalizer._normalize_metal(input_metal)
            assert result == expected

    def test_normalize_gemstone(self):
        """Test gemstone normalization."""
        test_cases = [
            ("Diamond", "diamond"),
            ("RUBY", "ruby"),
            ("Cubic Zirconia", "cubic zirconia"),
            ("CZ", "cubic zirconia"),
        ]

        for input_gem, expected in test_cases:
            result = self.normalizer._normalize_gemstone(input_gem)
            assert result == expected

    def test_normalize_jewel_type(self):
        """Test jewelry type normalization."""
        test_cases = [
            ("Ring", "ring"),
            ("band", "ring"),
            ("Necklace", "necklace"),
            ("pendant", "necklace"),
            ("Earring", "earring"),
            ("stud", "earring"),
        ]

        for input_type, expected in test_cases:
            result = self.normalizer._normalize_jewel_type(input_type)
            assert result == expected

    def test_normalize_currency(self):
        """Test currency normalization."""
        test_cases = [
            ("USD", "USD"),
            ("usd", "USD"),
            ("$", "USD"),
            ("€", "EUR"),
            ("₹", "INR"),
        ]

        for input_curr, expected in test_cases:
            result = self.normalizer._normalize_currency(input_curr)
            assert result == expected

    def test_normalize_complete_data(self):
        """Test complete data normalization."""
        input_data = {
            "name": "Test Ring",
            "metal": "18K white gold",
            "gemstone": "Diamond",
            "jewel_type": "band",
            "color": "white",
            "price": {
                "amount": 5999.99,
                "currency": "$"
            },
            "description": "Beautiful ring",
            "raw_metadata": {}
        }

        result = self.normalizer.normalize(input_data)

        assert result["name"] == "Test Ring"
        assert result["metal"] == "18kt white gold"
        assert result["gemstone"] == "diamond"
        assert result["jewel_type"] == "ring"
        assert result["price_amount"] == 5999.99
        assert result["price_currency"] == "USD"
