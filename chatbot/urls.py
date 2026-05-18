from django.urls import path
from . import views

urlpatterns = [
    path('message/', views.chatbot_message, name='chatbot_message'),
]
