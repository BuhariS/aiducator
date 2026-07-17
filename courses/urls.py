from django.urls import path
from django.views.generic import RedirectView

from .views import (
    catalog,
    course_detail,
    enroll,
    learn,
    mark_lesson_complete_view,
)

app_name = "courses"

urlpatterns = [
    path("", catalog, name="catalog"),
    path("<slug:slug>/", course_detail, name="detail"),
    path("<slug:slug>/enroll/", enroll, name="enroll"),
    path("<slug:slug>/learn/", learn, name="learn"),
    path("<slug:slug>/learn/<uuid:lesson_id>/", learn, name="learn-lesson"),
    path("<slug:slug>/learn/<uuid:lesson_id>/complete/", mark_lesson_complete_view, name="complete-lesson"),
    path("dashboard/student/", RedirectView.as_view(pattern_name="dashboard:student-dashboard"), name="student-dashboard"),
    path("dashboard/teacher/", RedirectView.as_view(pattern_name="dashboard:teacher-dashboard"), name="teacher-dashboard"),
    path("<slug:slug>/studio/", RedirectView.as_view(pattern_name="teacher_courses:studio"), name="studio"),
    path("<slug:slug>/studio/versions/new/", RedirectView.as_view(pattern_name="teacher_courses:create-version"), name="create-version"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/", RedirectView.as_view(pattern_name="teacher_courses:version-editor"), name="version-editor"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/modules/add/", RedirectView.as_view(pattern_name="teacher_courses:add-module"), name="add-module"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/modules/<uuid:module_id>/lessons/new/", RedirectView.as_view(pattern_name="teacher_courses:create-lesson"), name="create-lesson"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/modules/<uuid:module_id>/lessons/<uuid:lesson_id>/edit/", RedirectView.as_view(pattern_name="teacher_courses:edit-lesson"), name="edit-lesson"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/questions/new/", RedirectView.as_view(pattern_name="teacher_courses:create-question"), name="create-question"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/lessons/<uuid:lesson_id>/questions/<uuid:question_id>/edit/", RedirectView.as_view(pattern_name="teacher_courses:edit-question"), name="edit-question"),
    path("<slug:slug>/studio/versions/<uuid:version_id>/publish/", RedirectView.as_view(pattern_name="teacher_courses:publish-version"), name="publish-version"),
]
