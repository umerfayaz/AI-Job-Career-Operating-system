import html
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
import os
from datetime import datetime


class EmailSender:
    """Sends reports via email with PDF attachments"""

    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM", self.smtp_user)
        self.to_email = os.getenv("TO_EMAIL")

        if not self.smtp_user or not self.smtp_password:
            print("Warning  Email credentiols are not configured")

    def send_report(self, subject:str, body: str, pdf_path: str = None):
        """
        Send email with optional PDF attachment
        """

        try:
            msg = MIMEMultipart()
            msg['from'] = self.email_from
            msg['To'] = self.to_email
            msg['subject'] = f" {subject} - {datetime.now().strftime('%Y-%m-%d')}"


            ## Add Body

            msg.attach(MIMEText(body, 'html'))

            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    pdf = MIMEApplication(f.read(), _subtype='pdf')
                    pdf.add_header('Content-Disposition','attachment',
                            filname = Path(pdf_path).name)
                    msg.attach(pdf)

            ## Send Email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f" Email Send to {self.to_email}")
            return True
        
        except Exception as e:
            print(f" Failed to send email:{e}")
            return False


