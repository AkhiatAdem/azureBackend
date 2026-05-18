from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    path('request-password-reset/', views.request_password_reset, name='request_password_reset'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('upgrade-membership/', views.upgrade_membership, name='upgrade_membership'),
    
    # Genres
    path('genres/', views.genre_list, name='genre_list'),
    path('genres/<int:pk>/', views.genre_detail, name='genre_detail'),
    
    # Movies
    path('movies/', views.movie_list, name='movie_list'),
    path('movies/<int:pk>/', views.movie_detail, name='movie_detail'),
    
    # Rooms
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/<int:pk>/', views.room_detail, name='room_detail'),
    
    # Screenings
    path('screenings/', views.screening_list, name='screening_list'),

    # Tickets
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/<uuid:ticket_uuid>/verify/', views.verify_ticket, name='verify_ticket'),

    # User Management (Admin)
    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/promote/', views.promote_user, name='promote_user'),
    path('users/<int:pk>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),

    # Stats (Manager/Admin)
    path('stats/', views.cinema_stats, name='cinema_stats'),
]