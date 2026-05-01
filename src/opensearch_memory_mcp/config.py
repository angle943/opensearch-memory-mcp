"""Configuration loaded from config.json in the project root."""

import json
from pathlib import Path
from pydantic import BaseModel

# Config file lives in the project root, right next to pyproject.toml
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"

DEFAULTS = {
    "opensearch_url": "http://localhost:9200",
    "opensearch_user": "",
    "opensearch_password": "",
    "opensearch_verify_certs": False,
    "opensearch_model_id": "",
    "embedding_dimension": 768,
    "index_prefix": "memory",
}


class Settings(BaseModel):
    opensearch_url: str = DEFAULTS["opensearch_url"]
    opensearch_user: str = DEFAULTS["opensearch_user"]
    opensearch_password: str = DEFAULTS["opensearch_password"]
    opensearch_verify_certs: bool = DEFAULTS["opensearch_verify_certs"]
    opensearch_model_id: str = DEFAULTS["opensearch_model_id"]
    embedding_dimension: int = DEFAULTS["embedding_dimension"]
    index_prefix: str = DEFAULTS["index_prefix"]

    @property
    def interactions_index(self) -> str:
        return f"{self.index_prefix}-interactions"

    @property
    def sessions_index(self) -> str:
        return f"{self.index_prefix}-sessions"

    @property
    def ingest_pipeline(self) -> str:
        return f"{self.index_prefix}-nlp-pipeline"

    @property
    def search_pipeline(self) -> str:
        return f"{self.index_prefix}-search-pipeline"

    @property
    def http_auth(self) -> tuple[str, str] | None:
        if self.opensearch_user and self.opensearch_password:
            return (self.opensearch_user, self.opensearch_password)
        return None


def load_settings() -> Settings:
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text())
    else:
        # Create default config so users can see and edit it
        CONFIG_FILE.write_text(json.dumps(DEFAULTS, indent=2) + "\n")
        data = DEFAULTS
    return Settings(**data)


settings = load_settings()
