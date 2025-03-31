# complaints/tasks.py

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from .models import Complaint
import logging

logger = logging.getLogger('complaints')

@shared_task
def delete_old_trashed_complaints():
    # Calculate the cutoff time based on settings
    cutoff_time = timezone.now() - timedelta(days=7)

    # Find complaints that have been in trash longer than the cutoff time
    old_complaints = Complaint.objects.filter(
        is_trashed=True,
        trashed_at__lt=cutoff_time
    )

    # Store count before deletion
    count = old_complaints.count()

    # Log what we're about to do
    logger.info(f"Found {count} complaints to delete from trash")

    # Delete each complaint individually to trigger the model's delete() method
    for complaint in old_complaints:
        try:
            # Log the image path before deletion
            if complaint.image:
                logger.info(f"Deleting image at: {complaint.image.path}")

            # This will call the custom delete() method in the model
            complaint.soft_delete()
            logger.info(f"Successfully deleted complaint ID: {complaint.id}")
        except Exception as e:
            logger.exception(f"Error deleting complaint ID {complaint.id}")

    return f"Deleted {count} complaints from trash that were older than 7 days"