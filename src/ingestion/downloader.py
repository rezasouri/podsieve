from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Literal, Mapping
from urllib.parse import urlparse

from ..core.commands import require_executable, run_command
from ..core.config import config_value
from ..core.errors import StageError


LOGGER = logging.getLogger(__name__)

UrlSource = Literal["youtube", "castbox"]

_ESCAPED_URL_SEPARATOR = re.compile(r"\\([:/?=&])")
_COOKIE_KEYRING_ERRORS = (
    "Item does not exist",
    "secretstorage.exceptions.ItemNotFoundException",
    "Object does not exist at path",
)
_YOUTUBE_AUTH_COOKIES = {
    "SID",
    "HSID",
    "SSID",
    "APISID",
    "SAPISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "LOGIN_INFO",
    "LSID",
    "__Host-1PLSID",
    "__Host-3PLSID",
}
_YOUTUBE_HOSTS = ("youtube.com", "youtube-nocookie.com", "youtu.be")
_CASTBOX_HOSTS = ("castbox.fm",)


def normalize_download_url(url: str) -> str:
    """Normalize a pasted HTTP(S) URL without changing its encoded path/query."""
    normalized = _ESCAPED_URL_SEPARATOR.sub(r"\1", url.strip())
    parsed = urlparse(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise StageError("download", f"invalid media URL: {url}")
    if "\\" in normalized:
        raise StageError(
            "download",
            "URL contains a backslash; pass it quoted without escaping '?' or '='",
        )
    return normalized


def normalize_youtube_url(url: str) -> str:
    """Backward-compatible alias for callers that normalize YouTube URLs."""
    return normalize_download_url(url)


def detect_url_source(url: str) -> UrlSource:
    """Return the supported provider represented by *url*."""
    normalized = normalize_download_url(url)
    hostname = (urlparse(normalized).hostname or "").lower().rstrip(".")
    if _host_matches(hostname, _YOUTUBE_HOSTS):
        return "youtube"
    if _host_matches(hostname, _CASTBOX_HOSTS):
        return "castbox"
    raise StageError(
        "download",
        f"unsupported media URL host: {hostname}. Supported providers: YouTube, Castbox.",
    )


def download_url_audio(
    *,
    url: str,
    output_template: Path,
    config: Mapping[str, Any],
    overwrite: bool = False,
) -> tuple[Path, UrlSource]:
    """Download audio from a supported YouTube or Castbox URL."""
    normalized_url = normalize_download_url(url)
    source = detect_url_source(normalized_url)
    output = _download_audio(
        url=normalized_url,
        source=source,
        output_template=output_template,
        config=config,
        overwrite=overwrite,
    )
    return output, source


def download_youtube_audio(
    *,
    url: str,
    output_template: Path,
    config: Mapping[str, Any],
    overwrite: bool = False,
) -> Path:
    """Download one YouTube video's audio.

    Kept for compatibility. New ingestion code should call ``download_url_audio``.
    """
    normalized_url = normalize_download_url(url)
    if detect_url_source(normalized_url) != "youtube":
        raise StageError("download", "download_youtube_audio requires a YouTube URL")
    return _download_audio(
        url=normalized_url,
        source="youtube",
        output_template=output_template,
        config=config,
        overwrite=overwrite,
    )


def _download_audio(
    *,
    url: str,
    source: UrlSource,
    output_template: Path,
    config: Mapping[str, Any],
    overwrite: bool,
) -> Path:
    stage = "download"
    template = Path(output_template).expanduser()
    raw_dir = template.parent
    output_stem = _template_stem(template)
    executable = require_executable("yt-dlp", stage)
    raw_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(raw_dir.glob(f"{output_stem}.*"))
    if existing and not overwrite:
        if len(existing) == 1:
            LOGGER.info("stage=download status=skipped existing=%s", existing[0])
            return existing[0].resolve()

        joined = ", ".join(str(path) for path in existing)
        raise StageError(
            stage,
            f"multiple raw outputs already exist: {joined}. Pass --overwrite to replace them.",
        )
    if overwrite:
        for path in existing:
            if path.is_file():
                path.unlink()

    command = [
        executable,
        "--no-playlist",
        "--print",
        "after_move:filepath",
    ]

    js_runtimes = config_value(config, "download", "js_runtimes")
    if js_runtimes:
        command.extend(["--js-runtimes", str(js_runtimes)])

    remote_components = config_value(config, "download", "remote_components")
    if remote_components:
        command.extend(["--remote-components", str(remote_components)])

    cookies_file = None
    cookies_browser = None
    if source == "youtube":
        cookies_file = config_value(config, "download", "cookies_file")
        cookies_browser = config_value(config, "download", "cookies_from_browser")
        if cookies_file:
            cookies_path = Path(str(cookies_file)).expanduser()
            if not cookies_path.is_file():
                raise StageError(
                    stage,
                    f"configured cookies file does not exist: {cookies_path}. "
                    "Export YouTube cookies in Netscape format or set "
                    "download.cookies_file: null.",
                )
            if not _has_youtube_auth_cookies(cookies_path):
                raise StageError(
                    stage,
                    f"configured cookies file does not contain non-empty YouTube "
                    f"auth cookies: {cookies_path}. Export cookies from a browser "
                    "where YouTube is signed in, using Netscape cookies.txt format.",
                )
            command.extend(["--cookies", str(cookies_path)])
        elif cookies_browser:
            command.extend(["--cookies-from-browser", str(cookies_browser)])

    default_format = "251/140/bestaudio" if source == "youtube" else "bestaudio/best"
    source_format = config_value(config, "download", f"{source}_format")
    selected_format = source_format or config_value(
        config, "download", "format", default_format
    )
    command.extend(
        [
            "-f",
            str(selected_format),
            "-x",
            "--audio-format",
            str(config_value(config, "download", "audio_format", "opus")),
            "--force-overwrites" if overwrite else "--no-overwrites",
            "-o",
            str(template),
            url,
        ]
    )

    try:
        result = run_command(command, stage=stage)
    except StageError as exc:
        hint = _download_failure_hint(
            exc.message,
            cookies_file=cookies_file,
            cookies_browser=cookies_browser,
        )
        if hint:
            raise StageError(stage, f"{exc.message}\nHint: {hint}") from exc
        raise
    printed_paths = [
        Path(line.strip()).expanduser()
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    for path in reversed(printed_paths):
        candidate = path if path.is_absolute() else (Path.cwd() / path)
        if (
            candidate.is_file()
            and _is_inside(candidate, raw_dir)
            and candidate.name.startswith(f"{output_stem}.")
        ):
            return candidate.resolve()

    generated = sorted(path for path in raw_dir.glob(f"{output_stem}.*") if path.is_file())
    if len(generated) == 1:
        return generated[0].resolve()
    detail = (result.stderr or result.stdout).strip()
    if len(detail) > 2000:
        detail = detail[-2000:]
    suffix = f" yt-dlp output: {detail}" if detail else ""
    raise StageError(
        stage,
        f"yt-dlp finished but no unambiguous output was found in {raw_dir}.{suffix}",
    )


def _download_failure_hint(
    message: str,
    *,
    cookies_file: Any,
    cookies_browser: Any,
) -> str | None:
    if cookies_browser and not cookies_file and any(
        marker in message for marker in _COOKIE_KEYRING_ERRORS
    ):
        return (
            "yt-dlp failed while decrypting Chrome cookies through the desktop "
            "keyring. Export YouTube cookies to a Netscape cookies.txt file and "
            "set download.cookies_file to that path, or unlock/repair GNOME "
            "Keyring and retry."
        )

    if "Sign in to confirm" in message and "not a bot" in message:
        return (
            "YouTube requires authenticated cookies for this request. Set "
            "download.cookies_file to an exported Netscape cookies.txt file, or "
            "configure download.cookies_from_browser with a browser profile "
            "yt-dlp can decrypt."
        )
    return None


def _has_youtube_auth_cookies(cookies_path: Path) -> bool:
    with cookies_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.startswith("#HttpOnly_"):
                line = line.removeprefix("#HttpOnly_")
            elif not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) < 7:
                continue

            domain, name, value = parts[0], parts[5], parts[6]
            if (
                ("youtube.com" in domain or "google.com" in domain)
                and name in _YOUTUBE_AUTH_COOKIES
                and bool(value)
            ):
                return True
    return False


def _host_matches(hostname: str, domains: tuple[str, ...]) -> bool:
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)


def _template_stem(output_template: Path) -> str:
    marker = ".%(ext)s"
    name = output_template.name
    if not name.endswith(marker):
        raise StageError(
            "download",
            f"output template must end with {marker!r}: {output_template}",
        )
    stem = name[: -len(marker)]
    if not stem:
        raise StageError("download", f"output template has no source stem: {output_template}")
    return stem


def _is_inside(path: Path, root: Path) -> bool:
    resolved_path = path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents
