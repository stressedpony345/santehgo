from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('request-success/', views.request_success, name='request_success'),
    path('masters/login/', views.master_login, name='master_login'),
    path('masters/logout/', views.master_logout, name='master_logout'),
    path('masters/', views.master_dashboard, name='master_dashboard'),
    path('masters/manifest.webmanifest', views.master_manifest, name='master_manifest'),
    path('masters/sw.js', views.master_service_worker, name='master_service_worker'),
    path('masters/api/requests/', views.master_requests_api, name='master_requests_api'),
    path('masters/api/requests/<int:request_id>/claim/', views.master_claim_request, name='master_claim_request'),
    path('masters/api/requests/<int:request_id>/complete/', views.master_complete_request, name='master_complete_request'),
    path('masters/api/push/public-key/', views.master_push_public_key, name='master_push_public_key'),
    path('masters/api/push/subscribe/', views.master_push_subscribe, name='master_push_subscribe'),
    path('masters/profile/password/', views.master_change_password, name='master_change_password'),
    path('api/categories/', views.categories_api, name='categories_api'),
    path('api/address-suggestions/', views.address_suggestions, name='address_suggestions'),
    path('api/requests/', views.create_request, name='create_request'),
]
