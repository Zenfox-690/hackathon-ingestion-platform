import time
import schedule

from main import run_pipeline


schedule.every(6).hours.do(run_pipeline)

print("Scheduler running...")

while True:
    schedule.run_pending()
    time.sleep(1)