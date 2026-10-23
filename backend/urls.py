from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Keep the short URLs used by settings, bookmarks, and the old UI working.
    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=False), name='login'),
    path('signup/', RedirectView.as_view(url='/accounts/signup/', permanent=False), name='signup'),
    path('logout/', RedirectView.as_view(url='/accounts/logout/', permanent=False), name='logout'),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('accounts.urls')),
    path('trainer/', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('', RedirectView.as_view(url='/trainer/', permanent=False)),
]
