from django import forms

from .models import AccommodationRequest, Appeal, Attempt, Question


class AttemptForm(forms.ModelForm):
    def __init__(self, *args, allow_copy_paste=False, **kwargs):
        super().__init__(*args, **kwargs)
        if allow_copy_paste:
            for attribute in ("onpaste", "oncopy", "oncut", "ondrop", "oncontextmenu", "data-protected-input"):
                self.fields["answer_text"].widget.attrs.pop(attribute, None)
            self.fields["answer_text"].widget.attrs["aria-describedby"] = "accessibility-accommodation"

    class Meta:
        model = Attempt
        fields = ("answer_text",)
        widgets = {
            "answer_text": forms.Textarea(
                attrs={
                    "rows": 12,
                    "class": "w-full rounded-2xl border border-slate-200 bg-white p-4 text-ink shadow-sm outline-none transition focus:border-emerald focus:ring-4 focus:ring-emerald/10",
                    "placeholder": "Type your answer here...",
                    "autocomplete": "off",
                    "spellcheck": "false",
                    "onpaste": "return false;",
                    "oncopy": "return false;",
                    "oncut": "return false;",
                    "ondrop": "return false;",
                    "oncontextmenu": "return false;",
                    "data-protected-input": "true",
                }
            )
        }

    def clean_answer_text(self):
        answer = self.cleaned_data["answer_text"].strip()
        if len(answer) < 10:
            raise forms.ValidationError("Please provide a complete answer of at least 10 characters.")
        return answer


class GradeDecisionForm(forms.Form):
    final_score = forms.IntegerField(min_value=0, max_value=100)
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ("question_type", "prompt", "max_score", "position", "is_active", "is_objective")
        widgets = {
            "prompt": forms.Textarea(attrs={"rows": 5, "placeholder": "Write the assessment prompt..."}),
            "max_score": forms.NumberInput(attrs={"min": 1, "max": 100}),
            "position": forms.NumberInput(attrs={"min": 1}),
        }


class RubricForm(forms.Form):
    criteria_text = forms.CharField(
        label="Rubric criteria",
        help_text="Enter one criterion per line. Criteria receive equal weight.",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Uses accurate Python terminology\nExplains the concept clearly"}),
    )
    total_score = forms.IntegerField(min_value=1, max_value=100, initial=100)

    def clean_criteria_text(self):
        criteria = [line.strip() for line in self.cleaned_data["criteria_text"].splitlines() if line.strip()]
        if not criteria:
            raise forms.ValidationError("Add at least one rubric criterion.")
        return criteria


class AccommodationRequestForm(forms.ModelForm):
    class Meta:
        model = AccommodationRequest
        fields = ("course", "accommodation_type", "details")
        widgets = {"details": forms.Textarea(attrs={"rows": 6, "placeholder": "Tell your teacher what support would help..."})}

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = (
            self.fields["course"].queryset.filter(
                enrollments__student=student,
                enrollments__status="active",
            ).distinct()
            if student
            else self.fields["course"].queryset.none()
        )


class AppealForm(forms.ModelForm):
    class Meta:
        model = Appeal
        fields = ("reason",)
        widgets = {
            "reason": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Explain why you believe the confirmed grade should be reviewed...",
                }
            )
        }

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 10:
            raise forms.ValidationError("Please explain your appeal in at least 10 characters.")
        return reason
