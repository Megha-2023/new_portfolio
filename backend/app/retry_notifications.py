import logging

from .config import get_settings
from .database import ContactRepository
from .email_service import GmailNotifier


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def retry_unsent_notifications(limit: int = 100) -> tuple[int, int]:
    settings = get_settings()
    missing = settings.missing_required_values()
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    repository = ContactRepository(settings)
    notifier = GmailNotifier(settings)
    sent = 0
    failed = 0

    for enquiry in repository.unsent_enquiries(limit):
        try:
            notifier.send(enquiry)
            repository.mark_notification_sent(enquiry.id)
            sent += 1
        except Exception:
            logger.exception("Notification retry failed for enquiry %s", enquiry.id)
            repository.mark_notification_failed(enquiry.id, "gmail_delivery_failed")
            failed += 1

    return sent, failed


if __name__ == "__main__":
    sent_count, failed_count = retry_unsent_notifications()
    print(f"Notifications sent: {sent_count}; failed: {failed_count}")

