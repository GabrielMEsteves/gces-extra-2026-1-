from __future__ import annotations

import logging
import time

from uda_pipeline.bootstrap import build_pipeline
from uda_pipeline.config import get_settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    _, pipeline = build_pipeline()
    logger.info("Worker iniciado com intervalo de %s segundos", settings.poll_interval_seconds)
    while True:
        summary = pipeline.run_once()
        logger.info("Ciclo concluido: %s", summary.model_dump())
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
