import random
import string
from datetime import datetime, timedelta


verification_codes = {}


def generate_verification_code():
    """This function is for genersting code"""
    return ''.join(random.choices(string.digits, k=6))


async def store_unverified_email(task_id, email, verification_code):
    """storing univerified email"""
    verification_codes[task_id] = {
        "email": email,
        "code": verification_code,
        "verified": False,
        "expires_at": datetime.now() + timedelta(hours=1),
        "created_at": datetime.now()
    } 

async def send_verification_code(email, code, task_id):
    from ..core.email_sender import EmailSender

    sender = EmailSender()

    body = f"""
    <html>
    <body>
        <h2>🔐 Verify Your Email</h2>
        <p>Your verification code is:</p>
        <h1 style="color: #4CAF50; letter-spacing: 5px;">{code}</h1>
        <p>This code expires in 24 hours.</p>
        <p>If you didn't request this, please ignore this email.</p>
    </body>
    </html>
    """

    sender.send_report(
        subject= "Verify Your Email",
        to_email=email,
        body=body,
    )

def verify_email_code(task_id, code):

    if task_id not in verification_codes:
        return False, "Invalid UserID"
    
    data = verification_codes[task_id]

    if datetime.now() > data["expires_at"]:
        return False, "Code Expires"
    
    if data["code"] !=code:
        return False, "Inavlid Code"
    
    verification_codes[task_id]["verified"] = True
    return True, "Email Verified"

def is_email_verified(task_id):
    if task_id not in verification_codes:
        return False
    
    return verification_codes[task_id].get("verified", False)





