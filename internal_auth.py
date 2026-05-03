import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_internal_api_key(service_name: str = "service") -> str:
    explicit_key = os.getenv("INTERNAL_API_KEY")
    if explicit_key:
        return explicit_key

    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if jwt_secret and jwt_secret != "default-secret-key":
        return jwt_secret

    key_file = Path(os.getenv("INTERNAL_API_KEY_FILE", Path(__file__).resolve().with_name(".internal_api_key")))
    if key_file.exists():
        existing_key = key_file.read_text(encoding="utf-8").strip()
        if existing_key:
            return existing_key

    generated_key = secrets.token_hex(32)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(generated_key)
    except FileExistsError:
        existing_key = key_file.read_text(encoding="utf-8").strip()
        if existing_key:
            return existing_key
        key_file.write_text(generated_key, encoding="utf-8")

    logger.warning(
        "INTERNAL_API_KEY not configured - generated a shared local key for %s at %s",
        service_name,
        key_file
    )
    return generated_key
