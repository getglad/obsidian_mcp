"""Tests for configuration module."""

from pathlib import Path

import pytest

from obsidian_mcp.config import ObsidianConfig


def test_config_creation(test_vault_path: Path) -> None:
    """Test creating configuration with valid path."""
    config = ObsidianConfig(vault_path=test_vault_path)
    assert config.vault_path == test_vault_path
    assert config.max_results == 100
    assert config.snippet_length == 200


def test_config_with_custom_values(test_vault_path: Path) -> None:
    """Test configuration with custom values."""
    config = ObsidianConfig(
        vault_path=test_vault_path,
        max_results=50,
        snippet_length=150,
        file_extensions=[".md"],
        exclude_folders=[".obsidian"],
    )
    assert config.max_results == 50
    assert config.snippet_length == 150
    assert config.file_extensions == [".md"]
    assert config.exclude_folders == [".obsidian"]


def test_config_nonexistent_path(tmp_path: Path) -> None:
    """Test that nonexistent path raises error."""
    nonexistent = tmp_path / "nonexistent"
    with pytest.raises(ValueError, match="Vault path does not exist"):
        ObsidianConfig(vault_path=nonexistent)


def test_config_file_instead_of_directory(tmp_path: Path) -> None:
    """Test that file path raises error."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")
    with pytest.raises(ValueError, match="not a directory"):
        ObsidianConfig(vault_path=file_path)


def test_config_invalid_max_results(test_vault_path: Path) -> None:
    """Test that invalid max_results raises error."""
    with pytest.raises(ValueError, match="max_results must be positive"):
        ObsidianConfig(vault_path=test_vault_path, max_results=0)

    with pytest.raises(ValueError, match="max_results must be positive"):
        ObsidianConfig(vault_path=test_vault_path, max_results=-1)


def test_config_invalid_snippet_length(test_vault_path: Path) -> None:
    """Test that invalid snippet_length raises error."""
    with pytest.raises(ValueError, match="snippet_length must be positive"):
        ObsidianConfig(vault_path=test_vault_path, snippet_length=0)


def test_config_from_env(test_vault_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test creating configuration from environment variables."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(test_vault_path))
    monkeypatch.setenv("OBSIDIAN_MAX_RESULTS", "50")
    monkeypatch.setenv("OBSIDIAN_SNIPPET_LENGTH", "150")

    config = ObsidianConfig.from_env()
    assert config.vault_path == test_vault_path
    assert config.max_results == 50
    assert config.snippet_length == 150


def test_config_from_env_missing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that missing env var raises error."""
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
    with pytest.raises(ValueError, match="OBSIDIAN_VAULT_PATH.*must be set"):
        ObsidianConfig.from_env()


def test_config_immutable(test_vault_path: Path) -> None:
    """Test that config is frozen/immutable."""
    config = ObsidianConfig(vault_path=test_vault_path)
    with pytest.raises(AttributeError):
        config.max_results = 200  # type: ignore
