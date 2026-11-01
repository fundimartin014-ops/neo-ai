#!/usr/bin/env python3
"""
run_neo_core.py

Starts Neo's main chat engine with reflection enabled.
Run this in one terminal window.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add your neo folder to path
sys.path.insert(0, str(Path(__file__).parent))

# Import your existing Neo components
# (Adjust these imports to match your actual file structure)
from neo.core.neo_brain import NeoBrain
from neo.core.reflection_loop import ReflectiveNeoBrain, ReflectionLoop
from neo.core.reasoning_memory import ReasoningMemory
from neo.core.mode_router import ModeRouter
from neo.core.personality_engine import PersonalityEngine
from neo.core.cognitive_core import CognitiveCore
from neo.core.synthesis_engine import SynthesisEngine

# Your existing Ollama client
from neo.llm_clients import OllamaClient  # or however you import it


async def main():
    # Initialize your existing LLM client
    llm = OllamaClient(base_url="http://localhost:11434")
    
    # Initialize memory
    reasoning_db = ReasoningMemory("neo_reasoning.db")
    
    # Build core components
    router = ModeRouter(llm)
    personalities = PersonalityEngine("mentor")  # or your default
    cognitive = CognitiveCore(llm, {})
    synthesis = SynthesisEngine(llm)
    
    # Your existing plugin manager
    from neo.plugins import PluginManager  # adjust import
    plugins = PluginManager()
    
    # Build NeoBrain
    neo_brain = NeoBrain(
        local_llm=llm,
        plugin_manager=plugins,
        memory_db=None,  # or your existing SQLite connection
        config={'default_personality': 'mentor'}
    )
    
    # Wrap with reflection
    reflection = ReflectionLoop(llm, reasoning_db, config={
        'reflection_model': 'qwen2.5:7b',
        'min_chains': 5,
        'interval_turns': 20,
    })
    
    reflective_brain = ReflectiveNeoBrain(neo_brain, reflection)
    
    print("=" * 60)
    print("  NEO PERSONAL INTELLIGENCE - CORE ENGINE")
    print("=" * 60)
    print("Reflection: ENABLED")
    print("Personality: mentor")
    print("Mode: PERSONAL + TOOL_ASSISTED")
    print("-" * 60)
    
    # Your existing chat loop
    history = []
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            
            # Handle reflection commands
            if user_input.startswith('/'):
                from neo.core.reflection_loop import ReflectionCommands
                cmds = ReflectionCommands(reflective_brain)
                response = await cmds.handle(user_input)
                if response:
                    print(f"\nNeo: {response}")
                    continue
            
            # Process through NeoBrain
            result = await reflective_brain.process(user_input, history)
            
            # Display
            print(f"\nNeo: {result['response']}")
            
            # Show metadata in debug mode
            if '--debug' in sys.argv:
                print(f"   [mode: {result['mode']} | personality: {result['personality']}")
                print(f"    confidence: {result['confidence']:.2f} | sources: {result['sources']}")
                print(f"    cognitive_steps: {result['cognitive_steps']} | tools: {result['tools_used']}")
                print(f"    tool_independence: {result['tool_independence_score']:.2f}]")
            
            # Update history
            history.append({'role': 'user', 'content': user_input})
            history.append({'role': 'assistant', 'content': result['response']})
            
            # Keep history manageable
            if len(history) > 20:
                history = history[-20:]
                
        except KeyboardInterrupt:
            print("\n\nShutting down Neo...")
            break
        except Exception as e:
            print(f"\n[Error] {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())