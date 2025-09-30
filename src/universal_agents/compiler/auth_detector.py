"""Authentication detection for the agent compiler.

Scans .env files for API keys and storage/ for browser state files to
determine which providers the user has credentials for.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Map of env var names to auth keys
_API_KEY_ENV_VARS: dict[str, str] = {
    "OPENAI_API_KEY": "openai_key",
    "OPENROUTER_API_KEY": "openrouter_key",
}

# Map of storage state file patterns to auth keys
_STORAGE_STATE_FILES: dict[str, str] = {
    "claude_storage_state.json": "claude_storage",
    "gemini_storage_state.json": "gemini_storage",
    "gpt_storage_state.json": "gpt_storage",
    "pplx_storage_state.json": "pplx_storage",
}

# Env vars that point to custom storage state paths
_STORAGE_STATE_ENV_VARS: dict[str, str] = {
    "CLAUDE_STORAGE_STATE": "claude_storage",
    "GEMINI_STORAGE_STATE": "gemini_storage",
    "GPT_STORAGE_STATE": "gpt_storage",
    "PPLX_STORAGE_STATE": "pplx_storage",
}


@dataclass
class AuthStatus:
    """Detected authentication credentials."""

    available: dict[str, bool] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)

    def has(self, key: str) -> bool:
        return self.available.get(key, False)

    def summary_lines(self) -> list[str]:
        """Return human-readable status lines for display."""
        lines = []
        for key, found in sorted(self.available.items()):
            mark = "\u2713" if found else "\u2717"
            detail = self.details.get(key, "")
            label = key.replace("_", " ").title()
            line = f"  {mark} {label:<25s} {'found' if found else 'not found'}"
            if detail:
                line += f"  ({detail})"
            lines.append(line)
        return lines


class AuthDetector:
    """Detects available authentication for all providers.

    Checks:
      1. Environment variables (from os.environ and .env files)
      2. Browser storage state JSON files in the storage/ directory
      3. Env vars pointing to custom storage state paths
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        storage_dir: str | Path | None = None,
        env_file: str | Path | None = None,
    ):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.storage_dir = Path(storage_dir) if storage_dir else self.project_root / "storage"
        self.env_file = Path(env_file) if env_file else self.project_root / ".env"

    def detect(self) -> AuthStatus:
        """Scan for all available authentication and return status."""
        status = AuthStatus()

        # Load .env file into environment (if python-dotenv available)
        self._load_dotenv()

        # Check API key env vars
        for env_var, auth_key in _API_KEY_ENV_VARS.items():
            val = os.environ.get(env_var, "")
            if val:
                status.available[auth_key] = True
                # Show first 8 + last 4 chars for identification
                masked = f"{val[:8]}...{val[-4:]}" if len(val) > 16 else "***"
                status.details[auth_key] = masked
                logger.debug("Found %s \u2192 %s", env_var, auth_key)
            else:
                status.available[auth_key] = False

        # Check storage state files in storage/
        for filename, auth_key in _STORAGE_STATE_FILES.items():
            filepath = self.storage_dir / filename
            if filepath.is_file():
                valid = self._validate_storage_state(filepath)
                status.available[auth_key] = valid
                if valid:
                    status.details[auth_key] = str(filepath)
                    logger.debug("Found valid storage state: %s", filepath)
                else:
                    status.details[auth_key] = "file exists but invalid"
            else:
                status.available.setdefault(auth_key, False)

        # Check env vars pointing to custom storage state paths
        for env_var, auth_key in _STORAGE_STATE_ENV_VARS.items():
            custom_path = os.environ.get(env_var, "")
            if custom_path and Path(custom_path).is_file():
                valid = self._validate_storage_state(Path(custom_path))
                if valid:
                    status.available[auth_key] = True
                    status.details[auth_key] = custom_path
                    logger.debug("Found custom storage state from %s: %s", env_var, custom_path)

        # Copilot \u2014 check if CLI is available
        status.available["copilot_cli"] = self._check_copilot_cli()

        return status

    def _load_dotenv(self) -> None:
        """Load .env file if python-dotenv is available."""
        if self.env_file.is_file():
            try:
                from dotenv import load_dotenv
                load_dotenv(self.env_file, override=False)
                logger.debug("Loaded .env from %s", self.env_file)
            except ImportError:
                logger.debug("python-dotenv not installed, reading .env manually")
                self._load_dotenv_manual()

    def _load_dotenv_manual(self) -> None:
        """Minimal .env parser (no quotes, no interpolation)."""
        try:
            for line in self.env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            pass

    @staticmethod
    def _validate_storage_state(path: Path) -> bool:
        """Check if a storage state JSON file is valid and non-empty."""
        try:
            data = json.loads(path.read_text())
            # Playwright storage state has "cookies" and/or "origins"
            if isinstance(data, dict):
                has_cookies = bool(data.get("cookies"))
                has_origins = bool(data.get("origins"))
                return has_cookies or has_origins
            return False
        except (json.JSONDecodeError, OSError):
            return False

    @staticmethod
    def _check_copilot_cli() -> bool:
        """Check if GitHub Copilot CLI is installed."""
        import shutil
        return shutil.which("copilot") is not None or shutil.which("github-copilot-cli") is not None
