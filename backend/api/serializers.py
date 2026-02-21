from rest_framework import serializers
from .models import (
    Project, DataSource, ExtractedRequirement, 
    BRDDocument, ConflictDetection, EditHistory
)

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'

class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = '__all__'

class ExtractedRequirementSerializer(serializers.ModelSerializer):
    data_source_type = serializers.CharField(source='data_source.source_type', read_only=True)
    
    class Meta:
        model = ExtractedRequirement
        fields = '__all__'

class BRDDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BRDDocument
        fields = '__all__'

class ConflictDetectionSerializer(serializers.ModelSerializer):
    requirement1_title = serializers.CharField(source='requirement1.title', read_only=True)
    requirement2_title = serializers.CharField(source='requirement2.title', read_only=True)
    
    class Meta:
        model = ConflictDetection
        fields = '__all__'

class EditHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EditHistory
        fields = '__all__'

class BRDGenerationRequestSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    include_conflicts = serializers.BooleanField(default=True)
    include_traceability = serializers.BooleanField(default=True)
    include_sentiment = serializers.BooleanField(default=True)

class EditRequestSerializer(serializers.Serializer):
    brd_id = serializers.IntegerField()
    section = serializers.CharField()
    edit_instruction = serializers.CharField()
