from datetime import UTC, datetime
import base64
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest
from email_validator import EmailUndeliverableError
from fastapi.testclient import TestClient

from app.config import Settings
from app.email_service import GmailNotifier
from app.email_validation import (
    EmailDomainUnreachableError,
    EmailDomainValidator,
    InvalidEmailError,
    normalize_email_address,
)
from app.main import create_app
from app.models import StoredEnquiry
from app.security import get_client_ip, hash_client_ip


VALID_PAYLOAD = {
    "name": "  Megha Test  ",
    "email": " Portfolio.User@GMAIL.COM ",
    "enquiry_type": "development",
    "message": "  A sufficiently detailed test enquiry.  ",
    "language": "en",
    "privacy_acknowledgement": True,
    "website": "",
}


class FakeRepository:
    def __init__(self, rate_limit_accepted: bool = True) -> None:
        self.rate_limit_accepted = rate_limit_accepted
        self.saved = []
        self.notification_sent = []
        self.notification_failures = []
        self.ip_hashes = []

    def consume_rate_limit(self, ip_hash: str) -> bool:
        self.ip_hashes.append(ip_hash)
        return self.rate_limit_accepted

    def save_enquiry(self, submission):
        self.saved.append(submission)
        return StoredEnquiry(
            id="8dc579e0-cf32-4c09-a292-c825632b6a92",
            created_at=datetime.now(UTC),
            name=submission.name,
            email=str(submission.email),
            enquiry_type=submission.enquiry_type.value,
            message=submission.message,
            language=submission.language.value,
            privacy_acknowledged_at=datetime.now(UTC),
        )

    def mark_notification_sent(self, enquiry_id: str) -> None:
        self.notification_sent.append(enquiry_id)

    def mark_notification_failed(self, enquiry_id: str, error: str) -> None:
        self.notification_failures.append((enquiry_id, error))


class FakeNotifier:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent = []

    def send(self, enquiry: StoredEnquiry) -> None:
        if self.should_fail:
            raise RuntimeError("simulated Gmail API failure")
        self.sent.append(enquiry)


class FakeDomainValidator:
    def __init__(self, error=None) -> None:
        self.error = error
        self.checked = []

    def validate(self, email: str) -> None:
        self.checked.append(email)
        if self.error:
            raise self.error


def make_client(repository=None, notifier=None, domain_validator=None, trust_proxy_headers=False):
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_secret_key="sb_secret_test_only",
        gmail_client_id="test-client-id.apps.googleusercontent.com",
        gmail_client_secret="test-client-secret",
        gmail_refresh_token="test-refresh-token",
        gmail_sender_email="sender@example.com",
        contact_notification_to="recipient@example.com",
        rate_limit_salt="test-rate-limit-salt",
        allowed_origins="https://portfolio.example",
        trust_proxy_headers=trust_proxy_headers,
    )
    app = create_app(settings)
    app.state.repository_factory = lambda _: repository or FakeRepository()
    app.state.notifier_factory = lambda _: notifier or FakeNotifier()
    app.state.email_domain_validator = domain_validator or FakeDomainValidator()
    return TestClient(app)


def test_health_endpoint():
    response = make_client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_valid_enquiry_is_trimmed_stored_and_notified():
    repository = FakeRepository()
    notifier = FakeNotifier()
    response = make_client(repository, notifier).post("/api/contact", json=VALID_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "notification_sent": True}
    assert repository.saved[0].name == "Megha Test"
    assert repository.saved[0].email == "Portfolio.User@gmail.com"
    assert repository.saved[0].message == "A sufficiently detailed test enquiry."
    assert repository.notification_sent
    assert notifier.sent


def test_honeypot_is_silently_accepted_without_storage():
    repository = FakeRepository()
    payload = {"website": "https://spam.example"}
    response = make_client(repository).post("/api/contact", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert repository.saved == []
    assert repository.ip_hashes == []


def test_invalid_submission_is_rejected_without_storage():
    repository = FakeRepository()
    payload = {**VALID_PAYLOAD, "message": "too short", "privacy_acknowledgement": False}
    response = make_client(repository).post("/api/contact", json=payload)

    assert response.status_code == 422
    assert response.json() == {"error": "validation_error"}
    assert repository.saved == []


def test_rate_limit_returns_429_without_storage():
    repository = FakeRepository(rate_limit_accepted=False)
    response = make_client(repository).post("/api/contact", json=VALID_PAYLOAD)

    assert response.status_code == 429
    assert response.json() == {"error": "rate_limit"}
    assert repository.saved == []


def test_gmail_api_failure_keeps_enquiry_and_returns_success():
    repository = FakeRepository()
    notifier = FakeNotifier(should_fail=True)
    response = make_client(repository, notifier).post("/api/contact", json=VALID_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "notification_sent": False}
    assert len(repository.saved) == 1
    assert repository.notification_failures == [
        ("8dc579e0-cf32-4c09-a292-c825632b6a92", "gmail_delivery_failed")
    ]


def test_cors_allows_configured_frontend_origin():
    response = make_client().options(
        "/api/contact",
        headers={
            "Origin": "https://portfolio.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://portfolio.example"


def test_hash_is_salted_and_proxy_headers_are_opt_in():
    assert hash_client_ip("192.0.2.5", "one") != hash_client_ip("192.0.2.5", "two")

    class RequestStub:
        headers = {"x-forwarded-for": "203.0.113.9, 10.0.0.2"}
        client = type("Client", (), {"host": "192.0.2.5"})()

    assert get_client_ip(RequestStub(), False) == "192.0.2.5"
    assert get_client_ip(RequestStub(), True) == "203.0.113.9"


def test_notification_is_multipart_and_escapes_visitor_html():
    settings = Settings(
        gmail_client_id="test-client-id.apps.googleusercontent.com",
        gmail_client_secret="test-client-secret",
        gmail_refresh_token="test-refresh-token",
        gmail_sender_email="sender@example.com",
        contact_notification_to="recipient@example.com",
    )
    enquiry = StoredEnquiry(
        id="8dc579e0-cf32-4c09-a292-c825632b6a92",
        created_at=None,
        name="Megha <Test>",
        email="visitor@example.com",
        enquiry_type="teaching",
        message="Hello <script>alert('x')</script>",
        language="fr",
        privacy_acknowledged_at="2026-09-23T10:30:00+00:00",
    )

    message = GmailNotifier(settings)._build_message(enquiry)
    plain_text = message.get_body(preferencelist=("plain",)).get_content()
    html_text = message.get_body(preferencelist=("html",)).get_content()

    assert message["Reply-To"] == "visitor@example.com"
    assert message.is_multipart()
    assert enquiry.id in plain_text
    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text
    assert "Privacy acknowledgement: accepted" in plain_text
    assert "2026-09-23T10:30:00+00:00" in plain_text


def test_gmail_api_uses_oauth_https_and_sends_encoded_message(monkeypatch):
    captured = {}

    class FakeCredentials:
        def __init__(self, **kwargs):
            captured["credentials"] = kwargs

        def refresh(self, request):
            captured["refreshed"] = True

    class FakeExecution:
        def execute(self):
            captured["executed"] = True
            return {"id": "gmail-message-id"}

    class FakeMessages:
        def send(self, *, userId, body):
            captured["user_id"] = userId
            captured["body"] = body
            return FakeExecution()

    class FakeUsers:
        def messages(self):
            return FakeMessages()

    class FakeService:
        def users(self):
            return FakeUsers()

    monkeypatch.setattr("app.email_service.Credentials", FakeCredentials)
    monkeypatch.setattr("app.email_service.Request", lambda: object())
    monkeypatch.setattr(
        "app.email_service.build",
        lambda api, version, **kwargs: FakeService(),
    )

    settings = Settings(
        gmail_client_id="test-client-id.apps.googleusercontent.com",
        gmail_client_secret="test-client-secret",
        gmail_refresh_token="test-refresh-token",
        gmail_sender_email="sender@example.com",
        contact_notification_to="recipient@example.com",
    )
    enquiry = StoredEnquiry(
        id="8dc579e0-cf32-4c09-a292-c825632b6a92",
        created_at="2026-09-23T10:29:00+00:00",
        name="Megha Test",
        email="visitor@examplemail.com",
        enquiry_type="development",
        message="A test message for the mocked Gmail API.",
        language="en",
        privacy_acknowledged_at="2026-09-23T10:29:00+00:00",
    )

    GmailNotifier(settings).send(enquiry)

    raw = base64.urlsafe_b64decode(captured["body"]["raw"].encode("ascii"))
    sent_message = BytesParser(policy=policy.default).parsebytes(raw)
    assert captured["credentials"]["refresh_token"] == "test-refresh-token"
    assert captured["credentials"]["token_uri"].startswith("https://")
    assert captured["refreshed"] is True
    assert captured["user_id"] == "me"
    assert captured["executed"] is True
    assert sent_message["To"] == "recipient@example.com"
    assert sent_message["Reply-To"] == "visitor@examplemail.com"


@pytest.mark.parametrize(
    ("raw_email", "normalized"),
    [
        ("valid.user@gmail.com", "valid.user@gmail.com"),
        ("  Person@UNIVERSITY.EDU  ", "Person@university.edu"),
        ("Employee@COMPANY.CO.UK", "Employee@company.co.uk"),
    ],
)
def test_email_syntax_is_trimmed_and_normalized(raw_email, normalized):
    assert normalize_email_address(raw_email) == normalized


@pytest.mark.parametrize(
    "email",
    ["valid.user@gmail.com", "person@university.edu", "employee@company.co.uk"],
)
def test_valid_mail_domains_pass_mocked_mx_check(monkeypatch, email):
    monkeypatch.setattr(
        "app.email_validation.validate_email_deliverability",
        lambda *args, **kwargs: {"mx": [(10, "mail.examplemail.com")]},
    )
    EmailDomainValidator(timeout=0.1).validate(email)


@pytest.mark.parametrize(
    "raw_email",
    [
        "malformed-address",
        "missing-at.example.com",
        "user..dots@examplemail.com",
        f"{'a' * 245}@examplemail.com",
        "victim@examplemail.com\r\nBcc: attacker@examplemail.com",
    ],
)
def test_invalid_email_syntax_is_rejected(raw_email):
    with pytest.raises(InvalidEmailError):
        normalize_email_address(raw_email)


@pytest.mark.parametrize(
    "raw_email",
    [
        "user@example.com",
        "user@sub.example.com",
        "user@example.net",
        "user@example.org",
        "user@localhost",
        "user@sub.local",
        "user@invalid",
        "user@test",
    ],
)
def test_reserved_email_domains_and_subdomains_are_rejected(raw_email):
    with pytest.raises(EmailDomainUnreachableError):
        normalize_email_address(raw_email)


@pytest.mark.parametrize("dns_case", ["nxdomain", "no_mail_records"])
def test_confirmed_dns_failure_is_rejected(monkeypatch, dns_case):
    def reject_domain(*args, **kwargs):
        raise EmailUndeliverableError(dns_case)

    monkeypatch.setattr("app.email_validation.validate_email_deliverability", reject_domain)
    validator = EmailDomainValidator(timeout=0.1)
    with pytest.raises(EmailDomainUnreachableError):
        validator.validate("person@company.examplemail")


def test_temporary_dns_timeout_is_allowed_and_logged(monkeypatch, caplog):
    monkeypatch.setattr(
        "app.email_validation.validate_email_deliverability",
        lambda *args, **kwargs: {"unknown-deliverability": "timeout"},
    )
    validator = EmailDomainValidator(timeout=0.1)
    validator.validate("person@company.examplemail")
    assert "Temporary DNS problem" in caplog.text


def test_confirmed_unreachable_domain_is_not_stored_or_notified():
    repository = FakeRepository()
    notifier = FakeNotifier()
    domain_validator = FakeDomainValidator(EmailDomainUnreachableError())
    payload = {**VALID_PAYLOAD, "email": "person@unreachable-domain.com"}

    response = make_client(repository, notifier, domain_validator).post(
        "/api/contact", json=payload
    )

    assert response.status_code == 422
    assert response.json() == {"error": "email_domain_unreachable", "field": "email"}
    assert repository.saved == []
    assert notifier.sent == []


def test_malformed_email_is_not_stored_or_notified():
    repository = FakeRepository()
    notifier = FakeNotifier()
    response = make_client(repository, notifier).post(
        "/api/contact", json={**VALID_PAYLOAD, "email": "not-an-email"}
    )

    assert response.status_code == 422
    assert response.json() == {"error": "invalid_email", "field": "email"}
    assert repository.saved == []
    assert notifier.sent == []


def test_frontend_has_bilingual_email_domain_mapping():
    script = (Path(__file__).parents[2] / "script.js").read_text(encoding="utf-8")
    assert "Please use a working email address. This domain cannot receive email." in script
    assert "Veuillez utiliser une adresse e-mail fonctionnelle." in script
    assert "responseData.error === 'email_domain_unreachable'" in script
    assert "contactEmail.focus()" in script
