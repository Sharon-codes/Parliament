import asyncio
import os
from agent_tools import search_web

async def smoke_test_search():
    queries = [
        "iPhone 16 Release Date",
        "Who is the current Prime Minister of India",
        "SpaceX Starship latest launch",
    ]
    
    print("Initializing Multi-Layer Web Search Smoke Test (v81.0)...")
    for q in queries:
        print(f"\nQUERY: {q}")
        try:
            res = await search_web(q)
            print(f"RESULT:\n{res}")
        except Exception as e:
            print(f"FAILURE: {str(e)}")

if __name__ == "__main__":
    asyncio.run(smoke_test_search())
