import time
from pathlib import Path


def safe_unlink(path: Path | None, retries: int = 6, delay_seconds: float = 0.1) -> bool:
    """Best-effort file delete that tolerates transient Windows file locks."""
    if path is None:
        return True

    for attempt in range(retries):
        try:
            path.unlink(missing_ok=True)
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            if attempt == retries - 1:
                return False
            time.sleep(delay_seconds)
        except OSError:
            if attempt == retries - 1:
                return False
            time.sleep(delay_seconds)

    return False
