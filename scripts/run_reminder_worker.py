import logging
import time

from app.database.connection import SessionLocal, init_db
from app.worker.reminder_worker import process_due_events


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    while True:
        with SessionLocal() as db:
            result = process_due_events(db)
        if result["processed"]:
            logging.info("reminder worker result=%s", result)
        time.sleep(5)


if __name__ == "__main__":
    main()
