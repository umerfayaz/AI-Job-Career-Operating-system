import os
from typing import Dict
from dotenv import load_dotenv
load_dotenv()

def load_email_config() -> Dict:
    return {
        "email": os.getenv("IMAP_EMAIL"),
        "password": os.getenv("SMTP_PASSWORD"),
        "imap_server": os.getenv("IMAP_SERVER", "imap.gmail.com"),
        "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail_com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "folder": os.getenv("IMAP_FOLDER", "INBOX"),
        "from_email": os.getenv("EMAIL_FROM", os.getenv("SMTP_USER")),
        "default_recipient": os.getenv(
            "DEFAULT_RECEIPT_EMAIL",
            "chubaykhan@gmail.com"
        )
    }

