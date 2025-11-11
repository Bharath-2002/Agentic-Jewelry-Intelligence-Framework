#!/usr/bin/env python3
"""
Development runner script for Agentic Jewelry Intelligence Framework.
"""

import sys
import subprocess
import argparse


def run_dev_server():
    """Run the development server with auto-reload."""
    print("Starting development server...")
    subprocess.run([
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info"
    ])


def run_migrations():
    """Run database migrations."""
    print("Running database migrations...")
    subprocess.run(["alembic", "upgrade", "head"])


def create_migration(message: str):
    """Create a new migration."""
    print(f"Creating migration: {message}")
    subprocess.run(["alembic", "revision", "--autogenerate", "-m", message])


def run_tests():
    """Run tests."""
    print("Running tests...")
    subprocess.run(["pytest", "-v"])


def install_deps():
    """Install dependencies."""
    print("Installing dependencies...")
    subprocess.run(["poetry", "install"])
    print("Installing Playwright browsers...")
    subprocess.run(["playwright", "install", "chromium"])


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Agentic Jewelry Intelligence Framework Runner")
    parser.add_argument(
        "command",
        choices=["dev", "migrate", "new-migration", "test", "install"],
        help="Command to run"
    )
    parser.add_argument(
        "-m", "--message",
        help="Migration message (for new-migration command)",
        default="Auto-generated migration"
    )

    args = parser.parse_args()

    if args.command == "dev":
        run_dev_server()
    elif args.command == "migrate":
        run_migrations()
    elif args.command == "new-migration":
        create_migration(args.message)
    elif args.command == "test":
        run_tests()
    elif args.command == "install":
        install_deps()


if __name__ == "__main__":
    main()
