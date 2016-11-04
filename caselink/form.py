from django import forms
from django.conf import settings

from .models import WorkItem

def assignee_list():
    assignees = settings.CASELINK_MEMBERS.split()
    for assignee in assignees:
        yield (assignee, assignee)

class MaitaiAutomationRequest(forms.Form):

    """Form for MaitaiAutomationRequest. """

    manual_cases = forms.CharField(label='Manual cases(Workitems)', max_length=1023, required=True)
    assignee = forms.ChoiceField(label='Assignee on JIRA', required=True,
                                 choices=assignee_list, initial=settings.CASELINK_DEFAULT_ASSIGNEE)
    labels = forms.CharField(label='Labels on JIRA, split by comma',
                             max_length=1023, required=False)

    def clean(self):
        cleaned_data = super(MaitaiAutomationRequest, self).clean()
        labels = cleaned_data.get("labels")

        if " " in labels:
            msg = "Space not allowed in labels."
            self.add_error('labels', msg)
