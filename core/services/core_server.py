#!/usr/bin/env python3
"""
neo/services/core_server.py

HTTP server for Neo's chat interface.
"""

import asyncio
import argparse
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# Import your existing NeoBrain
from neo.core.neo_brain import NeoBrain
from neo.core.reflection_loop import ReflectiveNeoBrain, ReflectionLoop
from neo.core.reasoning_memory import ReasoningMemory


class NeoHandler(BaseHTTPRequestHandler):
    def __init__(self, neo_brain, *args, **kwargs):
        self.neo = neo_brain
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/health':
            self._respond(200, {'status': 'ok', 'mode': 'personal_intelligence'})
        elif self.path == '/self':
            # Return Neo's self-model
            model = self.neo.get_self_model()
            self._respond(200, model)
        else:
            self._respond(404, {'error': 'not found'})
    
    def do_POST(self):
        if self.path == '/chat':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            data = json.loads(body)
            
            user_input = data.get('message', '')
            history = data.get('history', [])
            
            # Run Neo
            result = asyncio.run(self.neo.process(user_input, history))
            
            self._respond(200, result)
        else:
            self._respond(404, {'error': 'not found'})
    
    def _respond(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass


def make_handler(neo_brain):
    def handler(*args, **kwargs):
        return NeoHandler(neo_brain, *args, **kwargs)
    return handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--db', default='/data/neo.db')
    parser.add_argument('--reasoning-db', default='/data/neo_reasoning.db')
    parser.add_argument('--eval-db', default='/data/neo_eval_history.db')
    parser.add_argument('--personality', default='mentor')
    parser.add_argument('--auto-reflect', action='store_true')
    args = parser.parse_args()
    
    # Initialize components
    # (You'll adapt this to your actual initialization)
    from neo.core.mode_router import ModeRouter
    from neo.core.personality_engine import PersonalityEngine
    from neo.core.cognitive_core import CognitiveCore
    from neo.core.synthesis_engine import SynthesisEngine
    
    # Mock or real LLM client
    class LocalLLM:
        async def generate(self, prompt, **kwargs):
            # Replace with your actual Ollama client
            import urllib.request
            req = urllib.request.Request(
                'http://ollama:11434/api/generate',
                data=json.dumps({
                    'model': kwargs.get('model', 'qwen2.5:7b'),
                    'prompt': prompt,
                    'stream': False
                }).encode(),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())['response']
    
    llm = LocalLLM()
    
    # Build NeoBrain
    router = ModeRouter(llm)
    personalities = PersonalityEngine(args.personality)
    cognitive = CognitiveCore(llm, {})
    synthesis = SynthesisEngine(llm)
    
    # Mock plugin manager (replace with yours)
    class MockPlugins:
        def list_available(self): return []
        async def execute(self, name, query): return ""
    
    neo_brain = NeoBrain(
        local_llm=llm,
        plugin_manager=MockPlugins(),
        memory_db=None,  # Replace with your SQLite connection
        config={'default_personality': args.personality}
    )
    
    # Wrap with reflection
    reasoning_mem = ReasoningMemory(args.reasoning_db)
    reflection = ReflectionLoop(llm, reasoning_mem)
    reflective_brain = ReflectiveNeoBrain(neo_brain, reflection)
    
    # Start server
    server = HTTPServer((args.host, args.port), make_handler(reflective_brain))
    print(f"Neo core server running on {args.host}:{args.port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()