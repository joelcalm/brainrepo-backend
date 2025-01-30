# backend/email_utils.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")

def send_summary_email(to_email, subject, summary):
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    auth = ("api", MAILGUN_API_KEY)

    html_content = f"""
    <html>
      <body>
        <h1>{subject}</h1>
        <p>{summary}</p>
      </body>
    </html>
    """

    data = {
        "from": f"YouTube Summary <mailgun@{MAILGUN_DOMAIN}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    try:
        response = requests.post(url, auth=auth, data=data)
        response.raise_for_status()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Mailgun error: {e}")
