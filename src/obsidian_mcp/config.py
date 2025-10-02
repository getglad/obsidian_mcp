"""Configuration management for Obsidian MCP server."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar


@dataclass(slots=True, frozen=True)
class ObsidianConfig:
    """Configuration for Obsidian vault access."""

    DEFAULT_FILE_EXTENSIONS: ClassVar[list[str]] = [".md", ".canvas"]
    DEFAULT_EXCLUDE_FOLDERS: ClassVar[list[str]] = [".obsidian", ".trash", "templates"]

    vault_path: Path
    file_extensions: list[str] = field(
        default_factory=lambda: ObsidianConfig.DEFAULT_FILE_EXTENSIONS.copy()
    )
    exclude_folders: list[str] = field(
        default_factory=lambda: ObsidianConfig.DEFAULT_EXCLUDE_FOLDERS.copy()
    )
    max_results: int = 100
    snippet_length: int = 200

    # Google Calendar integration (optional)
    calendar_enabled: bool = False
    calendar_credentials_path: Path | None = None
    calendar_id: str = "primary"
    calendar_headless: bool = False
    obsidian_url_base: str = "obsidian://open?vault=MyVault&file="

    @classmethod
    def from_env(cls) -> "ObsidianConfig":
        """Create configuration from environment variables."""
        vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
        if not vault_path:
            raise ValueError("OBSIDIAN_VAULT_PATH environment variable must be set")

        # Calendar configuration (optional)
        calendar_creds_path = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH")
        calendar_enabled = calendar_creds_path is not None

        return cls(
            vault_path=Path(vault_path).expanduser().resolve(),
            max_results=int(os.getenv("OBSIDIAN_MAX_RESULTS", "100")),
            snippet_length=int(os.getenv("OBSIDIAN_SNIPPET_LENGTH", "200")),
            calendar_enabled=calendar_enabled,
            calendar_credentials_path=(
                Path(calendar_creds_path).expanduser().resolve() if calendar_creds_path else None
            ),
            calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            calendar_headless=os.getenv("GOOGLE_CALENDAR_HEADLESS", "false").lower()
            in ("true", "1", "yes"),
            obsidian_url_base=os.getenv(
                "OBSIDIAN_VAULT_URL_BASE", "obsidian://open?vault=MyVault&file="
            ),
        )

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {self.vault_path}")
        if not self.vault_path.is_dir():
            raise ValueError(f"Vault path is not a directory: {self.vault_path}")
        if self.vault_path.is_symlink():
            raise ValueError(f"Vault path cannot be a symbolic link: {self.vault_path}")
        if not os.access(self.vault_path, os.R_OK):
            raise ValueError(f"Vault path is not readable: {self.vault_path}")
        if self.max_results <= 0:
            raise ValueError(f"max_results must be positive, got {self.max_results}")
        if self.snippet_length <= 0:
            raise ValueError(f"snippet_length must be positive, got {self.snippet_length}")
