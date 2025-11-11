"""Email notification utility for job status updates."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict
from datetime import datetime
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_job_notification(
    job_id: str,
    job_url: str,
    status: str,
    stats: Optional[Dict] = None,
    error_message: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None
) -> bool:
    """
    Send email notification about job completion or failure.

    Args:
        job_id: Unique job identifier
        job_url: URL that was scraped
        status: Job status (success/failed)
        stats: Job statistics dictionary
        error_message: Error message if job failed
        started_at: Job start time
        finished_at: Job finish time

    Returns:
        True if email sent successfully, False otherwise
    """
    if not settings.email_enabled:
        logger.info("Email notifications are disabled")
        return False
    
    if not settings.email_to:
        logger.warning("No recipient email configured")
        return False

    try:
        # Calculate duration
        duration = None
        if started_at and finished_at:
            duration = (finished_at - started_at).total_seconds()

        # Create email content
        subject, body = _create_email_content(
            job_id=job_id,
            job_url=job_url,
            status=status,
            stats=stats,
            error_message=error_message,
            duration=duration
        )

        # Send email
        _send_email(subject, body)
        logger.info(f"Email notification sent for job {job_id} with status: {status}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        return False


def _create_email_content(
    job_id: str,
    job_url: str,
    status: str,
    stats: Optional[Dict],
    error_message: Optional[str],
    duration: Optional[float]
) -> tuple[str, str]:
    """Create email subject and body."""

    # Subject
    if status == "success":
        subject = f"✓ Scraping Job Completed Successfully - {job_id[:8]}"
    else:
        subject = f"✗ Scraping Job Failed - {job_id[:8]}"

    # Body
    if status == "success":
        body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px;">
        <h2 style="color: #28a745; border-bottom: 3px solid #28a745; padding-bottom: 10px;">
            ✓ Scraping Job Completed Successfully
        </h2>

        <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #555; margin-top: 0;">Job Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; font-weight: bold; width: 150px;">Job ID:</td>
                    <td style="padding: 8px;">{job_id}</td>
                </tr>
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 8px; font-weight: bold;">URL:</td>
                    <td style="padding: 8px;"><a href="{job_url}">{job_url}</a></td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Status:</td>
                    <td style="padding: 8px; color: #28a745; font-weight: bold;">SUCCESS</td>
                </tr>
                {f'<tr style="background-color: #f5f5f5;"><td style="padding: 8px; font-weight: bold;">Duration:</td><td style="padding: 8px;">{duration:.1f} seconds</td></tr>' if duration else ''}
            </table>
        </div>

        <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #555; margin-top: 0;">Statistics</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; font-weight: bold; width: 150px;">Pages Crawled:</td>
                    <td style="padding: 8px;">{stats.get('pages_crawled', 0) if stats else 0}</td>
                </tr>
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 8px; font-weight: bold;">Products Found:</td>
                    <td style="padding: 8px;">{stats.get('products_found', 0) if stats else 0}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Products Stored:</td>
                    <td style="padding: 8px; color: #28a745; font-weight: bold;">{stats.get('products_stored', 0) if stats else 0}</td>
                </tr>
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 8px; font-weight: bold;">Images Downloaded:</td>
                    <td style="padding: 8px;">{stats.get('images_downloaded', 0) if stats else 0}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Errors:</td>
                    <td style="padding: 8px;">{stats.get('errors', 0) if stats else 0}</td>
                </tr>
            </table>
        </div>

        <div style="margin-top: 20px; padding: 15px; background-color: #e7f3ff; border-left: 4px solid #2196F3; border-radius: 5px;">
            <p style="margin: 0; color: #555;">
                <strong>Next Steps:</strong><br>
                View your scraped products at: <a href="http://localhost:8000/jewels">http://localhost:8000/jewels</a>
            </p>
        </div>

        <p style="margin-top: 20px; font-size: 12px; color: #999; text-align: center;">
            Agentic Jewelry Intelligence Framework<br>
            Automated notification - do not reply
        </p>
    </div>
</body>
</html>
"""
    else:
        body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px;">
        <h2 style="color: #dc3545; border-bottom: 3px solid #dc3545; padding-bottom: 10px;">
            ✗ Scraping Job Failed
        </h2>

        <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #555; margin-top: 0;">Job Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; font-weight: bold; width: 150px;">Job ID:</td>
                    <td style="padding: 8px;">{job_id}</td>
                </tr>
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 8px; font-weight: bold;">URL:</td>
                    <td style="padding: 8px;"><a href="{job_url}">{job_url}</a></td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Status:</td>
                    <td style="padding: 8px; color: #dc3545; font-weight: bold;">FAILED</td>
                </tr>
                {f'<tr style="background-color: #f5f5f5;"><td style="padding: 8px; font-weight: bold;">Duration:</td><td style="padding: 8px;">{duration:.1f} seconds</td></tr>' if duration else ''}
            </table>
        </div>

        <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
            <h3 style="color: #856404; margin-top: 0;">Error Details</h3>
            <p style="color: #856404; margin: 0; font-family: monospace; background-color: #fffbf0; padding: 10px; border-radius: 3px;">
                {error_message or "Unknown error occurred"}
            </p>
        </div>

        <div style="background-color: white; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #555; margin-top: 0;">Partial Statistics</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; font-weight: bold; width: 150px;">Pages Crawled:</td>
                    <td style="padding: 8px;">{stats.get('pages_crawled', 0) if stats else 0}</td>
                </tr>
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 8px; font-weight: bold;">Products Found:</td>
                    <td style="padding: 8px;">{stats.get('products_found', 0) if stats else 0}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Products Stored:</td>
                    <td style="padding: 8px;">{stats.get('products_stored', 0) if stats else 0}</td>
                </tr>
                <tr style="background-color: #f5f5f5;">
                    <td style="padding: 8px; font-weight: bold;">Errors:</td>
                    <td style="padding: 8px; color: #dc3545; font-weight: bold;">{stats.get('errors', 0) if stats else 0}</td>
                </tr>
            </table>
        </div>

        <div style="margin-top: 20px; padding: 15px; background-color: #f8d7da; border-left: 4px solid #dc3545; border-radius: 5px;">
            <p style="margin: 0; color: #721c24;">
                <strong>Action Required:</strong><br>
                Please check the logs for more details and retry the job if necessary.
            </p>
        </div>

        <p style="margin-top: 20px; font-size: 12px; color: #999; text-align: center;">
            Agentic Jewelry Intelligence Framework<br>
            Automated notification - do not reply
        </p>
    </div>
</body>
</html>
"""

    return subject, body



def _send_email(subject: str, body: str) -> None:
    """Send an email using SMTP with HTML body."""

    # Validate configuration
    if not settings.email_host or not settings.email_host_user:
        raise ValueError("Email is not configured. Missing SMTP settings.")

    # Construct email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from or settings.email_host_user
    msg["To"] = settings.email_to
    logger.info(f"Email notification from {settings.email_from} with pass: {settings.email_host_password}")
    # Attach HTML content
    html_part = MIMEText(body, "html")
    msg.attach(html_part)

    # Send email
    with smtplib.SMTP(settings.email_host, settings.email_port) as server:
        if settings.email_use_tls:
            server.starttls()

        server.login(settings.email_host_user, settings.email_host_password)
        server.send_message(msg)
