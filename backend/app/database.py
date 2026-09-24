from datetime import UTC, datetime
from typing import Any

from supabase import Client, create_client

from .config import Settings
from .models import StoredEnquiry
from .schemas import ContactRequest


class ContactRepository:
    def __init__(self, settings: Settings) -> None:
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_secret_key,
        )

    def consume_rate_limit(self, ip_hash: str) -> bool:
        response = self.client.rpc(
            "consume_contact_rate_limit",
            {"p_ip_hash": ip_hash},
        ).execute()
        return response.data is True

    def save_enquiry(self, submission: ContactRequest) -> StoredEnquiry:
        payload = {
            "name": submission.name,
            "email": str(submission.email),
            "enquiry_type": submission.enquiry_type.value,
            "message": submission.message,
            "language": submission.language.value,
            "privacy_acknowledged_at": datetime.now(UTC).isoformat(),
            "notification_sent": False,
        }
        response = self.client.table("contact_enquiries").insert(payload).execute()
        if not response.data:
            raise RuntimeError("Supabase did not return the stored enquiry")
        return self._to_enquiry(response.data[0])

    def mark_notification_sent(self, enquiry_id: str) -> None:
        self.client.table("contact_enquiries").update({
            "notification_sent": True,
            "notification_error": None,
        }).eq("id", enquiry_id).execute()

    def mark_notification_failed(self, enquiry_id: str, safe_error: str) -> None:
        self.client.table("contact_enquiries").update({
            "notification_sent": False,
            "notification_error": safe_error,
        }).eq("id", enquiry_id).execute()

    def unsent_enquiries(self, limit: int = 100) -> list[StoredEnquiry]:
        response = (
            self.client.table("contact_enquiries")
            .select("id,created_at,name,email,enquiry_type,message,language,privacy_acknowledged_at")
            .eq("notification_sent", False)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return [self._to_enquiry(row) for row in (response.data or [])]

    @staticmethod
    def _to_enquiry(row: dict[str, Any]) -> StoredEnquiry:
        return StoredEnquiry(
            id=str(row["id"]),
            created_at=row.get("created_at"),
            name=str(row["name"]),
            email=str(row["email"]),
            enquiry_type=str(row["enquiry_type"]),
            message=str(row["message"]),
            language=str(row["language"]),
            privacy_acknowledged_at=row.get("privacy_acknowledged_at"),
        )
