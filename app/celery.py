from celery import Celery
from celery.schedules import crontab

from app.main import settings

celery_app = Celery("tasks", broker=settings.celery_broker)

MONITORING_TASK = "app.tasks.monitor"

celery_app.conf.task_routes = {MONITORING_TASK: "main-queue"}

# Schedule the monitoring task
celery_app.conf.beat_schedule = {
    "monitor": {
        "task": MONITORING_TASK,
        "schedule": crontab(
            minute=f"*/{settings.frequency}"  # Run the task every X minutes
        ),
    }
}
