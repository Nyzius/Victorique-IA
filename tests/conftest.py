import os
import tempfile
from pathlib import Path

# IMPORTANT: configure an isolated data directory BEFORE importing the app.
# Tests must never touch the real data/assistant.db.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="assistente-pessoal-testes-"))
_TEST_DATA = _TEST_ROOT / "data"

os.environ["ASSISTANT_DATA_DIR"] = str(_TEST_DATA)
os.environ["ASSISTANT_DB_PATH"] = str(_TEST_DATA / "assistant.db")
os.environ["ASSISTANT_TESTING"] = "1"
os.environ.setdefault("ASSISTANT_MODEL", os.environ.get("ASSISTANT_MODEL", "qwen2.5-coder:7b"))
# Nos testes, forcar Ollama como backend (mockado nos testes) para evitar
# tentar iniciar o llama-server real.
os.environ["ASSISTANT_DEFAULT_BACKEND"] = "ollama"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.memory.database import init_db  # noqa: E402

init_db()


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return _TEST_DATA


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app
    return TestClient(app, base_url="http://127.0.0.1:8765")
