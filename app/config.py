import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

# Data location can be overridden for tests or portable installs.
# Never point this at user data you do not intend to modify.
DATA_DIR = Path(os.environ.get("ASSISTANT_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
DOCS_DIR = DATA_DIR / "documents"
BACKUPS_DIR = DATA_DIR / "backups"
DB_PATH = Path(os.environ.get("ASSISTANT_DB_PATH", str(DATA_DIR / "assistant.db"))).expanduser().resolve()

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_dirs(name: str, defaults: list) -> list:
    raw = os.environ.get(name)
    if raw:
        items = [p.strip() for p in raw.split(";") if p.strip()]
        if items:
            return items
    return defaults


class Settings(BaseModel):
    app_name: str = "Assistente Virtual Pessoal"
    version: str = "1.1.0"
    host: str = "127.0.0.1"
    port: int = _env_int("ASSISTANT_PORT", 8765)
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    # Requested by the user and verified as installed on this machine.
    # qwen2.5-coder:7b needs ~5.2 GB VRAM at 4096 ctx, so the GTX 1660 Super
    # (6 GB) offloads part of the layers to CPU. qwen2.5:3b runs 100% on GPU.
    default_model: str = os.environ.get("ASSISTANT_MODEL", "qwen2.5-coder:7b")
    embedding_model: str = os.environ.get("ASSISTANT_EMBEDDING_MODEL", "nomic-embed-text")
    max_context_tokens: int = _env_int("ASSISTANT_NUM_CTX", 4096)
    max_output_tokens: int = _env_int("ASSISTANT_MAX_OUTPUT_TOKENS", 1024)
    temperature: float = 0.7
    max_history_messages: int = 15
    max_message_chars: int = 32000
    max_upload_mb: int = 25
    allowed_document_extensions: list[str] = [".pdf", ".txt", ".md"]
    authorization_ttl_seconds: int = 120

    # Local origins allowed to call the API from a browser.
    allowed_origins: list[str] = [
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    ]

    # Security Whitelist: directories the assistant is authorized to access.
    # By default: the application workspace and the user's Documents folder.
    authorized_directories: list[str] = _env_dirs(
        "ASSISTANT_AUTHORIZED_DIRS",
        [
            str(DATA_DIR),
            str(Path.home() / "Documents"),
            str(BASE_DIR),
        ],
    )


settings = Settings()
