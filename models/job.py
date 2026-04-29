from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    """Represents a single job listing scraped from a career portal."""

    portal_name: str
    job_id: str
    title: str
    url: str
    location: str = ""
    posted_date: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "portal_name": self.portal_name,
            "job_id": self.job_id,
            "title": self.title,
            "url": self.url,
            "location": self.location,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "scraped_at": self.scraped_at.isoformat(),
        }

    def __str__(self) -> str:
        date_str = self.posted_date.strftime("%b %d, %Y") if self.posted_date else "Unknown"
        return f"[{self.portal_name}] {self.title} | {self.location} | Posted: {date_str}"
