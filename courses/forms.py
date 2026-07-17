from django import forms
from django.utils.text import slugify

from .models import Course, LessonVersion, Module


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ("title", "description", "duration_weeks", "passing_score", "max_retries")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Introduction to Python"}),
            "description": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Describe what students will learn..."}
            ),
            "duration_weeks": forms.NumberInput(attrs={"min": 1, "max": 52}),
            "passing_score": forms.NumberInput(attrs={"min": 1, "max": 100}),
            "max_retries": forms.NumberInput(attrs={"min": 0, "max": 10}),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        slug = slugify(title)
        if not slug:
            raise forms.ValidationError("Use letters or numbers so the course can have a web address.")
        if Course.objects.filter(slug=slug).exists():
            raise forms.ValidationError("A course with this title already exists. Choose a different title.")
        return title


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ("title", "position")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Module title"}),
            "position": forms.NumberInput(attrs={"min": 1}),
        }


class LessonForm(forms.ModelForm):
    objectives_text = forms.CharField(
        label="Learning objectives",
        help_text="Enter one objective per line.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Explain variables\nUse variables in a program"}),
    )

    class Meta:
        model = LessonVersion
        fields = ("title", "position", "content")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Lesson title"}),
            "position": forms.NumberInput(attrs={"min": 1}),
            "content": forms.Textarea(attrs={"rows": 14, "placeholder": "Write the lesson explanation..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.objectives:
            self.fields["objectives_text"].initial = "\n".join(self.instance.objectives)

    def clean_objectives_text(self):
        objectives = [line.strip() for line in self.cleaned_data["objectives_text"].splitlines() if line.strip()]
        if not objectives:
            raise forms.ValidationError("Add at least one learning objective.")
        return objectives

    def save(self, commit=True):
        lesson = super().save(commit=False)
        lesson.objectives = self.cleaned_data["objectives_text"]
        if commit:
            lesson.save()
        return lesson
