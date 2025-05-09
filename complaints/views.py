# complaints/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from .models import Complaint
from .forms import ComplaintForm
from django.utils.dateformat import format
import geopandas as gpd
from shapely.geometry import Point
import os
import zipfile
import tempfile
import fiona
import json
from django.conf import settings 
from django.core.cache import cache 
from django.http import JsonResponse
import logging

# Set up logging
logger = logging.getLogger(__name__)

class WardBoundaryManager:
    """Class to manage ward boundary data and operations"""
    _instance = None  # Singleton instance
    
    def __new__(cls):
        """Implement singleton pattern"""
        if cls._instance is None:
            cls._instance = super(WardBoundaryManager, cls).__new__(cls)
            cls._instance._gdf = None  # Initialize GeoDataFrame to None
            cls._instance.load_boundaries()  # Load boundaries on first instantiation
        return cls._instance
    
    def load_boundaries(self):
        """Load ward boundaries from KMZ file"""
        try:
            kmz_file = settings.WARD_BOUNDARY_KMZ_PATH
            kml_file = self._extract_kml_from_kmz(kmz_file)
            self._gdf = self._load_kml_as_gdf(kml_file)
            logger.info("Ward boundaries loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading ward boundaries: {e}")
            self._gdf = None
    
    def _extract_kml_from_kmz(self, kmz_file):
        """Extract KML file from KMZ archive"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            with zipfile.ZipFile(kmz_file, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid KMZ file: {kmz_file}. It may be corrupted. {e}")
        
        # Find the KML file in the extracted contents
        for file in os.listdir(temp_dir):
            if file.endswith('.kml'):
                return os.path.join(temp_dir, file)
        
        # If no KML file was found
        raise FileNotFoundError(f"No KML file found in the KMZ archive: {kmz_file}")
    
    def _load_kml_as_gdf(self, kml_file):
        """Load KML file into GeoDataFrame"""
        with fiona.Env():
            try:
                gdf = gpd.read_file(kml_file, driver='KML')
                return gdf
            except fiona.errors.DriverError as e:
                raise ValueError(f"Could not read KML file {kml_file}. Ensure it is a valid KML format. {e}")
    
    def find_ward(self, lat, lon):
        """Find the ward containing the given coordinates"""
        if self._gdf is None:
            logger.warning("Ward boundaries not loaded. Returning 'Unknown'.")
            return "Unknown"
        
        # Create point from coordinates
        point = Point(lon, lat)
        
        # Check if point is within any ward boundary
        for _, row in self._gdf.iterrows():
            if row.geometry.contains(point):
                return row["Name"]
        
        return "Unknown"
    
    def reload_boundaries(self):
        """Force reload of boundary data"""
        self._gdf = None
        self.load_boundaries()
        return self._gdf is not None
    
    @property
    def is_loaded(self):
        """Check if boundaries are loaded"""
        return self._gdf is not None

# Initialize the ward boundary manager
ward_manager = WardBoundaryManager()

@login_required
def get_ward_from_coordinates(request):
    """API endpoint to get ward information from coordinates"""
    try:
        lat = float(request.GET.get('lat', 0))
        lng = float(request.GET.get('lng', 0))
        
        ward = ward_manager.find_ward(lat, lng)
        
        return JsonResponse({
            'success': True,
            'ward': ward
        })
    except Exception as e:
        logger.error(f"Error finding ward: {e}")
        return JsonResponse({
            'success': False,
            'ward': 'Unknown',
            'error': str(e)
        })

# Update the find_ward function to use the manager
def find_ward(lat, lon):
    """Finds the ward name for a given latitude and longitude"""
    return ward_manager.find_ward(lat, lon)

@method_decorator(login_required, name='dispatch')
class ComplaintCreateView(CreateView):
    model = Complaint
    form_class = ComplaintForm
    template_name = 'complaints/submit_complaint.html'
    success_url = reverse_lazy('view_complaints')

    def dispatch(self, request, *args, **kwargs):
        if hasattr(request.user, 'official_profile'):
            messages.error(request, "Government officials cannot submit complaints.")
            return redirect('authorities:authority_dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        complaint = form.save(commit=False)
        complaint.user = self.request.user
        # Assign ward based on lat-long
        if complaint.latitude and complaint.longitude:
            complaint.ward_number = find_ward(complaint.latitude, complaint.longitude)
        complaint.save()
        messages.success(self.request, 'Your complaint has been submitted successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class ComplaintListView(ListView):
    model = Complaint
    template_name = 'complaints/view_complaints.html'
    context_object_name = 'complaints'
    paginate_by = 9  # Show 9 complaints per page (3 rows of 3)

    def get_queryset(self):
        queryset = Complaint.objects.filter(user=self.request.user, is_trashed=False, is_permanently_deleted=False)

        # Apply filters if provided
        complaint_type = self.request.GET.get('type')
        status = self.request.GET.get('status')
        ward = self.request.GET.get('ward')

        if complaint_type:
            queryset = queryset.filter(complaint_type=complaint_type)
        if status:
            queryset = queryset.filter(status=status)
        if ward:
            queryset = queryset.filter(ward_number=ward)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all complaint types for the filter dropdown
        complaint_types = Complaint._meta.get_field('complaint_type').choices

        # Get all unique wards for the filter dropdown
        wards = Complaint.objects.filter(user=self.request.user).values_list('ward_number', flat=True)
        wards = sorted(set([ward for ward in wards if ward]))  # Remove None/empty values

        # Pass the selected filter values back to the template
        context['complaint_types'] = complaint_types
        context['wards'] = wards
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_ward'] = self.request.GET.get('ward', '')

        # Check if any filter is applied
        context['filtered'] = any([
            self.request.GET.get('type'),
            self.request.GET.get('status'),
            self.request.GET.get('ward')
        ])

        # Create query params string for pagination links
        query_params = []
        if self.request.GET.get('type'):
            query_params.append(f"type={self.request.GET.get('type')}")
        if self.request.GET.get('status'):
            query_params.append(f"status={self.request.GET.get('status')}")
        if self.request.GET.get('ward'):
            query_params.append(f"ward={self.request.GET.get('ward')}")

        context['query_params'] = '&'.join(query_params)

        return context


@method_decorator(login_required, name='dispatch')
class ComplaintDetailView(DetailView):
    model = Complaint
    template_name = 'complaints/complaint_detail.html'
    context_object_name = 'complaint'

    def dispatch(self, request, *args, **kwargs):
        # Get the complaint object
        complaint = self.get_object()

        # Check if user is official for this ward
        is_official = False
        if hasattr(request.user, 'official_profile'):
            is_official = (request.user.official_profile.ward_number == complaint.ward_number)

        # Allow access if the user is the submitter or a government official in the same ward
        if request.user == complaint.user or is_official:
            return super().dispatch(request, *args, **kwargs)
        else:
            messages.error(request, "You do not have permission to view this complaint.")
            return redirect('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complaint = self.get_object()

        # Check if user is official for this ward
        is_official = False
        if hasattr(self.request.user, 'official_profile'):
            is_official = (self.request.user.official_profile.ward_number == complaint.ward_number)

        # Fetch all updates in descending order (latest first)
        updates = complaint.updates.order_by('-updated_at')

        context['is_official'] = is_official
        context['updates'] = updates
        return context


@method_decorator(login_required, name='dispatch')
class MapView(View):
    template_name = 'complaints/map_view.html'

    def get(self, request, *args, **kwargs):
        # Start with all complaints for this user
        complaints_query = Complaint.objects.filter(
            user=request.user,
            latitude__isnull=False,
            longitude__isnull=False
        )

        # Apply filters if provided
        complaint_type = request.GET.get('type')
        status = request.GET.get('status')
        ward = request.GET.get('ward')

        if complaint_type:
            complaints_query = complaints_query.filter(complaint_type=complaint_type)
        if status:
            complaints_query = complaints_query.filter(status=status)
        if ward:
            complaints_query = complaints_query.filter(ward_number=ward)

        # Get all complaint types for the filter dropdown
        complaint_types = Complaint._meta.get_field('complaint_type').choices

        # Get all unique wards for the filter dropdown
        wards = Complaint.objects.filter(user=request.user).values_list('ward_number', flat=True)
        wards = sorted(set([ward for ward in wards if ward]))  # Remove None/empty values

        # Prepare complaints data for the map
        complaints_data = []
        for complaint in complaints_query:
            complaints_data.append({
                'id': complaint.id,
                'lat': float(complaint.latitude),
                'lng': float(complaint.longitude),
                'type': complaint.get_complaint_type_display(),
                'status': complaint.status,
                'url': f'/complaints/detail/{complaint.id}/',  # URL to complaint details
                'ward': complaint.ward_number or 'Unknown',
                'submitted_by': complaint.user.get_full_name() or complaint.user.username,
                'created_at': complaint.created_at.isoformat(),  # Pass the timestamp as ISO format
                'image_url': complaint.image.url if complaint.image else None,
            })

        # Create query params string for pagination links (if needed later)
        query_params = []
        if request.GET.get('type'):
            query_params.append(f"type={request.GET.get('type')}")
        if request.GET.get('status'):
            query_params.append(f"status={request.GET.get('status')}")
        if request.GET.get('ward'):
            query_params.append(f"ward={request.GET.get('ward')}")

        # Pass the complaints data and filters to the template
        context = {
            'complaints_data': json.dumps(complaints_data),
            'complaint_count': len(complaints_data),
            'total_count': Complaint.objects.filter(user=request.user, latitude__isnull=False, longitude__isnull=False).count(),
            'complaint_types': complaint_types,
            'wards': wards,
            'selected_type': request.GET.get('type', ''),
            'selected_status': request.GET.get('status', ''),
            'selected_ward': request.GET.get('ward', ''),
            'filtered': any([complaint_type, status, ward]),
            'query_params': '&'.join(query_params)
        }

        return render(request, self.template_name, context)

@method_decorator(login_required, name='dispatch')
class ComplaintUpdateView(UpdateView):
    model = Complaint
    form_class = ComplaintForm
    template_name = 'complaints/edit_complaint.html'
    success_url = reverse_lazy('view_complaints')

    def dispatch(self, request, *args, **kwargs):
        complaint = self.get_object()
        # Only allow the owner of the complaint to edit it
        if complaint.user != request.user:
            messages.error(request, "You do not have permission to edit this complaint.")
            return redirect('view_complaints')

        # Don't allow editing of resolved complaints
        if complaint.status == 'Resolved':
            messages.error(request, "You cannot edit a resolved complaint.")
            return redirect('complaint_detail', pk=complaint.id)

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        complaint = form.save(commit=False)
        # Recalculate ward if location changed
        if complaint.latitude and complaint.longitude:
            complaint.ward_number = find_ward(complaint.latitude, complaint.longitude)
        complaint.save()
        messages.success(self.request, 'Your complaint has been updated successfully!')
        return super().form_valid(form)

# Soft deletion
@method_decorator(login_required, name='dispatch')
class ComplaintDeleteView(View):
    def post(self, request, *args, **kwargs):
        complaint = get_object_or_404(Complaint, pk=kwargs['pk'])

        # Ensure the user is the owner of the complaint
        if complaint.user != request.user:
            messages.error(request, "You do not have permission to delete this complaint.")
            return HttpResponseRedirect(reverse('trash_bin'))

        # Store complaint type for success message
        complaint_type = complaint.get_complaint_type_display()

        # Delete the complaint
        complaint.soft_delete()

        messages.success(request, f"Your {complaint_type} complaint has been permanently deleted.")
        return HttpResponseRedirect(reverse('trash_bin'))

# New views for trash functionality

@method_decorator(login_required, name='dispatch')
class ComplaintTrashView(View):
    def post(self, request, *args, **kwargs):
        complaint = get_object_or_404(Complaint, pk=kwargs['pk'])

        # Ensure the user is the owner of the complaint
        if complaint.user != request.user:
            messages.error(request, "You do not have permission to trash this complaint.")
            return HttpResponseRedirect(reverse('view_complaints'))

        # Move to trash
        complaint.is_trashed = True
        complaint.trashed_at = timezone.now()
        complaint.save()

        messages.success(request, f"Your {complaint.get_complaint_type_display()} complaint has been moved to trash.")
        return HttpResponseRedirect(reverse('view_complaints'))


@method_decorator(login_required, name='dispatch')
class ComplaintRestoreView(View):
    def post(self, request, *args, **kwargs):
        complaint = get_object_or_404(Complaint, pk=kwargs['pk'])

        # Ensure the user is the owner of the complaint
        if complaint.user != request.user:
            messages.error(request, "You do not have permission to restore this complaint.")
            return HttpResponseRedirect(reverse('trash_bin'))

        # Restore from trash
        complaint.is_trashed = False
        complaint.trashed_at = None
        complaint.save()

        messages.success(request, f"Your {complaint.get_complaint_type_display()} complaint has been restored.")
        return HttpResponseRedirect(reverse('trash_bin'))


@method_decorator(login_required, name='dispatch')
class TrashBinView(ListView):
    model = Complaint
    template_name = 'complaints/trash_bin.html'
    context_object_name = 'trashed_complaints'
    paginate_by = 9

    def get_queryset(self):
        return Complaint.objects.filter(user=self.request.user, is_trashed=True, is_permanently_deleted=False)

@method_decorator(login_required, name='dispatch')
class EmptyTrashView(View):
    def post(self, request, *args, **kwargs):
        # Get all trashed complaints for this user
        trashed_complaints = Complaint.objects.filter(user=request.user, is_trashed=True)
        count = trashed_complaints.count()

        if count > 0:
            # Delete all trashed complaints
            trashed_complaints.delete()
            messages.success(request, f"Successfully deleted {count} complaints from trash.")
        else:
            messages.info(request, "Trash bin was already empty.")

        return HttpResponseRedirect(reverse('trash_bin'))