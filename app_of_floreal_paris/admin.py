from django.contrib import admin
from taggit.models import Tag  # для фильтрации по тегам
from .models import User, Product, Address, Order, ChatRoom, Message, Report


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'email_verified')
    list_filter = ('role',)
    search_fields = ('username', 'email')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'price', 'status', 'created_at')
    list_filter = (
        'status',
        ('tags', admin.RelatedOnlyFieldListFilter),  # Теперь корректно фильтрует по тегам
    )
    search_fields = ('title', 'description')
    readonly_fields = ('views',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'user', 'status', 'total_amount', 'created_at')
    list_filter = ('status',)
    search_fields = ('transaction_id', 'user__username')


# Регистрируем остальные модели без особой кастомизации:
admin.site.register(Address)
admin.site.register(ChatRoom)
admin.site.register(Message)
admin.site.register(Report)
