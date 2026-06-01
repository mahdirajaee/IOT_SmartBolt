import os
from pathlib import Path


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

    raise RuntimeError(
        f"INTERNAL_API_KEY not configured for {service_name}: set the INTERNAL_API_KEY environment "
        f"variable (or JWT_SECRET_KEY, or provide a key at {key_file}). Refusing to auto-generate a "
        f"key, which would silently break inter-service auth when services run on different hosts."
    )
