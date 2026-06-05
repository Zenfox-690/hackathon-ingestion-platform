import time
import schedule

from config import SCHEDULE_HOURS
from main import run_pipeline
from startup_checks import validate_environment


validate_environment()

schedule.every(SCHEDULE_HOURS).hours.do(run_pipeline)

print("Scheduler running...")

while True:
    schedule.run_pending()
    time.sleep(1)