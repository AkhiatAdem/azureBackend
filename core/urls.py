from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    
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
]