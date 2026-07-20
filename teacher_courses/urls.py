from django.urls import path

from courses.views import (
    add_module,
    artifact_form,
    archive_course,
    course_studio,
    course_settings,
    create_course,
    create_course_version,
    delete_artifact,
    delete_artifacts,
    delete_course,
    delete_lesson,
    delete_module,
    delete_question,
    delete_questions,
    final_project_form,
    generate_course,
    generation_status,
    lesson_form,
    publish_version,
    question_form,
    preview_version,
    teacher_course_studio,
    version_editor,
)

app_name = "teacher_courses"

urlpatterns = [
    path("studio/", teacher_course_studio, name="dashboard"),
    path("new/", create_course, name="create"),
    path("generate/", generate_course, name="generate"),
    path("generate/<uuid:request_id>/status/", generation_status, name="generation-status"),
    path("<slug:slug>/studio/", course_studio, name="studio"),
    path("<slug:slug>/settings/", course_settings, name="settings"),
    path("<slug:slug>/archive/", archive_course, name="archive"),
    path("<slug:slug>/delete/", delete_course, name="delete"),
    path("<slug:slug>/studio/versions/new/", create_course_version, name="create-version"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/", version_editor, name="version-editor"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/preview/", preview_version, name="preview-version"),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/final-project/",
        final_project_form,
        name="final-project",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/preview/<uuid:lesson_id>/",
        preview_version,
        name="preview-lesson",
    ),
    path("<slug:slug>/studio/versions/<uuid:version_id>/modules/add/", add_module, name="add-module"),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/modules/<uuid:module_id>/delete/",
        delete_module,
        name="delete-module",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/modules/<uuid:module_id>/edit/",
        add_module,
        name="edit-module",
    ),
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
        "<slug:slug>/studio/versions/<uuid:version_id>/modules/<uuid:module_id>/lessons/<uuid:lesson_id>/delete/",
        delete_lesson,
        name="delete-lesson",
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
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/artifacts/<uuid:artifact_id>/delete/",
        delete_artifact,
        name="delete-artifact",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/artifacts/delete/",
        delete_artifacts,
        name="delete-artifacts",
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
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/questions/<uuid:question_id>/delete/",
        delete_question,
        name="delete-question",
    ),
    path(
        "<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/questions/delete/",
        delete_questions,
        name="delete-questions",
    ),
    path("<slug:slug>/studio/versions/<uuid:version_id>/publish/", publish_version, name="publish-version"),
]
