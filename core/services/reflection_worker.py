#!/usr/bin/env python3
"""
neo/services/reflection_worker.py

Background worker that runs reflection loops continuously.
"""

import asyncio
import argparse
import time
from neo.core.reasoning_memory import ReasoningMemory
from neo.core.reflection_loop import ReflectionLoop


async def run_worker(db_path: str, interval: int, min_chains: int, model: str):
    """Run reflection worker loop."""
    
    class LocalLLM:
        async def generate(self, prompt, **kwargs):
            import urllib.request
            import json
            req = urllib.request.Request(
                'http://ollama:11434/api/generate',
                data=json.dumps({
                    'model': kwargs.get('model', model),
                    'prompt': prompt,
                    'stream': False
                }).encode(),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())['response']
    
    llm = LocalLLM()
    memory = ReasoningMemory(db_path)
    loop = ReflectionLoop(llm, memory, config={
        'reflection_model': model,
        'min_chains': min_chains,
    })
    
    print(f"Reflection worker started. Checking every {interval}s.")
    print(f"Min chains for reflection: {min_chains}")
    
    turn_counter = 0
    while True:
        try:
            turn_counter += 1
            result = await loop.check_and_reflect(
                turn_count=turn_counter,
                min_unresolved=3
            )
            
            if result:
                print(f"[{time.strftime('%H:%M:%S')}] Reflection complete:")
                print(f"  Chains reviewed: {result.chains_reviewed}")
                print(f"  Insights: {len(result.findings)}")
                print(f"  Belief updates: {len(result.belief_revisions)}")
            
            await asyncio.sleep(interval)
            
        except Exception as e:
            print(f"Reflection error: {e}")
            await asyncio.sleep(interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='/data/neo_reasoning.db')
    parser.add_argument('--interval', type=int, default=300)
    parser.add_argument('--min-chains', type=int, default=5)
    parser.add_argument('--model', default='qwen2.5:7b')
    parser.add_argument('--max-depth', type=int, default=3)
    args = parser.parse_args()
    
    asyncio.run(run_worker(args.db, args.interval, args.min_chains, args.model))


if __name__ == '__main__':
    main()