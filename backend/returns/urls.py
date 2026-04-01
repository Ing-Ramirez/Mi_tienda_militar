from django.urls import path
from . import views

urlpatterns = [
    # Cliente
    path('',                                   views.ReturnListCreateView.as_view(),  name='return-list-create'),
    path('<uuid:pk>/',                          views.ReturnDetailView.as_view(),      name='return-detail'),
    path('<uuid:pk>/evidence/',                 views.ReturnEvidenceView.as_view(),    name='return-evidence-upload'),
    path('<uuid:pk>/evidence/<uuid:eid>/',      views.ReturnEvidenceView.as_view(),    name='return-evidence-delete'),
    path('<uuid:pk>/transition/',               views.ReturnTransitionView.as_view(),  name='return-transition'),
    path('eligibility/<uuid:order_id>/',        views.ReturnEligibilityView.as_view(), name='return-eligibility'),
    path('policy/',                              views.ReturnPolicyView.as_view(),      name='return-policy'),
    # Admin
    path('admin/list/',                         views.AdminReturnListView.as_view(),   name='admin-return-list'),
]
