# complaints/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Complaint

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'complaint_type', 'ward_number', 'created_at', 'status', 'view_image')
    list_filter = ('complaint_type', 'status', 'created_at', 'ward_number')
    search_fields = ('user__username', 'description', 'ward_number')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'latitude', 'longitude', 'ward_number', 'image_preview')
    list_editable = ('status',)
    
    def view_image(self, obj):
        if obj.image:
            return format_html('<a href="{0}" target="_blank">View Image</a>', obj.image.url)
        return "No image"
    
    view_image.short_description = 'Image'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{0}" style="max-height: 300px; max-width: 100%;" />', obj.image.url)
        return "No image uploaded"
    
    image_preview.short_description = 'Image Preview'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'complaint_type', 'status', 'created_at')
        }),
        ('Complaint Details', {
            'fields': ('description', 'image', 'image_preview')
        }),
        ('Location Information', {
            'fields': ('latitude', 'longitude', 'ward_number'),
            'classes': ('collapse',),
        }),
    )