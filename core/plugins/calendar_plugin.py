# calendar_plugin.py
import sqlite3
import os
from datetime import datetime

class Plugin:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "brain.db")
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                reminder TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        
    def run(self):
        # No API key needed. Log once.
        print("[Calendar] Local SQLite calendar ready.")
        
    def add_event(self, title, date_str, reminder=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO calendar_events (title, event_date, reminder) VALUES (?, ?, ?)",
                  (title, date_str, reminder))
        conn.commit()
        conn.close()
        return f"📅 Event added: {title} on {date_str}"
        
    def list_events(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT title, event_date FROM calendar_events WHERE event_date >= date('now') ORDER BY event_date")
        rows = c.fetchall()
        conn.close()
        return rows or "No upcoming events."