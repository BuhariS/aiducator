from django.urls import path

from courses.views import (
    add_module,
    artifact_form,
    course_studio,
    create_course,
    create_course_version,
    delete_course,
    generate_course,
    generation_status,
    lesson_form,
    publish_version,
    question_form,
    preview_version,
    version_editor,
)

app_name = "teacher_courses"

urlpatterns = [
    path("new/", create_course, name="create"),
    path("generate/", generate_course, name="generate"),
    path("generate/<uuid:request_id>/status/", generation_status, name="generation-status"),
    path("<slug:slug>/studio/", course_studio, name="studio"),
    path("<slug:slug>/delete/", delete_course, name="delete"),
    path("<slug:slug>/studio/versions/new/", create_course_version, name="create-version"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/", version_editor, name="version-editor"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/preview/", preview_version, name="preview-version"),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/preview/<uuid:lesson_id>/",
        preview_version,
        name="preview-lesson",
    ),
    path("<slug:slug>/studio/versions/<uuid:version_id>/modules/add/", add_module, name="add-module"),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/modules/<uuid:module_id>/lessons/new/",
        lesson_form,
        name="create-lesson",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/modules/<uuid:module_id>/lessons/<uuid:lesson_id>/edit/",
        lesson_form,
        name="edit-lesson",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/artifacts/new/",
        artifact_form,
        name="create-artifact",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/artifacts/<uuid:artifact_id>/edit/",
        artifact_form,
        name="edit-artifact",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/questions/new/",
        question_form,
        name="create-question",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/questions/<uuid:question_id>/edit/",
        question_form,
        name="edit-question",
    ),
    path("<slug:slug>/studio/versions/<uuid:version_id>/publish/", publish_version, name="publish-version"),
]
