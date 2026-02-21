from django.contrib import admin
from .models import (
    Project, DataSource, ExtractedRequirement,
    BRDDocument, ConflictDetection, EditHistory
)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name', 'description']

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['project', 'source_type', 'source_identifier', 'is_relevant', 'relevance_score', 'created_at']
    list_filter = ['source_type', 'is_relevant']
    search_fields = ['source_identifier', 'raw_content']

@admin.register(ExtractedRequirement)
class ExtractedRequirementAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'requirement_type', 'priority', 'confidence_score', 'created_at']
    list_filter = ['requirement_type', 'priority']
    search_fields = ['title', 'description']

@admin.register(BRDDocument)
class BRDDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'status', 'version', 'created_at', 'updated_at']
    list_filter = ['status']
    search_fields = ['title']

@admin.register(ConflictDetection)
class ConflictDetectionAdmin(admin.ModelAdmin):
    list_display = ['project', 'conflict_type', 'severity', 'resolved', 'created_at']
    list_filter = ['conflict_type', 'severity', 'resolved']

@admin.register(EditHistory)
class EditHistoryAdmin(admin.ModelAdmin):
    list_display = ['brd_document', 'section', 'timestamp']
    list_filter = ['section']
    search_fields = ['edit_request']
