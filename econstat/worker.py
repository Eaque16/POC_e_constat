"""Worker SQL mono-job du POC E-Constat IA."""

import argparse
import asyncio
import logging
import time

from econstat.config import get_settings
from econstat.database import SessionLocal
from econstat.services.jobs import claim_next_job, recover_stale_jobs
from econstat.services.pipeline import process_processing_job

LOGGER = logging.getLogger("econstat.worker")


async def run_once() -> bool:
    settings = get_settings()
    with SessionLocal() as db:
        recovered = recover_stale_jobs(db, settings.job_stale_minutes)
        if recovered:
            LOGGER.warning("%s job(s) bloqué(s) remis en file", recovered)
        job = claim_next_job(db)
        if job is None:
            return False
        LOGGER.info("Traitement du job %s, étape %s", job.id, job.current_step)
        try:
            await process_processing_job(db, job, settings)
        except Exception:
            LOGGER.exception("Le job %s a échoué", job.id)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker SQL E-Constat IA")
    parser.add_argument("--once", action="store_true", help="Traite au plus un job puis s’arrête")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    while True:
        processed = asyncio.run(run_once())
        if arguments.once:
            return
        if not processed:
            time.sleep(settings.job_poll_seconds)


if __name__ == "__main__":
    main()
