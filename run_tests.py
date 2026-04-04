#!/usr/bin/env python3
"""Run pytest with proper environment setup."""
import os
import subprocess
import sys
from pathlib import Path

# Load .env.test
env_file = Path(__file__).parent / ".env.test"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                # Remove quotes
                value = value.strip('"\'')
                os.environ[key.strip()] = value
                
print("Environment loaded from .env.test")
print(f"JWT_SECRET length in env: {len(os.environ.get('JWT_SECRET', ''))}")

# Run pytest
result = subprocess.run([sys.executable, "-m", "pytest"] + sys.argv[1:])
sys.exit(result.returncode)
