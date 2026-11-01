#!/usr/bin/env python3
"""
run_dashboard.py

Generates and serves the health dashboard.
Run this in a THIRD terminal window.
"""

import sys
import time
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).parent))

from neo.tests.health_dashboard import NeoDataSource, DashboardGenerator


def generate_dashboard():
    """Generate fresh dashboard HTML."""
    try:
        source = NeoDataSource("neo_reasoning.db", "neo_eval_history.db")
        data = source.get_all_stats()
        gen = DashboardGenerator(data)
        html = gen.generate(refresh_seconds=30)
        Path("neo_dashboard.html").write_text(html, encoding='utf-8')
        return True
    except Exception as e:
        print(f"Dashboard generation error: {e}")
        return False


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.path = '/neo_dashboard.html'
        return super().do_GET()
    
    def log_message(self, format, *args):
        pass


def main():
    # Initial generation
    print("Generating dashboard...")
    if generate_dashboard():
        print("✅ Dashboard ready")
    else:
        print("⚠️ Dashboard failed, will retry")
    
    # Background regeneration
    def regen_loop():
        while True:
            time.sleep(30)
            generate_dashboard()
    
    regen_thread = threading.Thread(target=regen_loop, daemon=True)
    regen_thread.start()
    
    # Serve
    port = 3000
    server = HTTPServer(('localhost', port), DashboardHandler)
    print(f"\nDashboard server: http://localhost:{port}")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard server stopped")


if __name__ == '__main__':
    main()