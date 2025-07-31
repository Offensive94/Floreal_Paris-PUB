import uuid
import hashlib
import hmac

from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from taggit.managers import TaggableManager
from django.core.validators import MinValueValidator, MaxValueValidator


class User(AbstractUser):
    ROLE_CHOICES = (
        ('buyer', 'Покупатель'),
        ('seller', 'Продавец'),
        ('admin', 'Администратор'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='buyer')
    email_verified = models.BooleanField(default=False)

    avatar = ProcessedImageField(
        upload_to='avatars/',
        processors=[ResizeToFill(200, 200)],
        format='WEBP',
        options={'quality': 90},
        blank=True,
        null=True
    )
    phone = models.CharField(max_length=20, blank=True)
    seller_requested = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        related_name="floreal_user_set",
        related_query_name="floreal_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        related_name="floreal_user_set",
        related_query_name="floreal_user",
    )

    def __str__(self):
        return self.username


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.street}, {self.city}"


class Product(models.Model):
    STATUS_CHOICES = (
        ('in_stock', 'В наличии'),
        ('on_order', 'Под заказ'),
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products'
    )
    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_stock',
        verbose_name="Статус"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    is_active = models.BooleanField(default=True, verbose_name="Активный")
    views = models.PositiveIntegerField(default=0, verbose_name="Просмотры")

    image = models.ImageField(
        upload_to='products/',
        verbose_name="Изображение",
    )
    tags = TaggableManager()

    @property
    def was_edited(self):
        return (self.updated_at - self.created_at) > timedelta(minutes=3)

    def __str__(self):
        return self.title


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carts')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def total_price(self):
        return sum(item.product.price * item.quantity for item in self.items.all())

    def __str__(self):
        return f"Корзина пользователя {self.user.username} (Активна: {self.is_active})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)


    def __str__(self):
        return f"{self.product.title} x {self.quantity}"


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Ожидает обработки'),
        ('processing', 'В обработке'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.SET_NULL,
                             null=True)

    cart = models.ForeignKey(
        Cart,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )

    transaction_id = models.UUIDField(default=uuid.uuid4,
                                      editable=False,
                                      unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20,
                              choices=STATUS_CHOICES,
                              default='pending')
    digital_signature = models.CharField(max_length=64, blank=True)

    def generate_signature(self):
        message = f"{self.transaction_id}{self.total_amount}".encode()
        secret = settings.SECRET_KEY.encode()
        self.digital_signature = hmac.new(secret,
                                         message,
                                         hashlib.sha256).hexdigest()
        self.save()

    def __str__(self):
        return f"Заказ #{self.id} - {self.get_status_display()}"


class ChatRoom(models.Model):
    product = models.ForeignKey(Product,
                                on_delete=models.CASCADE,
                                related_name='chat_rooms')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL,
                              on_delete=models.CASCADE,
                              related_name='buyer_chats')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE,
                               related_name='seller_chats')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Message(models.Model):
    chat_room = models.ForeignKey(ChatRoom,
                                  on_delete=models.CASCADE,
                                  related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    attachment = models.FileField(upload_to='chat_attachments/',
                                  blank=True,
                                  null=True)


class Report(models.Model):
    REPORT_TYPE_CHOICES = (
        ('spam', 'Спам'),
        ('fake', 'Мошенничество'),
        ('inappropriate', 'Неуместный контент'),
        ('other', 'Другое'),
    )
    STATUS_CHOICES = (
        ('pending', 'На рассмотрении'),
        ('resolved', 'Решено'),
        ('rejected', 'Отклонено'),
    )
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL,
                                 on_delete=models.CASCADE,
                                 related_name='reports_made')
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.CASCADE,
                                      related_name='reports_received',
                                      null=True,
                                      blank=True)
    reported_product = models.ForeignKey(Product,
                                         on_delete=models.CASCADE,
                                         null=True,
                                         blank=True)
    report_type = models.CharField(max_length=20,
                                   choices=REPORT_TYPE_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20,
                              choices=STATUS_CHOICES,
                              default='pending')
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL,
                                    null=True,
                                    blank=True,
                                    related_name='resolved_reports')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Жалоба #{self.id} - {self.get_report_type_display()}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Номер телефона")
    address = models.TextField(blank=True, verbose_name="Адрес доставки")
    favorite_flowers = models.CharField(max_length=255, blank=True, verbose_name="Любимые цветы")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")

    def __str__(self):
        return f"Профиль {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

class Review(models.Model):
    product   = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating    = models.PositiveSmallIntegerField(
                    validators=[MinValueValidator(1), MaxValueValidator(5)],
                    verbose_name="Оценка (1–5)"
                )
    comment   = models.TextField(verbose_name="Комментарий", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')  # один отзыв от пользователя на товар

    def __str__(self):
        return f"Отзыв {self.rating}★ by {self.user.username} для {self.product.title}"