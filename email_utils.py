# email_utils.py
import os
import json
import base64
from email.mime.text import MIMEText

from google.oauth2 import service_account
from googleapiclient.discovery import build

import os
from dotenv import load_dotenv

load_dotenv() 


def style_html(content: str) -> str:
    """
    Wraps plain HTML content in a styled HTML template.
    """
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
      font-size: 16px;
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
    """
    Strips any markdown/code fence from the summary content.
    Adjust if your summary includes additional formatting tokens.
    """
    return (
        summary_html
        .strip()
        .removeprefix("```html")
        .removesuffix("```")
        .strip()
    )

def send_summary_email(to_email: str, subject: str, summary: str):
    """
    Sends an HTML-formatted email using the Gmail API via a
    service account with domain-wide delegation, impersonating
    news@brainrepo.es.
    """

    # 1. Load the entire JSON from an environment variable
    service_account_json_str = os.getenv("SERVICE_ACCOUNT_JSON")
    if not service_account_json_str:
        raise ValueError("SERVICE_ACCOUNT_JSON env variable is not set or empty.")

    service_account_info = json.loads(service_account_json_str)

    # 2. Create service account credentials, restricted to the 'gmail.send' scope
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/gmail.send"]
    )

    # 3. Delegate to news@brainrepo.es
    delegated_creds = creds.with_subject("news@brainrepo.es")

    # 4. Build the Gmail service
    service = build("gmail", "v1", credentials=delegated_creds)

    # 5. Clean & style the summary HTML
    clean = clean_summary(summary)
    styled_summary = style_html(clean)

    # 6. Prepare the MIME message
    message = MIMEText(styled_summary, "html")
    message["to"] = to_email
    message["subject"] = subject
    message["from"] = "BrainRepo <news@brainrepo.es>"

    # 7. Base64url-encode the message for Gmail API
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {"raw": raw_message}

    # 8. Send the email
    try:
        sent_message = service.users().messages().send(
            userId="news@brainrepo.es",  # or "me", same effect
            body=body
        ).execute()
        print("Email sent! Message ID:", sent_message.get("id"))
    except Exception as e:
        print("Failed to send email:", e)
