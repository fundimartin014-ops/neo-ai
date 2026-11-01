#!/usr/bin/env python3
"""
neo/services/dashboard_server.py

Simple HTTP server that regenerates dashboard HTML periodically.
"""

import argparse
import http.server
import socketserver
import time
import threading
from pathlib import Path

from neo.tests.health_dashboard import NeoDataSource, DashboardGenerator


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, html_path, *args, **kwargs):
        self.html_path = Path(html_path)
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            if self.html_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(self.html_path.read_bytes())
            else:
                self.send_error(503, "Dashboard not ready")
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass


def make_handler(html_path):
    def handler(*args, **kwargs):
        return DashboardHandler(html_path, *args, **kwargs)
    return handler


def regenerate_loop(html_path: str, db_path: str, eval_db: str, interval: int):
    """Background thread to regenerate dashboard HTML."""
    while True:
        try:
            source = NeoDataSource(db_path, eval_db)
            data = source.get_all_stats()
            gen = DashboardGenerator(data)
            html = gen.generate()
            
            Path(html_path).write_text(html, encoding='utf-8')
            print(f"[{time.strftime('%H:%M:%S')}] Dashboard regenerated")
            
        except Exception as e:
            print(f"Dashboard generation error: {e}")
        
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='/data/neo_reasoning.db')
    parser.add_argument('--eval-db', default='/data/neo_eval_history.db')
    parser.add_argument('--port', type=int, default=3000)
    parser.add_argument('--refresh', type=int, default=300)
    parser.add_argument('--bind', default='0.0.0.0')
    args = parser.parse_args()
    
    html_path = '/tmp/neo_dashboard.html'
    
    # Initial generation
    try:
        source = NeoDataSource(args.db, args.eval_db)
        data = source.get_all_stats()
        gen = DashboardGenerator(data)
        html = gen.generate()
        Path(html_path).write_text(html, encoding='utf-8')
    except Exception as e:
        print(f"Initial generation failed: {e}")
        Path(html_path).write_text(f"<h1>Neo Dashboard</h1><p>Error: {e}</p>")
    
    # Start background regeneration
    regen_thread = threading.Thread(
        target=regenerate_loop,
        args=(html_path, args.db, args.eval_db, args.refresh),
        daemon=True
    )
    regen_thread.start()
    
    # Start server
    with socketserver.TCPServer((args.bind, args.port), make_handler(html_path)) as httpd:
        print(f"Dashboard server on http://{args.bind}:{args.port}")
        httpd.serve_forever()


if __name__ == '__main__':
    main()