# email_utils.py

import os
import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def style_html(content: str) -> str:
    return f""" 
<html>
<head>
  <meta charset="UTF-8" />
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #ffffff;
    }}
    .email-container {{
      max-width: 600px;
      margin: 20px auto;
      padding: 20px;
      background-color: #f2f2f2;
      border-radius: 6px;
    }}
    h2, h3 {{
      color: #333333;
    }}
    p, li {{
      color: #555555;
      line-height: 1.5;
      font-size: 16px;  /* Increased font size for paragraphs and list items */
    }}
  </style>
</head>
<body>
  <div class="email-container">
    {content}
  </div>
</body>
</html>
"""


def clean_summary(summary_html: str) -> str:
    return (
        summary_html
        .strip()
        .removeprefix("```html")
        .removesuffix("```")
        .strip()
    )


def send_summary_email(to_email: str, subject: str, summary: str):
    """
    Sends an HTML-formatted email using the Gmail API.
    'summary' is expected to be valid HTML returned by the API.
    """
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    token_uri = "https://oauth2.googleapis.com/token"

    # Create credentials using the refresh token.
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )

    # Build the Gmail service
    service = build("gmail", "v1", credentials=creds)

    clean = clean_summary(summary)

    # Wrap the API's raw HTML summary in some basic styling.
    styled_summary = style_html(clean)

    # Create the MIME email message (HTML)
    message = MIMEText(styled_summary, "html")
    message["to"] = to_email
    message["subject"] = subject
    message["from"] = "news@brainrepo.es"

    # Encode as base64 for Gmail
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw_message}

    # Send the email
    try:
        sent_message = service.users().messages().send(userId="me", body=body).execute()
        print("Email sent! Message ID:", sent_message.get("id"))
    except Exception as e:
        print("Failed to send email:", e)
