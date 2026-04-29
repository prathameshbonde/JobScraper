import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

from models.job import Job

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends HTML-formatted job notification emails via SMTP."""

    def __init__(self, config: dict):
        self.smtp_server = config["smtp_server"]
        self.smtp_port = config["smtp_port"]
        self.sender_email = config["sender_email"]
        self.recipients = config["recipients"]
        self.subject_prefix = config.get("subject_prefix", "[JobScraper]")
        self.send_empty_report = config.get("send_empty_report", False)

    def send_jobs(self, jobs: list[Job], dry_run: bool = False):
        """Send an email with new job listings, grouped by portal."""
        if not jobs and not self.send_empty_report:
            logger.info("No new jobs found and send_empty_report is disabled. Skipping email.")
            return

        subject = self._build_subject(jobs)
        html_body = self._build_html(jobs)

        if dry_run:
            logger.info(f"[DRY RUN] Would send email to {self.recipients}")
            logger.info(f"[DRY RUN] Subject: {subject}")
            logger.info(f"[DRY RUN] {len(jobs)} jobs in email body")
            return

        self._send(subject, html_body)

    def send_test(self):
        """Send a test email to verify SMTP configuration."""
        subject = f"{self.subject_prefix} Test Email"
        html_body = """
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; background: #1a1a2e; color: #e0e0e0;">
            <div style="max-width: 600px; margin: 0 auto; background: #16213e; padding: 30px; border-radius: 12px;">
                <h1 style="color: #00d4aa;">✅ JobScraper Email Test</h1>
                <p>If you're reading this, your SMTP configuration is working correctly!</p>
                <p style="color: #888; font-size: 12px;">Sent at: {timestamp}</p>
            </div>
        </body>
        </html>
        """.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        self._send(subject, html_body)
        logger.info("Test email sent successfully!")

    def _build_subject(self, jobs: list[Job]) -> str:
        """Build the email subject line."""
        if not jobs:
            return f"{self.subject_prefix} No new jobs found"

        portal_count = len(set(j.portal_name for j in jobs))
        portal_text = f"{portal_count} portal{'s' if portal_count > 1 else ''}"
        return f"{self.subject_prefix} {len(jobs)} new job{'s' if len(jobs) > 1 else ''} found across {portal_text}"

    def _build_html(self, jobs: list[Job]) -> str:
        """Build a clean HTML email body with jobs grouped by portal."""
        now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        if not jobs:
            return f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; background: #1a1a2e; color: #e0e0e0;">
                <div style="max-width: 700px; margin: 0 auto; background: #16213e; padding: 30px; border-radius: 12px;">
                    <h1 style="color: #00d4aa; margin-bottom: 5px;">🔍 Job Scraper Report</h1>
                    <p style="color: #888; margin-top: 0;">{now}</p>
                    <p style="font-size: 16px;">No new jobs found today. We'll check again tomorrow!</p>
                </div>
            </body>
            </html>
            """

        # Group jobs by portal
        portals: dict[str, list[Job]] = {}
        for job in jobs:
            portals.setdefault(job.portal_name, []).append(job)

        # Build portal sections
        portal_sections = ""
        for portal_name, portal_jobs in portals.items():
            job_rows = ""
            for job in portal_jobs:
                date_str = job.posted_date.strftime("%b %d, %Y") if job.posted_date else "Unknown"
                job_rows += f"""
                <tr>
                    <td style="padding: 12px 16px; border-bottom: 1px solid #2a2a4a;">
                        <a href="{job.url}" style="color: #00d4aa; text-decoration: none; font-weight: 600; font-size: 15px;">
                            {job.title}
                        </a>
                        <div style="color: #999; font-size: 13px; margin-top: 4px;">
                            📍 {job.location or 'Not specified'} &nbsp;&nbsp;|&nbsp;&nbsp; 📅 {date_str}
                        </div>
                    </td>
                </tr>
                """

            portal_sections += f"""
            <div style="margin-bottom: 24px;">
                <h2 style="color: #e0e0e0; font-size: 18px; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 2px solid #00d4aa;">
                    🏢 {portal_name} <span style="color: #888; font-size: 14px; font-weight: normal;">({len(portal_jobs)} job{'s' if len(portal_jobs) > 1 else ''})</span>
                </h2>
                <table style="width: 100%; border-collapse: collapse; background: #1a1a3e; border-radius: 8px; overflow: hidden;">
                    {job_rows}
                </table>
            </div>
            """

        return f"""
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; background: #1a1a2e; color: #e0e0e0;">
            <div style="max-width: 700px; margin: 0 auto; background: #16213e; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                <h1 style="color: #00d4aa; margin-bottom: 5px;">🔍 Job Scraper Report</h1>
                <p style="color: #888; margin-top: 0;">{now}</p>
                <div style="background: #0d1b2a; padding: 16px; border-radius: 8px; margin-bottom: 24px; text-align: center;">
                    <span style="font-size: 28px; font-weight: bold; color: #00d4aa;">{len(jobs)}</span>
                    <span style="font-size: 16px; color: #ccc;"> new job{'s' if len(jobs) > 1 else ''} found across </span>
                    <span style="font-size: 20px; font-weight: bold; color: #FF9F43;">{len(portals)}</span>
                    <span style="font-size: 16px; color: #ccc;"> portal{'s' if len(portals) > 1 else ''}</span>
                </div>
                {portal_sections}
                <p style="color: #666; font-size: 12px; text-align: center; margin-top: 24px; border-top: 1px solid #2a2a4a; padding-top: 16px;">
                    Sent by JobScraper • {now}
                </p>
            </div>
        </body>
        </html>
        """

    def _send(self, subject: str, html_body: str):
        """Send an email via SMTP."""
        username = os.getenv("SMTP_USERNAME")
        password = os.getenv("SMTP_PASSWORD")

        if not username or not password:
            logger.error("SMTP_USERNAME and SMTP_PASSWORD must be set in .env file")
            raise ValueError("Missing SMTP credentials in environment variables")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = ", ".join(self.recipients)

        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.sendmail(self.sender_email, self.recipients, msg.as_string())
            logger.info(f"Email sent to {self.recipients}")
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")
            raise
