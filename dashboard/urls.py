from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/toggle-admin/', views.toggle_admin, name='toggle_admin'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/<int:pk>/delete/', views.delete_review, name='delete_review'),
]
