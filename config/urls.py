from django.contrib import admin
from django.urls import path
from portal import views as v
from portal import material_views as m
urlpatterns=[
 path('materials/import/',m.memo_import,name='memo_import'),path('materials/candidates/<int:pk>/convert/',m.candidate_convert),
 path('admin/',admin.site.urls), path('admin-mfa/',v.admin_mfa),
 path('login/',v.login,name='login'),path('otp/',v.otp),path('logout/',v.logout),path('policy/',v.policy),path('health/',v.health),
 path('exception/',v.exception_login),path('exception-issue/',v.exception_issue),path('roster/',v.roster),
 path('',v.cases,name='cases'),path('cases/<int:pk>/',v.case_detail,name='case'),path('cases/material/<slug:key>/',v.case_detail,name='fixed_case'),
 path('documents/<int:pk>/<str:kind>/',v.documents),
 path('posts/',v.posts,name='posts'),path('posts/new/',v.post_edit,name='post_new'),
 path('posts/<int:pk>/',v.post_detail,name='post'),path('posts/<int:pk>/edit/',v.post_edit,name='post_edit'),path('posts/<int:pk>/delete/',v.post_delete,name='post_delete'),
 path('requests/',v.requests_view,name='requests'),
]
