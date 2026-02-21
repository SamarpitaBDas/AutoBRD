from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'data-sources', views.DataSourceViewSet)
router.register(r'requirements', views.ExtractedRequirementViewSet)
router.register(r'brd-documents', views.BRDDocumentViewSet)
router.register(r'conflicts', views.ConflictDetectionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('health/', views.health_check, name='health-check'),
]
