import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    """
    Spreadsheet plugin stub for xlsx/csv parsing, exporting, reporting.
    (In production, use openpyxl, pandas, or Google Sheets API.)
    """

    def __init__(self):
        self.temp_dir = os.getenv("SPREADSHEET_TMP", "/tmp/spreadsheets")
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info("SpreadsheetPlugin temp dir: %s", self.temp_dir)

    def run(self):
        logger.info("SpreadsheetPlugin started (stub mode).")
        # Add import/export logic as needed.