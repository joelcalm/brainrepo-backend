#email_utils.py

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
import os

def send_summary_email(to_email, subject, summary):
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    token_uri = "https://oauth2.googleapis.com/token"

    # Create credentials. Passing None as the initial access token is acceptable.
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )

    # Build the Gmail service.
    service = build("gmail", "v1", credentials=creds)

    # Create the email message.
    message = MIMEText(summary, "html")
    message["to"] = to_email
    message["subject"] = subject
    message["from"] = "news@brainrepo.es"

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw_message}

    # Send the email.
    try:
        sent_message = service.users().messages().send(userId="me", body=body).execute()
        print("Email sent. Message ID:", sent_message.get("id"))
    except Exception as e:
        print("Failed to send email:", e)
