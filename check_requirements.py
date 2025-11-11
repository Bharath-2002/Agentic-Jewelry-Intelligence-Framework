#!/usr/bin/env python3
"""
Script to check if all system requirements are met.
"""

import sys
import subprocess
import shutil
from pathlib import Path


def check_command(command: str, name: str) -> bool:
    """Check if a command is available."""
    if shutil.which(command):
        print(f"✓ {name} is installed")
        return True
    else:
        print(f"✗ {name} is NOT installed")
        return False


def check_python_version() -> bool:
    """Check Python version."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} (>= 3.11)")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (need >= 3.11)")
        return False


def check_env_file() -> bool:
    """Check if .env file exists."""
    if Path(".env").exists():
        print("✓ .env file exists")
        return True
    else:
        print("✗ .env file NOT found (copy from .env.template)")
        return False


def check_docker_running() -> bool:
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ Docker is running")
            return True
        else:
            print("✗ Docker is NOT running")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("✗ Docker is NOT running or not installed")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("Agentic Jewelry Intelligence Framework - Requirements Check")
    print("=" * 60)
    print()

    checks = []

    print("System Requirements:")
    print("-" * 60)
    checks.append(check_python_version())
    checks.append(check_command("poetry", "Poetry"))
    checks.append(check_command("docker", "Docker"))
    checks.append(check_command("docker-compose", "Docker Compose"))

    print()
    print("Configuration:")
    print("-" * 60)
    checks.append(check_env_file())

    print()
    print("Services (optional for local dev):")
    print("-" * 60)
    check_docker_running()

    print()
    print("=" * 60)

    if all(checks):
        print("✓ All requirements met! You're ready to go.")
        print()
        print("Next steps:")
        print("  1. Review .env configuration")
        print("  2. Run: docker-compose up --build")
        print("  3. Visit: http://localhost:8000/docs")
        return 0
    else:
        print("✗ Some requirements are missing. Please install them first.")
        print()
        print("Installation help:")
        print("  - Python 3.11+: https://www.python.org/downloads/")
        print("  - Poetry: pip install poetry")
        print("  - Docker: https://docs.docker.com/get-docker/")
        return 1


if __name__ == "__main__":
    sys.exit(main())
