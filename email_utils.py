from email.message import EmailMessage
import mimetypes
import os
import smtplib
from typing import List, Optional


def send_email_with_attachment(
    subject: str,
    body: str,
    to_emails: List[str],
    attachment_path: Optional[str],
    smtp_server: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender_email: Optional[str] = None,
    use_tls: bool = True,
):
    """Send an email with an optional attachment using an SMTP server.

    Args:
        subject: Email subject line.
        body: Plain-text email body.
        to_emails: List of recipient email addresses.
        attachment_path: Path to the file to attach. If None or file does not exist, no attachment is added.
        smtp_server: SMTP server hostname.
        smtp_port: SMTP server port (e.g., 587 for TLS, 465 for SSL).
        smtp_username: Username for SMTP authentication.
        smtp_password: Password for SMTP authentication.
        sender_email: The "From" email address. Defaults to `smtp_username` if not provided.
        use_tls: If True, the connection will use STARTTLS. For implicit SSL (e.g., port 465), set this to False.
    """

    if sender_email is None:
        sender_email = smtp_username

    if not to_emails:
        raise ValueError("At least one recipient email address must be provided.")

    # Create the email message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(to_emails)
    msg.set_content(body)

    # Attach the file if provided and exists
    if attachment_path and os.path.isfile(attachment_path):
        ctype, encoding = mimetypes.guess_type(attachment_path)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)

        with open(attachment_path, "rb") as fp:
            msg.add_attachment(
                fp.read(),
                maintype=maintype,
                subtype=subtype,
                filename=os.path.basename(attachment_path),
            )
    else:
        if attachment_path:
            raise FileNotFoundError(f"Attachment file not found: {attachment_path}")

    # Connect to SMTP server and send the message
    if use_tls and smtp_port == 465:
        # If the user set use_tls=True but provided the SSL port, treat as implicit SSL
        use_tls = False

    if use_tls:
        connection = smtplib.SMTP(smtp_server, smtp_port)
        connection.starttls()
    else:
        # Could be implicit SSL (e.g., port 465) or unencrypted (not recommended)
        connection = smtplib.SMTP_SSL(smtp_server, smtp_port) if smtp_port == 465 else smtplib.SMTP(smtp_server, smtp_port)

    try:
        connection.login(smtp_username, smtp_password)
        connection.send_message(msg)
    finally:
        connection.quit() 