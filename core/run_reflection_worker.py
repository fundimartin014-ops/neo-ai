#!/usr/bin/env python3
"""
run_reflection_worker.py

Background self-reflection worker.
Run this in a SECOND terminal window while neo_core runs.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from neo.core.reasoning_memory import ReasoningMemory
from neo.core.reflection_loop import ReflectionLoop
from neo.llm_clients import OllamaClient  # your existing client


async def main():
    llm = OllamaClient(base_url="http://localhost:11434")
    memory = ReasoningMemory("neo_reasoning.db")
    
    loop = ReflectionLoop(llm, memory, config={
        'reflection_model': 'qwen2.5:7b',
        'min_chains': 5,
        'interval_turns': 999999,  # Manual only on Windows
    })
    
    print("=" * 60)
    print("  NEO REFLECTION WORKER")
    print("=" * 60)
    print("Press ENTER to trigger reflection")
    print("Type 'auto' to enable automatic mode")
    print("Type 'quit' to exit")
    print("-" * 60)
    
    turn_counter = 0
    
    while True:
        cmd = input("\n[reflect] > ").strip().lower()
        
        if cmd == 'quit':
            break
        elif cmd == 'auto':
            print("Auto-reflection enabled. Checking every 5 minutes...")
            while True:
                turn_counter += 1
                result = await loop.check_and_reflect(turn_counter, min_unresolved=3)
                if result:
                    print(f"\n[{time.strftime('%H:%M:%S')}] Reflection complete:")
                    print(f"  Chains: {result.chains_reviewed}")
                    print(f"  Insights: {len(result.findings)}")
                    for f in result.findings[:3]:
                        print(f"  - {f.finding_type}: {f.description[:60]}")
                await asyncio.sleep(300)
        else:
            # Manual reflection
            print("Running reflection...")
            result = await loop.reflect(force=True)
            if result:
                print(f"\nReflection complete:")
                print(f"  Chains reviewed: {result.chains_reviewed}")
                print(f"  Insights found: {len(result.findings)}")
                print(f"  Belief updates: {len(result.belief_revisions)}")
                print(f"\n  Summary: {result.overall_insight[:200]}")
                if result.action_items:
                    print(f"\n  Actions:")
                    for item in result.action_items[:3]:
                        print(f"    - {item}")
            else:
                print("No data to reflect on yet. Have more conversations first.")


if __name__ == '__main__':
    asyncio.run(main())