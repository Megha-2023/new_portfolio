from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class StoredEnquiry:
    id: str
    created_at: datetime | str | None
    name: str
    email: str
    enquiry_type: str
    message: str
    language: str

