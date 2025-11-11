"""Setup script for Agentic Jewelry Intelligence Framework."""

from setuptools import setup, find_packages

setup(
    name="agentic-jewelry-intelligence",
    version="0.1.0",
    description="Autonomous jewelry product scraping and intelligence framework",
    author="Thuli Studios",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        # Dependencies are managed by Poetry
        # See pyproject.toml
    ],
)
