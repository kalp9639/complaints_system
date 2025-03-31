from django.db import models
from django.contrib.auth.models import User
from complaints.models import Complaint

class GovernmentOfficial(models.Model):
    """
    Represents a government official with ward-specific access
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='official_profile')
    ward_number = models.CharField(max_length=50)
    department = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Ward {self.ward_number}"

class ComplaintUpdate(models.Model):
    """
    Track official updates to complaints with proof images
    """
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved')
    ]

    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='updates')
    official = models.ForeignKey(GovernmentOfficial, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    update_description = models.TextField(blank=True, null=True)
    proof_image = models.ImageField(upload_to='complaint_updates/', blank=False, null=False)
    updated_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Update for Complaint #{self.complaint.id} by {self.official.user.username}"

