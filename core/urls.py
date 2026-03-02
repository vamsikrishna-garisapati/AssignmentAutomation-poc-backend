from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("topics/", views.TopicList.as_view()),
    path("assignments/", views.AssignmentListCreate.as_view()),
    path("assignments/generate/", views.AssignmentGenerate.as_view()),
    path("assignments/<int:pk>/assign/", views.AssignmentAssign.as_view()),
    path("assignments/<int:pk>/", views.AssignmentDetail.as_view()),
    path("student/assignments/", views.StudentAssignmentList.as_view()),
    path("submissions/", views.SubmissionListCreate.as_view()),
    path("submissions/<int:pk>/", views.SubmissionDetail.as_view()),
]
