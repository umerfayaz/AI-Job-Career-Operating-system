import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.brain_outcomeLoop.email_config import load_email_config
from email.mime.application import MIMEApplication
import structlog
from pathlib import Path
from datetime import datetime

logger = structlog.get_logger()

class EmailSender:
    """Sends reports via email with PDF attachments"""

    def __init__(self):
        config = load_email_config()
        self.smtp_server = config["smtp_server"]
        self.smtp_port = config["smtp_port"]
        self.smtp_user = config["email"]
        self.smtp_password = config["password"]
        self.email_from = config["from_email"]
        self.default_receipt = config["default_recipient"]

        if not self.smtp_user or not self.smtp_password:
            print("Warning  Email credentiols are not configured")

    def send_report(self, subject:str, to_email: str, body: str, pdf_path: str = None, require_verification: bool =True):
        """
        Send email with optional PDF attachment
        """

        try:

            final_recipient = to_email or self.default_receipt
            
            logger.info(f" Sending email from resume {final_recipient}")

            if not to_email:
                logger.info(f"No email found in resume using default {self.default_receipt}")

            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = final_recipient
            msg['Subject'] = Header(
                f" {subject} - {datetime.now().strftime('%Y-%m-%d')}",
                'utf-8')

            ## Add Body

            msg.attach(MIMEText(body, 'html', 'utf-8'))

            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    pdf = MIMEApplication(f.read(), _subtype='pdf')
                    pdf.add_header('Content-Disposition','attachment',
                            filename = Path(pdf_path).name)
                    msg.attach(pdf)

            ## Send Email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f" Email Send to {final_recipient}")
            return True
        
        except Exception as e:
            print(f" Failed to send email:{e}")
            return False


