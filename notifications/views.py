# notifications/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.views import View
from django.http import Http404, JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages 
from .models import Notification
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from complaints.models import Complaint 
import logging

logger = logging.getLogger(__name__)

class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    """Marks all unread notifications for the current user as read."""
    
    def post(self, request, *args, **kwargs):
        try:
            updated_count = Notification.objects.filter(recipient=request.user, unread=True).update(unread=False)
            logger.info(f"Marked {updated_count} notifications as read for user {request.user.username}")
            
            # Check if this is an AJAX request (from notification slider)
            is_ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            if is_ajax_request:
                # Return JSON response for AJAX requests
                return JsonResponse({
                    'success': True,
                    'message': f'Marked {updated_count} notifications as read',
                    'updated_count': updated_count
                })
        except Exception as e:
            logger.error(f"Error marking all notifications read for user {request.user.username}: {e}", exc_info=True)
            messages.error(request, "Could not mark all notifications as read.")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Could not mark all notifications as read'
                }, status=500)

        # For non-AJAX requests, redirect as before
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('home')))


class NotificationRedirectView(LoginRequiredMixin, View):
    """
    Marks a specific notification as read.
    Redirects to its target URL if the target (Complaint) is accessible.
    Shows a message and redirects home if the target is trashed or deleted.
    Handles GET requests (when user clicks the notification link).
    """
    
    def get(self, request, notification_id, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
        target = notification.target # Get the generic target object

        # --- Mark as read immediately upon clicking ---
        if notification.unread:
            notification.mark_as_read()
            logger.info(f"Marked notification {notification_id} as read for user {request.user.username}")
        # --- End mark as read ---

        redirect_url = None # Initialize redirect_url

        # --- Check if the target is a Complaint and its status ---
        if isinstance(target, Complaint):
            complaint = target # We already have the complaint object
            complaint_id_for_msg = complaint.id # Store ID for messages before potential redirect

            if complaint.is_permanently_deleted:
                messages.warning(
                    request,
                    f"Unable to fetch the complaint. It has been permanently deleted."
                )
                return redirect(reverse('all_notifications_list')) # Redirect to home or 'all_notifications_list'

            elif complaint.is_trashed:
                messages.info(
                    request,
                    f"Unable to fetch the complaint. It is currently in the trash bin."
                )
                # Optional: Redirect to trash bin instead?
                # return redirect(reverse('trash_bin'))
                return redirect(reverse('trash_bin')) # Redirect 'all_notifications_list'

            else:
                # Complaint exists and is accessible, try to get its URL
                try:
                    redirect_url = complaint.get_absolute_url()
                except AttributeError:
                    logger.warning(f"Complaint target (ID: {complaint.pk}) has no get_absolute_url method.")
                except Exception as e:
                    logger.error(f"Error getting redirect URL for Complaint notification {notification_id}: {e}", exc_info=True)

        # --- If target is not a Complaint or target is None ---
        elif target:
            # Handle other potential target types if needed in the future
            # For now, try to get a URL if it's not None
            try:
                redirect_url = target.get_absolute_url()
            except AttributeError:
                logger.warning(f"Notification target {target} (Type: {type(target).__name__}, ID: {target.pk}) has no get_absolute_url method.")
            except Exception as e:
                logger.error(f"Error getting redirect URL for non-Complaint notification {notification_id}: {e}", exc_info=True)

        # --- Perform the redirect if URL was found, otherwise fallback ---
        if redirect_url:
            return redirect(redirect_url)
        else:
            # Fallback if target doesn't exist, has no URL, or an error occurred getting the URL
            if target: # Only show error if a target existed but URL failed
                messages.error(request, "Could not determine where to redirect for this notification.")
            # If target was None initially, no error message is needed, just redirect safely.
            return redirect(reverse('home')) # Redirect home as a safe fallback


class AllNotificationsListView(LoginRequiredMixin, View):
    template_name = 'notifications/all_notifications.html'
    
    def get(self, request, *args, **kwargs):
        # Get all notifications for the user, ordered by timestamp
        notification_list = Notification.objects.filter(recipient=request.user).select_related('actor')

        # Set up Paginator
        paginator = Paginator(notification_list, 15) # Show 15 notifications per page
        page_number = request.GET.get('page') # Get page number from request query parameters

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            page_obj = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            page_obj = paginator.page(paginator.num_pages)

        # Get the unread count separately for the header button logic
        unread_count = Notification.objects.filter(recipient=request.user, unread=True).count()

        context = {
            # 'notifications': page_obj, # Pass the page object
            'page_obj': page_obj,      # Use 'page_obj' which is standard Django convention
            'is_paginated': True,      # Let the template know pagination is active
            'unread_notification_count': unread_count # Still needed for the header button
        }
        return render(request, self.template_name, context)