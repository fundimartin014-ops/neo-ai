import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    """
    Stub: Email sending plugin.
    Set SMTP credentials in .env/environment and use a secure mail library for real use!
    """

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")

    def run(self):
        logger.info("Email plugin initialized (stub)")
        # Add connection or test logic here

    def send_email(self, recipient, subject, body):
        logger.info(f"Would send an email to {recipient}: {subject}")
        # In production: implement with smtplib, etc.
        return f"Stub: Email to {recipient} not actually sent."