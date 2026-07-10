import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, to_email: str, subject: str, body: str, html: str | None = None) -> None:
        logger.info("Sending email: to=%s | subject=%s", to_email, subject[:80])
        msg = MIMEMultipart("alternative")
        msg["From"] = self.username
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        if html:
            msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            logger.info("Email sent: to=%s | subject=%s", to_email, subject[:80])
        except Exception:
            logger.exception("Email send failed: to=%s | subject=%s", to_email, subject[:80])
            raise
