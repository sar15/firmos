def send_email(to_email: str, subject: str, body: str):
    """Delivery is disabled until recipient resolution and an outbox exist."""
    raise RuntimeError("Decision email delivery is disabled in V1.")
