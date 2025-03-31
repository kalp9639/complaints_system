# complaints/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
import os

class Complaint(models.Model):
    COMPLAINT_TYPES = (
        ('garbage', 'Garbage'),
        ('pothole', 'Pothole'),
        ('cattle', 'Cattle'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='complaints')
    complaint_type = models.CharField(max_length=10, choices=COMPLAINT_TYPES)
    image = models.ImageField(upload_to='complaints/')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='Pending', 
                              choices=(
                                  ('Pending', 'Pending'),
                                  ('In Progress', 'In Progress'),
                                  ('Resolved', 'Resolved'),
                              ))

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    ward_number = models.CharField(max_length=50, null=True, blank=True) 

    is_trashed = models.BooleanField(default=False)
    trashed_at = models.DateTimeField(null=True, blank=True)

    is_permanently_deleted = models.BooleanField(default=False)
    permanently_deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_complaint_type_display()} complaint by {self.user.username}"
    
    def soft_delete(self):
        """Mark complaint as permanently deleted instead of actual deletion."""
        self.is_permanently_deleted = True
        self.permanently_deleted_at = timezone.now()
        self.save()

    def get_absolute_url(self):
        # Assuming you have a named URL pattern for complaint detail
        return reverse('complaint_detail', kwargs={'pk': self.pk})

    '''
    def delete(self, *args, **kwargs):
        # Delete the image file from the file system
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)
            
        # Call the parent class's delete method to delete the model instance
        super().delete(*args, **kwargs)
    '''