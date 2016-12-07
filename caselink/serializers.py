from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.core.exceptions import ObjectDoesNotExist
from .models import *


class LinkageSerializer(serializers.ModelSerializer):
    def validate_autocase_pattern(self, data):
        for case in AutoCase.objects.all():
            if test_pattern_match(data, case.id):
                return data
        raise serializers.ValidationError("Pattern Invalid.")

    class Meta:
        model = Linkage


class WorkItemSerializer(serializers.ModelSerializer):
    caselinks = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    bugs = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    patterns = serializers.SerializerMethodField()

    def get_patterns(self, wi):
        return [link.autocase_pattern for link in wi.caselinks.all()]

    class Meta:
        model = WorkItem


class AutoCaseSerializer(serializers.ModelSerializer):
    caselinks = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    failures = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    class Meta:
        model = AutoCase


class WorkItemLinkageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Linkage
        exclude = ('workitem',)


class BugSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bug


class AutoCaseFailureSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoCaseFailure


class FrameworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Framework


class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component


class ArchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Arch
