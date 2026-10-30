"""
entrypoint หลัก — รันจาก root ด้วย: python main.py
"""
import sys
import asyncio
sys.path.insert(0, ".")
from src.main import main

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
