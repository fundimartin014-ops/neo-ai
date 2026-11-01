# =====================================================================
# core/plugins/web_trainer_plugin.py
# PERSISTENT WEB TRAINING — skips already-indexed URLs with freshness check
# =====================================================================

import os
import hashlib
import pickle
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URLS_FILE = r"C:\Users\fundi\OneDrive\Documents\TRAININGBOT2\web_sources.txt"
CHUNK_SIZE = 800
TIMEOUT = 10
HEADERS = {"User-Agent": "FundiBrain/1.0"}
STATE_FILE = Path("data/web_state.pkl")  # Persistent state
FRESHNESS_HOURS = 24  # Re-scrape after this many hours

try:
    from core.memory import remember
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

try:
    from core.topic import detect_topic
    TOPIC_AVAILABLE = True
except ImportError:
    TOPIC_AVAILABLE = False
    detect_topic = lambda x: "General"


class WebStateManager:
    """Manages which URLs have been processed and when."""
    
    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.processed = self._load()
    
    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return {}
        return {}
    
    def save(self):
        with open(self.state_file, 'wb') as f:
            pickle.dump(self.processed, f)
    
    def needs_update(self, url: str) -> bool:
        """Check if URL needs re-scraping based on freshness."""
        if url not in self.processed:
            return True
        
        last_scrape = self.processed[url].get("timestamp")
        if not last_scrape:
            return True
        
        last = datetime.fromisoformat(last_scrape)
        age = datetime.now() - last
        return age > timedelta(hours=FRESHNESS_HOURS)
    
    def mark_processed(self, url: str, chunks: int):
        self.processed[url] = {
            "chunks": chunks,
            "timestamp": datetime.now().isoformat(),
            "last_hash": None  # Could add content hash for change detection
        }
        self.save()
    
    def get_stats(self):
        return {
            "total_processed": len(self.processed),
            "urls": list(self.processed.keys())
        }


def clean_text(text):
    return " ".join(text.split())


class Plugin:
    def __init__(self):
        self.state = WebStateManager()
        logger.info("[WebTrainer] Plugin instantiated successfully.")

    def run(self):
        print("[WebTrainer] Initializing web trainer...")
        if not os.path.exists(URLS_FILE):
            print("[WebTrainer] web_sources.txt not found.")
            return

        try:
            with open(URLS_FILE, "r", encoding="utf-8") as f:
                urls = [u.strip() for u in f if u.strip()]
        except Exception as e:
            print(f"[WebTrainer] CRITICAL: Failed reading source manifest: {e}")
            return

        if not urls:
            print("[WebTrainer] No URLs found inside web_sources.txt.")
            return

        new_count = 0
        skip_count = 0
        update_count = 0

        for url in urls:
            if url.startswith("#"):
                continue
            
            # Check freshness
            if not self.state.needs_update(url):
                print(f"[WebTrainer] Skipped (fresh): {url}")
                skip_count += 1
                continue

            action = "Updating" if url in self.state.processed else "Training NEW"
            print(f"[WebTrainer] {action}: {url}")
            stored = self.scrape_and_store(url)
            
            if stored > 0:
                if action.startswith("Updating"):
                    update_count += 1
                else:
                    new_count += 1

        print(f"[WebTrainer] Complete: {new_count} new, {update_count} updated, {skip_count} fresh skipped")
        print(f"[WebTrainer] State: {self.state.get_stats()['total_processed']} URLs tracked")

    def scrape_and_store(self, url):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code != 200:
                print(f"[WebTrainer] Failed {url} (status {r.status_code})")
                return 0

            soup = BeautifulSoup(r.text, "html.parser")
            
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                tag.decompose()

            text = clean_text(soup.get_text())
            if not text or len(text) < 100:
                print(f"[WebTrainer] Not enough content at {url}")
                return 0

            chunks = [text[i:i+CHUNK_SIZE].strip() for i in range(0, len(text), CHUNK_SIZE)]
            seen_hashes = set()
            stored = 0

            for i, chunk in enumerate(chunks, 1):
                if not chunk:
                    continue
                
                h = hashlib.md5(chunk.encode("utf-8")).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                
                topic = detect_topic(chunk[:1000]) if TOPIC_AVAILABLE else "General"

                if MEMORY_AVAILABLE:
                    try:
                        remember(
                            input_text=f"{url} [chunk {i}]",
                            response=chunk,
                            source="web",
                            meta={"topic": topic, "url": url, "hash": h}
                        )
                    except Exception as e:
                        logger.debug(f"Memory store error: {e}")
                else:
                    self._store_direct(url, i, chunk, topic)

                stored += 1

            # Mark as processed with timestamp
            self.state.mark_processed(url, stored)
            print(f"[WebTrainer] Stored {stored} chunks from {url}")
            return stored

        except Exception as e:
            print(f"[WebTrainer] Exception scraping {url}: {e}")
            return 0
    
    def _store_direct(self, url, chunk_num, chunk, topic):
        try:
            import sqlite3
            conn = sqlite3.connect("brain.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory (input_text, response, source, meta)
                VALUES (?, ?, ?, ?)
            """, (f"{url} [chunk {chunk_num}]", chunk, "web",
                  f'{{"url": "{url}", "topic": "{topic}"}}'))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[WebTrainer] Direct SQLite error: {e}")


# Backward compatibility
def clean_text(text):
    return " ".join(text.split())