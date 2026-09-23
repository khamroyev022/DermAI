from django.urls import path,include

urlpatterns = [
    path('auth/api/',include('account.urls')),
    path('clinic/api/',include('clinical.urls')),
    path('patient/api/',include('patients.urls')),
]
