#!/usr/bin/env python3
"""Asynchronous AI Search example using the Grip SDK.

https://grip.theshoaib.me/
"""

import asyncio
import sys
from grip import AsyncGrip


async def main():
    print("✨ Grip SDK: Asynchronous Streaming Search Example\n")

    client = AsyncGrip()
    query = "Breakthroughs in renewable energy battery storage"
    print(f"Streaming query: '{query}'...\n")

    try:
        print("[Answer] > ", end="", flush=True)
        async for chunk in client.search.stream(query):
            if chunk.event == "delta" and chunk.delta:
                sys.stdout.write(chunk.delta)
                sys.stdout.flush()
        sys.stdout.write("\n")
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
