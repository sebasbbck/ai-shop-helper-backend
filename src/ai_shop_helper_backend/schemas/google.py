from datetime import datetime

from sqlmodel import SQLModel


class GoogleConnectResponse(SQLModel):
    auth_url: str


class GoogleStatusResponse(SQLModel):
    connected: bool
    google_email: str | None = None
    token_expires_at: datetime | None = None


class GoogleCallbackSuccess(SQLModel):
    message: str
    google_email: str


class GA4ReportRequest(SQLModel):
    date_ranges: list[dict] = [{"startDate": "30daysAgo", "endDate": "today"}]
    metrics: list[dict] = [
        {"name": "sessions"},
        {"name": "activeUsers"},
        {"name": "screenPageViews"},
    ]
    dimensions: list[dict] = []
    limit: int = 10


class GA4RealtimeRequest(SQLModel):
    metrics: list[dict] = [{"name": "activeUsers"}]
    dimensions: list[dict] = [{"name": "country"}]
    limit: int = 10


class SearchConsoleQueryRequest(SQLModel):
    site_url: str
    start_date: str
    end_date: str
    dimensions: list[str] = ["query"]
    row_limit: int = 10
