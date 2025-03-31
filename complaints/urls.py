# complaints/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('submit/', views.ComplaintCreateView.as_view(), name='submit_complaint'),
    path('list/', views.ComplaintListView.as_view(), name='view_complaints'),
    path('detail/<int:pk>/', views.ComplaintDetailView.as_view(), name='complaint_detail'),
    path('complaint/edit/<int:pk>/', views.ComplaintUpdateView.as_view(), name='edit_complaint'),
    path('map/', views.MapView.as_view(), name='map_view'),
    path('complaints/delete/<int:pk>/', views.ComplaintDeleteView.as_view(), name='delete_complaint'),
    path('complaints/trash/<int:pk>/', views.ComplaintTrashView.as_view(), name='trash_complaint'),
    path('complaints/restore/<int:pk>/', views.ComplaintRestoreView.as_view(), name='restore_complaint'),
    path('complaints/trash-bin/', views.TrashBinView.as_view(), name='trash_bin'),
    path('complaints/empty-trash/', views.EmptyTrashView.as_view(), name='empty_trash'),
]

