import logging
from functools import lru_cache

from email_validator import (
    EmailNotValidError,
    EmailUndeliverableError,
    caching_resolver,
    validate_email,
)
from email_validator.deliverability import validate_email_deliverability


logger = logging.getLogger(__name__)

RESERVED_EMAIL_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
    "test",
    "invalid",
    "localhost",
    "local",
}


class InvalidEmailError(ValueError):
    """The email address has invalid or unsafe syntax."""


class EmailDomainUnreachableError(ValueError):
    """The email domain is reserved or cannot receive email."""


def _is_reserved_domain(domain: str) -> bool:
    normalized_domain = domain.rstrip(".").lower()
    return any(
        normalized_domain == reserved or normalized_domain.endswith(f".{reserved}")
        for reserved in RESERVED_EMAIL_DOMAINS
    )


def normalize_email_address(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidEmailError("Email must be text")

    candidate = value.strip()
    if not candidate or len(candidate) > 254:
        raise InvalidEmailError("Email length is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise InvalidEmailError("Email contains control characters")

    if candidate.count("@") == 1:
        raw_domain = candidate.rsplit("@", 1)[1]
        if _is_reserved_domain(raw_domain):
            raise EmailDomainUnreachableError("Reserved email domain")

    try:
        result = validate_email(candidate, check_deliverability=False)
    except EmailNotValidError as error:
        raise InvalidEmailError("Invalid email syntax") from error

    normalized = result.normalized
    if len(normalized) > 254:
        raise InvalidEmailError("Normalized email is too long")
    if _is_reserved_domain(result.ascii_domain or result.domain):
        raise EmailDomainUnreachableError("Reserved email domain")
    return normalized


class EmailDomainValidator:
    """Checks domain-level mail delivery without probing individual mailboxes."""

    def __init__(self, timeout: float = 3.0) -> None:
        self.resolver = caching_resolver(timeout=timeout)

    def validate(self, normalized_email: str) -> None:
        syntax = validate_email(normalized_email, check_deliverability=False)
        try:
            result = validate_email_deliverability(
                syntax.ascii_domain,
                syntax.domain,
                dns_resolver=self.resolver,
            )
        except EmailUndeliverableError as error:
            raise EmailDomainUnreachableError("Email domain cannot receive mail") from error

        if result.get("unknown-deliverability"):
            logger.warning(
                "Temporary DNS problem during email-domain validation; "
                "accepting the syntactically valid address"
            )


@lru_cache(maxsize=1)
def get_email_domain_validator() -> EmailDomainValidator:
    return EmailDomainValidator()

