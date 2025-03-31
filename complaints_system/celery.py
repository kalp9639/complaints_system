# complaints_system/celery.py

import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings  # Import Django settings

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'complaints_system.settings')

# Create the Celery app
app = Celery('complaints_system')

# Load configuration from Django settings
app.config_from_object('django.conf.settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Define the schedule for the task
app.conf.beat_schedule = {
    'delete-old-trashed-complaints': {
        'task': 'complaints.tasks.delete_old_trashed_complaints',
        'schedule': crontab(hour=3, minute=0),  # Run at 3 AM every day
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')