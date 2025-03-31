# notifications/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.conf import settings # Import settings
from django.urls import reverse
from complaints.models import Complaint
from authorities.models import ComplaintUpdate
from .models import Notification
from twilio.rest import Client # Import Twilio Client
from twilio.base.exceptions import TwilioRestException # Import Twilio exceptions
import logging
import re # Import regex module for more advanced checks if needed

logger = logging.getLogger(__name__)

# Helper function to send SMS
def send_complaint_update_sms(recipient_user, complaint, update_instance):
    """Sends an SMS notification about a complaint update."""
    try:
        # 1. Get recipient's phone number
        recipient_profile = getattr(recipient_user, 'profile', None)
        if not recipient_profile or not recipient_profile.mobile_number:
            logger.warning(f"User {recipient_user.username} has no mobile number for SMS notification (Complaint ID: {complaint.id}).")
            return

        to_phone_number_raw = recipient_profile.mobile_number.strip() # Remove leading/trailing whitespace

        # --- E.164 Formatting Logic ---
        # Remove any non-digit characters except potential leading '+'
        to_phone_number_digits = re.sub(r'[^\d+]', '', to_phone_number_raw)

        if to_phone_number_digits.startswith('+'):
            to_phone_number_e164 = to_phone_number_digits # Already in correct format (hopefully)
        elif len(to_phone_number_digits) == 10 and settings.DEFAULT_COUNTRY_CODE == '91': # Assuming 10 digits is Indian local number
            to_phone_number_e164 = f"+{settings.DEFAULT_COUNTRY_CODE}{to_phone_number_digits}"
        elif len(to_phone_number_digits) == 12 and to_phone_number_digits.startswith('91'): # Handle case where 91 is present but '+' is missing
             to_phone_number_e164 = f"+{to_phone_number_digits}"
        # Add more conditions here for other countries or formats if needed
        else:
            logger.error(f"Cannot reliably format phone number '{to_phone_number_raw}' for user {recipient_user.username} into E.164. Aborting SMS.")
            return # Cannot proceed without a valid format

        logger.info(f"Attempting to send SMS to formatted number: {to_phone_number_e164}")
        # --- End E.164 Formatting Logic ---


        # 2. Get necessary details (as before)
        official = update_instance.official.user
        official_name = official.get_full_name() or official.username
        new_status = update_instance.status
        complaint_type = complaint.get_complaint_type_display()
        complaint_id = complaint.id

        # 3. Construct the absolute URL (as before)
        try:
            complaint_path = complaint.get_absolute_url()
            complaint_url = f"{settings.SITE_DOMAIN}{complaint_path}"
        except Exception:
            logger.error(f"Could not generate absolute URL for complaint {complaint_id}. SMS link will be omitted.", exc_info=True)
            complaint_url = None

        # 4. Construct the SMS message body (Improved)
        greeting = "\n\nGreetings from the Civic Complaints App!\n"
        update_line = f"Your {complaint_type} complaint"
        if complaint.ward_number:
            update_line += f" in ward {complaint.ward_number}" # Add ward number if available
        update_line += f" has been updated."

        status_line = f"==== New Status ====\n{new_status}\n(Updated by {official_name})"

        # Combine the parts
        message_parts = [
            greeting,
            update_line,
            status_line
        ]

        # Add the link if available
        if complaint_url:
            link_line = f"\nView details: {complaint_url}"
            message_parts.append(link_line)
        else:
            fallback_line = "\nVisit the website to view details."
            message_parts.append(fallback_line)

        # Join parts with newline characters
        message_body = "\n".join(message_parts)

        # 5. Initialize Twilio client (as before)
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        # 6. Send the SMS - USE THE FORMATTED NUMBER
        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone_number_e164 # Use the E.164 formatted number
        )
        logger.info(f"SMS sent successfully to {to_phone_number_e164} (SID: {message.sid}) for Complaint ID {complaint_id}")

    except TwilioRestException as e:
        # Use the E.164 number in error logging too
        logger.error(f"Twilio Error sending SMS to {to_phone_number_e164 if 'to_phone_number_e164' in locals() else to_phone_number_raw} for Complaint ID {complaint_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"General Error sending SMS for Complaint ID {complaint_id}: {e}", exc_info=True)

@receiver(post_save, sender=Complaint)
def complaint_created_notification(sender, instance, created, **kwargs):
    """
    Notify the user (on-site notification) when their complaint is created.
    The verb starts with "You..." and the actor is set to None.
    """
    if created:
        try:
            # Verb starts directly with "You..."
            verb_text = f'You submitted a {instance.get_complaint_type_display()} complaint'
            if instance.ward_number:
                verb_text += f' in ward {instance.ward_number}'

            Notification.objects.create(
                recipient=instance.user,
                actor=None, # Set actor to None for self-notifications
                verb=verb_text,
                target=instance
            )
            logger.info(f"On-site notification created for new complaint {instance.id} for user {instance.user.username}")
        
        except Exception as e:
             logger.error(f"Error creating on-site notification for new complaint {instance.id}: {e}", exc_info=True)

@receiver(post_save, sender=ComplaintUpdate)
def complaint_status_updated_notification(sender, instance, created, **kwargs):
    """
    Handles notifications (on-site and SMS) when an official updates a complaint.
    Verb now describes the action, status is retrieved from action_object.
    """
    if created:
        try:
            complaint = instance.complaint
            recipient = complaint.user
            actor = instance.official.user
            actor_name = actor.get_full_name() or actor.username

            # --- 1. Create On-Site Notification (Modified Verb) ---
            # Verb describes the action, not the result status
            verb_text = (
                f'updated your {complaint.get_complaint_type_display()} complaint '
            )
            if complaint.ward_number:
                verb_text += f' in ward {complaint.ward_number}'

            Notification.objects.create(
                recipient=recipient,
                actor=actor,
                verb=verb_text, # Store the modified verb
                target=complaint,
                action_object=instance # Link to ComplaintUpdate holds the new status
            )
            logger.info(f"On-site notification created for complaint update {instance.id} for user {recipient.username}")

            # --- 2. Send SMS Notification ---
            send_complaint_update_sms(recipient_user=recipient, complaint=complaint, update_instance=instance)

        except Exception as e:
            logger.error(f"Error processing complaint update notification (Update ID: {instance.id}): {e}", exc_info=True)