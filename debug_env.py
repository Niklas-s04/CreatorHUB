#!/usr/bin/env python3
"""Quick debug - check .env file."""
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('JWT_SECRET='):
            value = line.split('=', 1)[1].strip()
            print(f"JWT_SECRET={value}")
            print(f"Length: {len(value)}")
            break
