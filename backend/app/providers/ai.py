from typing import Protocol


class AIProvider(Protocol):
    """Replaceable AI interface for later mention verification and classification."""

    def classify_mention(self, advertiser: str, text: str, context: str) -> dict: ...
