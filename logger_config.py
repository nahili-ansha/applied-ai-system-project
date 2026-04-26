import logging
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("pawpal")
    if logger.handlers:
        return  # Already configured — Streamlit reruns call this repeatedly

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.FileHandler(log_dir / "pawpal.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
