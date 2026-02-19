"""
URL configuration for houser project.
"""
from django.contrib import admin
from django.urls import path
from api.views import hello, intent, search, stats, chat, clear_cache

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/hello', hello, name='hello'),
    path('api/intent', intent, name='intent'),
    path('api/search', search, name='search'),
    path('api/stats', stats, name='stats'),
    path('api/chat', chat, name='chat'),  # New unified endpoint
    path('api/clear-cache', clear_cache, name='clear_cache'),
]
