from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from portal import views as v
from portal.business_number import evidence as business_number_evidence
from portal import discussions as d
from portal import material_views as m
from portal import preparation as p
from portal import appeals as a
urlpatterns=[
 path('devotion/hymn-310/', TemplateView.as_view(template_name='portal/devotion_hymn.html'), name='devotion_hymn'),
 path('devotion/acts-17-30-31/', TemplateView.as_view(template_name='portal/devotion_acts.html'), name='devotion_acts'),
 path('business-number-evidence/<str:filename>/', business_number_evidence, name='business_number_evidence'),
 path('prepare',p.prepare_redirect),path('prepare/',p.index,name='prepare'),
 path('prepare/events/',p.events,name='prepare_events'),
 path('prepare/claims/<slug:key>/',a.detail,name='prepare_appeal_detail'),
 path('prepare/claims/<slug:key>/comments/',a.comment,name='prepare_appeal_comment'),
 path('prepare/documents/<slug:code>/',a.document,name='prepare_document'),
 path('prepare/logout/',p.logout,name='prepare_logout'),
 path('prepare/events/<slug:key>/',p.detail,name='prepare_detail'),
 path('prepare/events/<slug:key>/comments/',p.comment,name='prepare_comment'),
 path('materials/import/',m.memo_import,name='memo_import'),path('materials/candidates/<int:pk>/convert/',m.candidate_convert),
 path('admin/',admin.site.urls), path('admin-mfa/',v.admin_mfa),
 path('apply/',v.apply,name='apply'),path('login/',v.login,name='login'),path('otp/',v.otp),path('logout/',v.logout),path('policy/',v.policy,name='policy'),path('health/',v.health,name='health'),
 path('exception/',v.exception_login),path('exception-issue/',v.exception_issue),path('roster/',v.roster),
 path('',v.cases,name='cases'),path('cases/archive/',v.legacy_cases,name='legacy_cases'),path('cases/<int:pk>/',v.case_detail,name='case'),path('cases/material/<slug:key>/',v.case_detail,name='fixed_case'),
 path('documents/<int:pk>/<str:kind>/',v.documents,name='document'),
 path('posts/',v.posts,name='posts'),path('posts/new/',v.post_edit,name='post_new'),
 path('posts/<int:pk>/',v.post_detail,name='post'),path('posts/<int:pk>/edit/',v.post_edit,name='post_edit'),path('posts/<int:pk>/delete/',v.post_delete,name='post_delete'),
 path('comment-link/<int:pk>/',v.comment_link),
 path('comments/<slug:key>/',d.comment_write,name='comment_create'),
 path('comments/<slug:key>/<int:pk>/',d.comment_write,name='comment_change'),
 path('requests/',v.requests_view,name='requests'),
]

