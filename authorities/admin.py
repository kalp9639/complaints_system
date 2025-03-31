from django.contrib import admin
from .models import GovernmentOfficial, ComplaintUpdate

@admin.register(GovernmentOfficial)
class GovernmentOfficialAdmin(admin.ModelAdmin):
    list_display = ('user', 'ward_number', 'department')
    list_filter = ('ward_number', 'department')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'ward_number')

@admin.register(ComplaintUpdate)
class ComplaintUpdateAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'official', 'status', 'updated_at')
    list_filter = ('status', 'updated_at')
    search_fields = ('complaint__id', 'official__user__username')