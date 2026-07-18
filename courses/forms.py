from urllib.parse import urlparse

from django import forms
from django.utils.text import slugify

from ai_engine.security import allowed_embed_url, clean_input, reject_prompt_injection

from .models import Course, FinalProject, LessonArtifact, LessonVersion, Module


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
        if Course.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A course with this title already exists. Choose a different title.")
        return title

    def save(self, commit=True):
        course = super().save(commit=False)
        if course.status == Course.Status.DRAFT:
            course.slug = slugify(course.title)
        if commit:
            course.save()
        return course


class CourseGenerationForm(forms.Form):
    title = forms.CharField(
        max_length=180,
        label="Course title",
        widget=forms.TextInput(attrs={"placeholder": "Secondary-school Python programming"}),
    )
    objective = forms.CharField(
        required=False,
        max_length=2_000,
        label="Learning objective",
        help_text="State what learners should know and apply. A free prompt can provide this instead.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Learners will know and apply Python fundamentals..."}),
    )
    duration_weeks = forms.IntegerField(min_value=1, max_value=52, initial=12, label="Duration in weeks")
    audience = forms.CharField(
        max_length=180,
        required=False,
        initial="Nigerian secondary-school students",
        widget=forms.TextInput(attrs={"placeholder": "Nigerian secondary-school students"}),
    )
    translation_languages = forms.CharField(
        required=False,
        label="Translation languages",
        help_text="Optional comma-separated language codes, for example yo-NG, ha-NG, ig-NG.",
        widget=forms.TextInput(attrs={"placeholder": "yo-NG, ha-NG, ig-NG"}),
    )
    free_prompt = forms.CharField(
        required=False,
        max_length=4_000,
        label="Additional teacher prompt",
        help_text="Use this for creative direction, local examples, pacing, or a fully free-form request.",
        widget=forms.Textarea(attrs={"rows": 7, "placeholder": "Create practical lessons using Nigerian classroom examples..."}),
    )

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        slug = slugify(title)
        if not slug:
            raise forms.ValidationError("Use letters or numbers so the course can have a web address.")
        if Course.objects.filter(slug=slug).exists():
            raise forms.ValidationError("A course with this title already exists. Choose a different title.")
        return title

    def clean_translation_languages(self):
        value = self.cleaned_data.get("translation_languages", "")
        languages = [item.strip() for item in value.split(",") if item.strip()]
        if len(languages) > 12:
            raise forms.ValidationError("Request no more than 12 translation languages.")
        return languages

    def clean_objective(self):
        objective = clean_input(self.cleaned_data.get("objective", ""), field_name="Learning objective", max_length=2_000)
        return reject_prompt_injection(objective, field_name="Learning objective")

    def clean_free_prompt(self):
        prompt = clean_input(self.cleaned_data.get("free_prompt", ""), field_name="Additional teacher prompt", max_length=4_000)
        return reject_prompt_injection(prompt, field_name="Additional teacher prompt")

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("objective", "").strip() and not cleaned_data.get("free_prompt", "").strip():
            raise forms.ValidationError("Add a learning objective or an additional teacher prompt.")
        return cleaned_data


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ("title", "position")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Module title"}),
            "position": forms.NumberInput(attrs={"min": 1}),
        }


class ArtifactForm(forms.ModelForm):
    class Meta:
        model = LessonArtifact
        fields = ("artifact_type", "content", "asset", "position", "is_active", "teacher_approved")
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Add text, a URL, or embed reference..."}
            ),
            "asset": forms.ClearableFileInput(attrs={"accept": "image/*,video/*"}),
            "position": forms.NumberInput(attrs={"min": 0}),
        }

    def clean(self):
        cleaned_data = super().clean()
        artifact_type = cleaned_data.get("artifact_type")
        content = cleaned_data.get("content", "").strip()
        asset = cleaned_data.get("asset")
        if artifact_type == LessonArtifact.ArtifactType.IMAGE and not content and not asset:
            raise forms.ValidationError("Add an image URL or upload an image file.")
        if artifact_type == LessonArtifact.ArtifactType.VIDEO and not content and not asset:
            self.add_error("content", "Add a video URL or upload a video file.")
        if artifact_type == LessonArtifact.ArtifactType.SIMULATION and not content:
            self.add_error("content", "Add a simulation URL.")
        if artifact_type in {
            LessonArtifact.ArtifactType.TEXT,
            LessonArtifact.ArtifactType.CODE,
            LessonArtifact.ArtifactType.IMAGE_PROMPT,
            LessonArtifact.ArtifactType.YOUTUBE_SEARCH,
        } and not content:
            self.add_error("content", "Add text content.")
        if content and artifact_type in {
            LessonArtifact.ArtifactType.IMAGE,
            LessonArtifact.ArtifactType.VIDEO,
            LessonArtifact.ArtifactType.SIMULATION,
        } and urlparse(content).scheme not in {"http", "https"}:
            self.add_error("content", "Resource links must use http:// or https://.")
        if content and artifact_type in {
            LessonArtifact.ArtifactType.IMAGE,
            LessonArtifact.ArtifactType.VIDEO,
            LessonArtifact.ArtifactType.SIMULATION,
        }:
            try:
                cleaned_data["content"] = allowed_embed_url(content, field_name="Learning resource URL")
            except Exception as exc:
                self.add_error("content", str(exc))
        if content:
            cleaned_data["content"] = clean_input(content, field_name="Learning material", max_length=12_000)
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].required = False


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
            "content": forms.Textarea(attrs={"rows": 14, "maxlength": 20000, "placeholder": "Write the lesson explanation..."}),
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


class FinalProjectForm(forms.ModelForm):
    objectives_text = forms.CharField(
        label="Project objectives",
        help_text="Enter one objective per line.",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    requirements_text = forms.CharField(
        label="Requirements",
        help_text="Enter one requirement per line.",
        widget=forms.Textarea(attrs={"rows": 5}),
    )
    deliverables_text = forms.CharField(
        label="Deliverables",
        help_text="Enter one deliverable per line.",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    rubric_text = forms.CharField(
        label="Assessment rubric",
        help_text="Enter one criterion per line. Criteria receive equal weight.",
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    class Meta:
        model = FinalProject
        fields = ("title", "brief", "estimated_hours")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Community Python project"}),
            "brief": forms.Textarea(attrs={"rows": 8, "placeholder": "Describe the final project challenge..."}),
            "estimated_hours": forms.NumberInput(attrs={"min": 1, "max": 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["objectives_text"].initial = "\n".join(self.instance.objectives)
            self.fields["requirements_text"].initial = "\n".join(self.instance.requirements)
            self.fields["deliverables_text"].initial = "\n".join(self.instance.deliverables)
            self.fields["rubric_text"].initial = "\n".join(
                criterion.get("criterion", "") for criterion in self.instance.rubric
            )

    @staticmethod
    def _lines(value):
        return [line.strip() for line in value.splitlines() if line.strip()]

    def clean_objectives_text(self):
        objectives = self._lines(self.cleaned_data["objectives_text"])
        if not objectives:
            raise forms.ValidationError("Add at least one project objective.")
        return objectives

    def clean_requirements_text(self):
        requirements = self._lines(self.cleaned_data["requirements_text"])
        if not requirements:
            raise forms.ValidationError("Add at least one project requirement.")
        return requirements

    def clean_deliverables_text(self):
        deliverables = self._lines(self.cleaned_data["deliverables_text"])
        if not deliverables:
            raise forms.ValidationError("Add at least one project deliverable.")
        return deliverables

    def clean_rubric_text(self):
        rubric = self._lines(self.cleaned_data["rubric_text"])
        if not rubric:
            raise forms.ValidationError("Add at least one project rubric criterion.")
        return rubric

    def save(self, commit=True):
        project = super().save(commit=False)
        project.objectives = self.cleaned_data["objectives_text"]
        project.requirements = self.cleaned_data["requirements_text"]
        project.deliverables = self.cleaned_data["deliverables_text"]
        criteria = self.cleaned_data["rubric_text"]
        project.rubric = [
            {"criterion": criterion, "weight": round(100 / len(criteria), 2)}
            for criterion in criteria
        ]
        project.teacher_approved = False
        if commit:
            project.save()
        return project
