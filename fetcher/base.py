import time
from typing import Any, Dict, List

from logs.logger import log


class BaseFetcher:
    """Base class for all hackathon source fetchers with bounded retries and error isolation."""

    name: str = "Base"
    max_retries: int = 2
    timeout_seconds: int = 30

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch hackathons from source. Subclasses must implement."""
        raise NotImplementedError

    def fetch_safe(self) -> List[Dict[str, Any]]:
        """Execute fetch with bounded retries and graceful failure handling."""
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.fetch()
            except Exception as e:
                last_exc = e
                log(f"[{self.name}] Attempt {attempt}/{self.max_retries} encountered error: {e}")
                if attempt < self.max_retries:
                    time.sleep(1.0 * attempt)
        raise RuntimeError(f"{self.name} fetcher failed after {self.max_retries} attempts: {last_exc}")
