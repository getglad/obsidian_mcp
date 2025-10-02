"""Google Calendar integration for Obsidian MCP."""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request  # type: ignore[import-not-found]
from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
from google_auth_oauthlib.flow import (
    InstalledAppFlow,  # type: ignore[import-not-found, import-untyped]
)
from googleapiclient.discovery import build  # type: ignore[import-not-found, import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-not-found, import-untyped]

logger = logging.getLogger(__name__)

# Restricted scope - only calendar events, no calendar management
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Token storage directory
CREDENTIALS_DIR = Path(".credentials")
TOKEN_FILE = CREDENTIALS_DIR / "token.json"


class CalendarError(Exception):
    """Base exception for calendar operations."""

    pass


class CalendarAuthError(CalendarError):
    """Raised when authentication fails."""

    pass


class CalendarService:
    """Manages Google Calendar API interactions."""

    def __init__(self, credentials_path: str, calendar_id: str = "primary", headless: bool = False):
        """
        Initialize calendar service.

        Args:
            credentials_path: Path to OAuth2 credentials.json
            calendar_id: Google Calendar ID (default: "primary")
            headless: If True, use console-based OAuth flow instead of browser (default: False)
        """
        self.credentials_path = Path(credentials_path)
        self.calendar_id = calendar_id
        self.headless = headless
        self._service: Any | None = None

        if not self.credentials_path.exists():
            raise CalendarAuthError(
                f"Google Calendar credentials not found at: {self.credentials_path}\n\n"
                "To set up Google Calendar integration:\n"
                "1. Go to https://console.cloud.google.com/\n"
                "2. Create a project (or select existing)\n"
                "3. Enable Google Calendar API\n"
                "4. Create OAuth 2.0 credentials (Desktop app type)\n"
                "5. Download credentials.json and save to this location\n\n"
                "See docs/CALENDAR.md for detailed setup instructions."
            )

    def _get_credentials(self) -> Credentials:
        """
        Get or refresh OAuth2 credentials.

        Returns:
            Valid credentials

        Raises:
            CalendarAuthError: If authentication fails
        """
        creds = None

        # Ensure credentials directory exists
        CREDENTIALS_DIR.mkdir(exist_ok=True)

        # Load existing token if available
        if TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load token: {e}")
                creds = None

        # Refresh or obtain new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired credentials...")
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}")
                    raise CalendarAuthError(
                        f"Failed to refresh access token: {e}\n\n"
                        "Your refresh token may be invalid or revoked.\n"
                        "To fix: Delete .credentials/token.json and re-authorize."
                    ) from e
            else:
                # First time authorization
                try:
                    logger.info("Starting OAuth2 authorization flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), SCOPES
                    )

                    if self.headless:
                        # Console-based flow for headless environments
                        logger.info("Running in headless mode - using console-based OAuth")
                        logger.info("=" * 60)
                        logger.info("AUTHORIZATION REQUIRED")
                        logger.info("=" * 60)
                        creds = flow.run_console()
                        logger.info("=" * 60)
                    else:
                        # Browser-based flow (default)
                        logger.info("Opening browser for authorization...")
                        creds = flow.run_local_server(port=0)

                    logger.info("✅ Authorization successful!")
                except Exception as e:
                    logger.error(f"OAuth authorization failed: {e}")
                    raise CalendarAuthError(
                        f"OAuth authorization failed: {e}\n\n"
                        "Common issues:\n"
                        "- Incorrect credentials.json file (must be OAuth Desktop app type)\n"
                        "- Calendar API not enabled in Google Cloud Console\n"
                        "- Network connection issues\n\n"
                        "See docs/CALENDAR.md for troubleshooting."
                    ) from e

            # Save credentials for future use
            try:
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
                os.chmod(TOKEN_FILE, 0o600)  # Restrict permissions
                logger.info(f"Saved credentials to {TOKEN_FILE}")
            except Exception as e:
                logger.warning(f"Failed to save token: {e}")

        return creds  # type: ignore[no-any-return]

    def get_service(self) -> Any:
        """
        Get or create calendar service.

        Returns:
            Google Calendar API service

        Raises:
            CalendarAuthError: If authentication fails
        """
        if self._service is None:
            creds = self._get_credentials()
            try:
                self._service = build("calendar", "v3", credentials=creds)
            except Exception as e:
                raise CalendarAuthError(f"Failed to build calendar service: {e}") from e

        return self._service

    def create_event(
        self,
        summary: str,
        start_datetime: datetime,
        end_datetime: datetime,
        description: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a calendar event.

        Args:
            summary: Event title
            start_datetime: Event start time
            end_datetime: Event end time
            description: Optional event description
            location: Optional location

        Returns:
            Created event details

        Raises:
            CalendarError: If event creation fails
        """
        service = self.get_service()

        event_body: dict[str, Any] = {
            "summary": summary,
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": "UTC",
            },
        }

        if description:
            event_body["description"] = description

        if location:
            event_body["location"] = location

        try:
            event = service.events().insert(calendarId=self.calendar_id, body=event_body).execute()
            logger.info(f"Created calendar event: {event.get('id')}")
            return event  # type: ignore[no-any-return]
        except HttpError as e:
            raise CalendarError(f"Failed to create event: {e}") from e

    def update_event(
        self,
        event_id: str,
        summary: str | None = None,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing calendar event.

        Args:
            event_id: Event ID to update
            summary: New event title
            start_datetime: New start time
            end_datetime: New end time
            description: New description
            location: New location

        Returns:
            Updated event details

        Raises:
            CalendarError: If update fails
        """
        service = self.get_service()

        try:
            # Get existing event
            event = service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()

            # Update fields
            if summary is not None:
                event["summary"] = summary
            if start_datetime is not None:
                event["start"] = {
                    "dateTime": start_datetime.isoformat(),
                    "timeZone": "UTC",
                }
            if end_datetime is not None:
                event["end"] = {
                    "dateTime": end_datetime.isoformat(),
                    "timeZone": "UTC",
                }
            if description is not None:
                event["description"] = description
            if location is not None:
                event["location"] = location

            # Update event
            updated_event = (
                service.events()
                .update(calendarId=self.calendar_id, eventId=event_id, body=event)
                .execute()
            )
            logger.info(f"Updated calendar event: {event_id}")
            return updated_event  # type: ignore[no-any-return]
        except HttpError as e:
            raise CalendarError(f"Failed to update event: {e}") from e

    def delete_event(self, event_id: str) -> None:
        """
        Delete a calendar event.

        Args:
            event_id: Event ID to delete

        Raises:
            CalendarError: If deletion fails
        """
        service = self.get_service()

        try:
            service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
            logger.info(f"Deleted calendar event: {event_id}")
        except HttpError as e:
            raise CalendarError(f"Failed to delete event: {e}") from e

    def list_events(
        self,
        max_results: int = 10,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        List upcoming calendar events.

        Args:
            max_results: Maximum number of events to return
            time_min: Start of time range (default: now)
            time_max: End of time range (default: 7 days from now)

        Returns:
            List of event details

        Raises:
            CalendarError: If listing fails
        """
        service = self.get_service()

        if time_min is None:
            time_min = datetime.now(timezone.utc)
        if time_max is None:
            time_max = time_min + timedelta(days=7)

        try:
            events_result = (
                service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min.isoformat() + "Z",
                    timeMax=time_max.isoformat() + "Z",
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            logger.info(f"Retrieved {len(events)} calendar events")
            return events  # type: ignore[no-any-return]
        except HttpError as e:
            raise CalendarError(f"Failed to list events: {e}") from e

    def get_event(self, event_id: str) -> dict[str, Any]:
        """
        Get a specific calendar event.

        Args:
            event_id: Event ID

        Returns:
            Event details

        Raises:
            CalendarError: If retrieval fails
        """
        service = self.get_service()

        try:
            event = service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
            return event  # type: ignore[no-any-return]
        except HttpError as e:
            raise CalendarError(f"Failed to get event: {e}") from e
