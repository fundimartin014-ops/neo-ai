import logging
import os
from core.database import init_db, get_conn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        # No key needed. SQLite is local and file-based.
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "brain.db")
        init_db()
        logger.info("[Database] SQLite brain.db initialized.")

    def run(self):
        logger.info("Database plugin ready. SQLite active.")

    def query(self, sql, params=()):
        """Run SELECT and return list of dicts."""
        try:
            conn = get_conn()
            c = conn.cursor()
            c.execute(sql, params)
            rows = c.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[DB Query Error] {e}")
            return []

    def execute(self, sql, params=()):
        """Run INSERT/UPDATE/DELETE."""
        try:
            conn = get_conn()
            c = conn.cursor()
            c.execute(sql, params)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"[DB Execute Error] {e}")
            return False