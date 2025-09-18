from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    # Pages principales
    path('', views.home, name='home'),
    path('list/', views.document_list, name='list'),
    path('upload/', views.document_upload, name='upload'),
    path('<int:pk>/', views.document_detail, name='detail'),

    # API endpoints
    path('api/<int:pk>/status/', views.document_status, name='status'),
    path('api/<int:pk>/reprocess/', views.reprocess_document, name='reprocess'),
    path('api/<int:pk>/delete/', views.delete_document, name='delete'),

    # Téléchargements
    path('<int:pk>/download/', views.download_original, name='download'),
    path('<int:pk>/export-html/', views.export_html, name='export_html'),
    path('api/<int:pk>/save-edits/', views.save_document_edits, name='save_edits'),

]