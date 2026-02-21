from django.db import models
from django.contrib.auth.models import User
import json


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name


class DataSource(models.Model):
    SOURCE_TYPES = [
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('meeting', 'Meeting Transcript'),
        ('document', 'Document Upload'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_identifier = models.CharField(max_length=500)
    raw_content = models.TextField()
    processed_content = models.TextField(blank=True)

    metadata = models.TextField(default='{}')

    created_at = models.DateTimeField(auto_now_add=True)
    is_relevant = models.BooleanField(default=True)
    relevance_score = models.FloatField(default=0.0)

    def get_metadata(self):
        try:
            return json.loads(self.metadata)
        except json.JSONDecodeError:
            return {}

    def set_metadata(self, data):
        self.metadata = json.dumps(data)

    def __str__(self):
        return f"{self.source_type} - {self.source_identifier}"


class ExtractedRequirement(models.Model):
    REQUIREMENT_TYPES = [
        ('functional', 'Functional'),
        ('non_functional', 'Non-Functional'),
        ('business', 'Business'),
        ('technical', 'Technical'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='requirements')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='requirements')
    requirement_type = models.CharField(max_length=20, choices=REQUIREMENT_TYPES)
    title = models.CharField(max_length=500)
    description = models.TextField()
    priority = models.CharField(max_length=20, default='medium')
    stakeholder = models.CharField(max_length=255, blank=True)
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class BRDDocument(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='brd_documents')
    title = models.CharField(max_length=500)

    executive_summary = models.TextField(blank=True)
    business_objectives = models.TextField(blank=True)
    stakeholder_analysis = models.TextField(blank=True)
    functional_requirements = models.TextField(blank=True)
    non_functional_requirements = models.TextField(blank=True)
    assumptions = models.TextField(blank=True)
    success_metrics = models.TextField(blank=True)
    timeline = models.TextField(blank=True)
    conflict_analysis = models.TextField(blank=True)

    traceability_matrix = models.TextField(default='{}')
    sentiment_analysis = models.TextField(default='{}')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file_path = models.CharField(max_length=500, blank=True)

    def get_traceability_matrix(self):
        try:
            return json.loads(self.traceability_matrix)
        except json.JSONDecodeError:
            return {}

    def set_traceability_matrix(self, data):
        self.traceability_matrix = json.dumps(data)

    def get_sentiment_analysis(self):
        try:
            return json.loads(self.sentiment_analysis)
        except json.JSONDecodeError:
            return {}

    def set_sentiment_analysis(self, data):
        self.sentiment_analysis = json.dumps(data)

    def __str__(self):
        return f"{self.title} - v{self.version}"


class ConflictDetection(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='conflicts')
    requirement1 = models.ForeignKey(ExtractedRequirement, on_delete=models.CASCADE, related_name='conflict1')
    requirement2 = models.ForeignKey(ExtractedRequirement, on_delete=models.CASCADE, related_name='conflict2')
    conflict_type = models.CharField(max_length=100)
    description = models.TextField()
    severity = models.CharField(max_length=20)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conflict: {self.conflict_type}"


class EditHistory(models.Model):
    brd_document = models.ForeignKey(BRDDocument, on_delete=models.CASCADE, related_name='edit_history')
    section = models.CharField(max_length=100)
    edit_request = models.TextField()
    previous_content = models.TextField()
    new_content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Edit to {self.section} at {self.timestamp}"
