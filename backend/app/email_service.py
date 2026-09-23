import html
import smtplib
from email.message import EmailMessage

from .config import Settings
from .models import StoredEnquiry


class GmailNotifier:
    def __init__(self, settings: Settings) -> None:
        self.sender = settings.gmail_sender_email
        self.password = settings.gmail_app_password
        self.recipient = settings.contact_recipient_email

    def send(self, enquiry: StoredEnquiry) -> None:
        email = self._build_message(enquiry)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(self.sender, self.password)
            smtp.send_message(email)

    def _build_message(self, enquiry: StoredEnquiry) -> EmailMessage:
        type_labels = {
            "development": "Python/backend development",
            "teaching": "Teaching/training",
            "other": "Other",
        }
        enquiry_type = type_labels.get(enquiry.enquiry_type, "Other")

        message = EmailMessage()
        message["Subject"] = f"Portfolio enquiry — {enquiry_type}"
        message["From"] = self.sender
        message["To"] = self.recipient
        message["Reply-To"] = enquiry.email
        message.set_content(
            "New portfolio enquiry\n\n"
            f"Enquiry ID: {enquiry.id}\n"
            f"Name: {enquiry.name}\n"
            f"Email: {enquiry.email}\n"
            f"Enquiry type: {enquiry_type}\n"
            f"Language: {enquiry.language.upper()}\n\n"
            f"Message:\n{enquiry.message}\n"
        )

        safe = {key: html.escape(value) for key, value in {
            "id": enquiry.id,
            "name": enquiry.name,
            "email": enquiry.email,
            "type": enquiry_type,
            "language": enquiry.language.upper(),
            "message": enquiry.message,
        }.items()}
        safe_message = safe["message"].replace("\n", "<br>")
        message.add_alternative(
            f"""
            <html><body>
              <h2>New portfolio enquiry</h2>
              <p><strong>Enquiry ID:</strong> {safe['id']}</p>
              <p><strong>Name:</strong> {safe['name']}</p>
              <p><strong>Email:</strong> {safe['email']}</p>
              <p><strong>Enquiry type:</strong> {safe['type']}</p>
              <p><strong>Language:</strong> {safe['language']}</p>
              <p><strong>Message:</strong></p>
              <p>{safe_message}</p>
            </body></html>
            """,
            subtype="html",
        )
        return message

