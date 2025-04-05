# authorities/views.py

# Django Shortcuts
from django.shortcuts import render, redirect, get_object_or_404

# Authentication & Authorization
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm

# Django Views
from django.views import View
from django.views.generic import FormView, TemplateView, ListView, DetailView, UpdateView

# Django Utilities & Security
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.utils import timezone

# Forms & Models
from .forms import OfficialSignUpForm, ComplaintUpdateForm, OfficialProfileUpdateForm
from complaints.models import Complaint
from .models import GovernmentOfficial, ComplaintUpdate

# Standard Library
import json

@method_decorator(csrf_protect, name='dispatch')
class OfficialSignUpView(FormView):
    template_name = 'authorities/official_signup.html'
    form_class = OfficialSignUpForm
    success_url = '/authorities/dashboard/'
    
    def dispatch(self, request, *args, **kwargs):
        # Check if the QR code has been verified
        if not request.session.get('authority_qr_verified', False):
            messages.error(request, 'Unauthorized Access: Please scan the authorized QR code first.')
            return redirect('authorities:qr_verification')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        try:
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(self.request, user)
            
            # Clear the verification flag from the session after successful signup
            if 'authority_qr_verified' in self.request.session:
                del self.request.session['authority_qr_verified']
                
            messages.success(self.request, f'Official account created for {username}!')
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f'Error creating account: {str(e)}')
            return self.form_invalid(form)

class OfficialLoginView(View):
    template_name = 'authorities/official_login.html'
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
    
    def post(self, request, *args, **kwargs):
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            try:
                official = user.official_profile
                login(request, user)
                messages.success(request, f'Welcome, {user.get_full_name()}!')
                return redirect('authorities:authority_dashboard')
            except GovernmentOfficial.DoesNotExist:
                messages.error(request, 'You are not registered as a government official.')
        else:
            messages.error(request, 'Invalid username or password.')
        
        return render(request, self.template_name)


class OfficialLogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('authorities:official_login')


@method_decorator(login_required, name='dispatch')
class AuthorityDashboardView(TemplateView):
    template_name = 'authorities/authority_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('authorities:official_login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complaints = Complaint.objects.filter(ward_number=self.official.ward_number)
        
        context.update({
            'official': self.official,
            'total_complaints': complaints.count(),
            'pending_complaints': complaints.filter(status='Pending').count(),
            'in_progress_complaints': complaints.filter(status='In Progress').count(),
            'resolved_complaints': complaints.filter(status='Resolved').count(),
        })
        return context


@method_decorator(login_required, name='dispatch')
class AuthorityComplaintsListView(ListView):
    template_name = 'authorities/authority_complaints_list.html'
    context_object_name = 'complaints'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('home')
    
    def get_queryset(self):
        queryset = Complaint.objects.filter(ward_number=self.official.ward_number)
        
        # Get filter parameters
        complaint_type = self.request.GET.get('type')
        status = self.request.GET.get('status')
        sort = self.request.GET.get('sort', 'newest')
        
        # Apply filters if present
        if complaint_type:
            queryset = queryset.filter(complaint_type=complaint_type)
        if status:
            queryset = queryset.filter(status=status)
        
        # Apply sorting
        if sort == 'oldest':
            queryset = queryset.order_by('created_at')
        else:  # default to newest
            queryset = queryset.order_by('-created_at')
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add complaint types
        context['complaint_types'] = Complaint.COMPLAINT_TYPES
        
        # Get selected filters for template
        context['selected_type'] = self.request.GET.get('type')
        context['selected_status'] = self.request.GET.get('status') 
        context['selected_sort'] = self.request.GET.get('sort', 'newest')
        
        return context


@method_decorator(login_required, name='dispatch')
class AuthorityComplaintsMapView(View):
    template_name = 'authorities/authority_complaints_map.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('home')
    
    def get(self, request, *args, **kwargs):
        complaints = Complaint.objects.filter(ward_number=self.official.ward_number)
        
        # Get filter parameters
        complaint_type = request.GET.get('type')
        status = request.GET.get('status')
        sort = request.GET.get('sort', 'newest')
        
        # Apply filters if present
        if complaint_type:
            complaints = complaints.filter(complaint_type=complaint_type)
        if status:
            complaints = complaints.filter(status=status)
        
        # Apply sorting
        if sort == 'oldest':
            complaints = complaints.order_by('created_at')
        else:  # default to newest
            complaints = complaints.order_by('-created_at')
        
        # Prepare complaints data for map
        complaints_data = []
        for complaint in complaints:
            complaints_data.append({
                'id': complaint.id,
                'lat': float(complaint.latitude),
                'lng': float(complaint.longitude),
                'type': complaint.get_complaint_type_display(),
                'status': complaint.status,
                'url': f'/complaints/detail/{complaint.id}/',
                'ward': complaint.ward_number or 'Unknown',
                'submitted_by': complaint.user.get_full_name() or complaint.user.username,
                'date': complaint.created_at.strftime('%Y-%m-%d %H:%M'),
                'image_url': complaint.image.url if complaint.image else None,
            })
        
        context = {
            'complaints_data': json.dumps(complaints_data),
            'complaint_count': len(complaints_data),
            'selected_type': complaint_type,
            'selected_status': status,
            'selected_sort': sort,
            'complaint_types': Complaint.COMPLAINT_TYPES,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class UpdateComplaintStatusView(View):
    template_name = 'authorities/update_complaint_status.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            self.complaint = get_object_or_404(
                Complaint, 
                id=kwargs.get('complaint_id'), 
                ward_number=self.official.ward_number
            )
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('home')
    
    def get(self, request, *args, **kwargs):
        form = ComplaintUpdateForm(initial={'status': self.complaint.status})
        return render(request, self.template_name, {
            'form': form, 
            'complaint': self.complaint
        })
    
    def post(self, request, *args, **kwargs):
        form = ComplaintUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            update = form.save(commit=False)
            update.complaint = self.complaint
            update.official = self.official
            update.save()
            
            self.complaint.status = form.cleaned_data['status']
            self.complaint.save()
            
            messages.success(request, 'Complaint status updated successfully!')
            return redirect('authorities:authority_complaints_list')
        
        return render(request, self.template_name, {
            'form': form, 
            'complaint': self.complaint
        })


@method_decorator(login_required, name='dispatch')
class OfficialComplaintsView(ListView):
    template_name = 'authority_complaints_list.html'
    context_object_name = 'complaints'
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'official_profile'):
            messages.error(request, "You do not have permission to access this page.")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Complaint.objects.filter(ward_number=self.request.user.official_profile.ward_number)


@method_decorator(login_required, name='dispatch')
class BaseTemplateUpdateView(TemplateView):
    template_name = 'accounts/base.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_official'] = hasattr(self.request.user, 'official_profile')
        return context


@method_decorator(login_required, name='dispatch')
class ComplaintDetailView(DetailView):
    model = Complaint
    template_name = 'complaints/complaint_detail.html'
    context_object_name = 'complaint'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            self.complaint = self.get_object()
            
            # Check if this official is authorized to view this complaint
            if self.complaint.ward_number != self.official.ward_number:
                messages.error(request, 'You do not have permission to view this complaint.')
                return redirect('home')
                
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add is_official flag and ordered updates
        context.update({
            'is_official': True,
            'updates': self.complaint.updates.order_by('-updated_at')
        })
        
        return context

@method_decorator(login_required, name='dispatch')
class OfficialProfileUpdateView(View):
    template_name = 'authorities/official_profile_edit.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('authorities:official_login')
    
    def get(self, request, *args, **kwargs):
        form = OfficialProfileUpdateForm(instance=self.official, user=request.user)
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = OfficialProfileUpdateForm(request.POST, instance=self.official, user=request.user)
        if form.is_valid():
            # Update User model fields
            user = request.user
            user.username = form.cleaned_data['username']
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.save()
            
            # Save GovernmentOfficial model fields
            official = form.save(commit=False)
            official.user = user
            official.save()
            
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('authorities:authority_dashboard')
        
        return render(request, self.template_name, {'form': form})


@method_decorator(login_required, name='dispatch')
class ChangePasswordView(View):
    template_name = 'authorities/change_password.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('authorities:official_login')
    
    def get(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user)
        # Add Bootstrap classes to form fields
        for field in form.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        return render(request, self.template_name, {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session to prevent logging out
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('authorities:authority_dashboard')
        
        return render(request, self.template_name, {'form': form})

@method_decorator(login_required, name='dispatch')
class OfficialDeleteProfileView(View):
    template_name = 'authorities/delete_profile.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.official = request.user.official_profile
            return super().dispatch(request, *args, **kwargs)
        except GovernmentOfficial.DoesNotExist:
            messages.error(request, 'Access denied. You are not registered as a government official.')
            return redirect('home')
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
    
    def post(self, request, *args, **kwargs):
        try:
            # Soft delete official profile
            official = self.official
            official.is_deleted = True
            official.deleted_at = timezone.now()
            official.save()
            
            # Soft delete user
            user = request.user
            user.is_active = False
            user.save()
            
            # Logout the user
            logout(request)
            
            messages.success(request, 'Your profile has been deactivated successfully.')
            return redirect('home')
        
        except Exception as e:
            messages.error(request, f'Error deleting profile: {str(e)}')
            return redirect('authorities:authority_dashboard')

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from pyzbar.pyzbar import decode
from PIL import Image
import os

class AuthorityQRVerificationView(View):
    template_name = 'authorities/qr_verification.html'
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
    
    def post(self, request, *args, **kwargs):
        if 'qr_image' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No image file provided'})
        
        try:
            # Get the uploaded image
            image_file = request.FILES['qr_image']
            
            # Open the image with PIL
            image = Image.open(image_file)
            
            # Decode the QR code
            decoded_objects = decode(image)
            
            if not decoded_objects:
                return JsonResponse({'success': False, 'message': 'No QR code found in the image'})
            
            # Get the QR code data
            qr_data = decoded_objects[0].data.decode('utf-8')
            
            # Print for debugging
            print(f"QR Code Content: {qr_data}")
            print(f"Expected Secret: {settings.AUTHORITY_QR_SECRET_KEY}")
            
            # Compare with the secret key
            if qr_data == settings.AUTHORITY_QR_SECRET_KEY:
                # Set session flag
                request.session['authority_qr_verified'] = True
                return JsonResponse({'success': True, 'redirect': '/authorities/signup/'})
            else:
                return JsonResponse({'success': False, 'message': 'Invalid QR code. Unauthorized access.'})
                
        except Exception as e:
            print(f"Error processing QR code: {str(e)}")
            return JsonResponse({'success': False, 'message': f'Error processing QR code: {str(e)}'})
