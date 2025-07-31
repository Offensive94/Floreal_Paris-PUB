from django.urls import path
from . import views

urlpatterns = [
    # Главная и условия
    path('', views.home, name='home'),
    path('terms/', views.terms_view, name='terms'),
    path('search/', views.search_view, name='search'),


    # Товары
    path('products/', views.product_list, name='product_list'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/mine/', views.my_products, name='my_products'),
    path('products/<int:product_id>/edit/',   views.edit_product,   name='edit_product'),
    path('products/<int:product_id>/delete/', views.delete_product, name='delete_product'),

    path('products/<int:product_id>/review/', views.add_review, name='add_review'),


    # Корзина
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/update-item/', views.update_cart_item, name='update_cart_item'),
    path("cart/remove/", views.remove_cart_item, name="remove_cart_item"),


    # Оформление заказа и чек
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/<int:order_id>/pay/', views.payment_view, name='payment'),
    path('checkout/<int:order_id>/result/', views.payment_result, name='payment_result'),

    # Чек на скачивание
    path('order/<uuid:transaction_id>/receipt/', views.generate_receipt, name='generate_receipt'),

    # Аутентификация и профиль
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('users/<str:username>/', views.public_profile, name='public_profile'),


    # Чат (возвращено)
    path('chats/', views.chat_list, name='chat_list'),
    # История сообщений (AJAX)
    path('chats/<int:room_id>/messages/', views.chat_messages, name='chat_messages'),
    # Отправка нового сообщения (AJAX)
    path('chats/<int:room_id>/send/', views.send_message, name='send_message'),
    # Окно чата
    path('chats/<int:room_id>/', views.chat_room, name='chat_room'),

    path('chats/start/<int:product_id>/', views.start_chat, name='start_chat'),


    # Админские удаления
    path('products/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    path('reviews/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('users/<str:username>/delete/', views.delete_user, name='delete_user'),
]
