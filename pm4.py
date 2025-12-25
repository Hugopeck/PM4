#!/usr/bin/env python3
"""
PM4 - Polymarket CLOB Market Maker

Usage:
    pip install -r requirements.txt
    python pm4.py config.json
"""
import sys

# Import and run the main module
from pm4.main import _amain
import asyncio

if __name__ == "__main__":
    asyncio.run(_amain())