from django.utils.timezone import now, localtime
from datetime import timedelta
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from .models import Complaint

class ComplaintThrottleMiddleware:
    """
    Middleware to throttle complaint submissions.
    Limits the number of complaints a user can submit within a specific time window.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Fetch limit & window from Django settings (with defaults)
        self.complaint_limit = getattr(settings, "COMPLAINT_SUBMISSION_LIMIT", 3)
        self.time_window_minutes = getattr(settings, "COMPLAINT_TIME_WINDOW", 5)

    def __call__(self, request):
        # Only apply throttling to authenticated users trying to submit complaints
        if request.user.is_authenticated and request.path == "/complaints/submit/":
            time_threshold = now() - timedelta(minutes=self.time_window_minutes)
            
            # Count how many complaints the user has submitted in the defined time window
            complaint_count = Complaint.objects.filter(user=request.user, created_at__gte=time_threshold).count()
            
            if complaint_count >= self.complaint_limit:
                # Find the earliest complaint in the window to calculate next allowed submission time
                first_complaint = Complaint.objects.filter(user=request.user, created_at__gte=time_threshold).earliest('created_at')
                next_allowed_time = first_complaint.created_at + timedelta(minutes=self.time_window_minutes)
                
                # Format the time in AM/PM format
                formatted_time = localtime(next_allowed_time).strftime("%I:%M %p")

                # Display message with exact return time
                message = f"You have reached the limit of {self.complaint_limit} complaints in {self.time_window_minutes} minutes. Come back later at {formatted_time} to submit more."
                messages.error(request, message)
                return redirect('view_complaints')

        response = self.get_response(request)
        return response
