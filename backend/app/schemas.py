from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from .email_validation import normalize_email_address


class EnquiryType(StrEnum):
    DEVELOPMENT = "development"
    TEACHING = "teaching"
    OTHER = "other"


class Language(StrEnum):
    EN = "en"
    FR = "fr"


class ContactRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    enquiry_type: EnquiryType
    message: str = Field(min_length=10, max_length=5000)
    language: Language
    privacy_acknowledgement: bool
    website: str = Field(default="", max_length=500)

    @field_validator("name", "message", "website", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("enquiry_type", "language", mode="before")
    @classmethod
    def trim_identifiers(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def validate_and_normalize_email(cls, value: object) -> str:
        return normalize_email_address(value)

    @field_validator("name")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("name contains invalid control characters")
        return value

    @model_validator(mode="after")
    def require_privacy_acknowledgement(self) -> "ContactRequest":
        if self.privacy_acknowledgement is not True:
            raise ValueError("privacy acknowledgement is required")
        return self


class ContactResponse(BaseModel):
    ok: bool = True
    notification_sent: bool | None = None


class ErrorResponse(BaseModel):
    error: str
