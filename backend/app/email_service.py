import base64
import html
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import Settings
from .models import StoredEnquiry


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GmailNotifier:
    """Sends owner notifications through the Gmail HTTPS API."""

    def __init__(self, settings: Settings) -> None:
        self.client_id = settings.gmail_client_id
        self.client_secret = settings.gmail_client_secret
        self.refresh_token = settings.gmail_refresh_token
        self.sender = settings.gmail_sender_email
        self.recipient = settings.contact_notification_to

    def send(self, enquiry: StoredEnquiry) -> None:
        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=[GMAIL_SEND_SCOPE],
        )
        credentials.refresh(Request())
        service = build(
            "gmail",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )
        raw_message = base64.urlsafe_b64encode(
            self._build_message(enquiry).as_bytes()
        ).decode("ascii")
        (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )

    def _build_message(self, enquiry: StoredEnquiry) -> EmailMessage:
        type_labels = {
            "development": "Python/backend development",
            "teaching": "Teaching/training",
            "other": "Other",
        }
        enquiry_type = type_labels.get(enquiry.enquiry_type, "Other")
        subject = f"Portfolio enquiry — {enquiry_type}"
        submitted_at = str(enquiry.created_at or "Not available")
        consent_at = str(enquiry.privacy_acknowledged_at or "Not available")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = self.recipient
        message["Reply-To"] = enquiry.email
        message.set_content(
            "New portfolio enquiry\n\n"
            f"Enquiry ID: {enquiry.id}\n"
            f"Subject: {subject}\n"
            f"Name: {enquiry.name}\n"
            f"Email: {enquiry.email}\n"
            f"Enquiry type: {enquiry_type}\n"
            f"Language: {enquiry.language.upper()}\n"
            f"Submitted at: {submitted_at}\n"
            "Privacy acknowledgement: accepted\n"
            f"Privacy acknowledged at: {consent_at}\n\n"
            f"Message:\n{enquiry.message}\n"
        )

        safe = {
            key: html.escape(value)
            for key, value in {
                "id": enquiry.id,
                "subject": subject,
                "name": enquiry.name,
                "email": enquiry.email,
                "type": enquiry_type,
                "language": enquiry.language.upper(),
                "submitted_at": submitted_at,
                "consent_at": consent_at,
                "message": enquiry.message,
            }.items()
        }
        safe_message = safe["message"].replace("\n", "<br>")
        message.add_alternative(
            f"""
            <html><body>
              <h2>New portfolio enquiry</h2>
              <p><strong>Enquiry ID:</strong> {safe['id']}</p>
              <p><strong>Subject:</strong> {safe['subject']}</p>
              <p><strong>Name:</strong> {safe['name']}</p>
              <p><strong>Email:</strong> {safe['email']}</p>
              <p><strong>Enquiry type:</strong> {safe['type']}</p>
              <p><strong>Language:</strong> {safe['language']}</p>
              <p><strong>Submitted at:</strong> {safe['submitted_at']}</p>
              <p><strong>Privacy acknowledgement:</strong> accepted</p>
              <p><strong>Privacy acknowledged at:</strong> {safe['consent_at']}</p>
              <p><strong>Message:</strong></p>
              <p>{safe_message}</p>
            </body></html>
            """,
            subtype="html",
        )
        return message

