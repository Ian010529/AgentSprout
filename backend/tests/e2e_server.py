"""Provider-boundary test server used only by local browser automation."""

from __future__ import annotations

from app.core.config import get_settings
from app.main import create_app


class BrowserTestEmbeddingProvider:
    model = "text-embedding-3-small"

    def embed(self, texts: list[str]) -> list[list[float]]:
        terms = ("ocean", "climate", "current", "temperature", "coral", "explore")
        return [[float(text.lower().count(term)) + 0.001 for term in terms] for text in texts]


application = create_app(get_settings(), embedding_provider=BrowserTestEmbeddingProvider())
