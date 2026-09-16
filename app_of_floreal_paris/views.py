import json
import random
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.html import escape

from .models import (
    Product, Cart, CartItem, Order,
    ChatRoom, Message, UserProfile, Review
)
from .forms import (
    RegisterForm, LoginForm, ProfileForm, ProductForm, ReviewForm, FakePaymentForm
)

User = get_user_model()

# --- Аутентификация и профиль ---

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Регистрация прошла успешно! Добро пожаловать, {user.username}!')
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                label = form.fields[field].label if field in form.fields else field
                for error in errors:
                    messages.error(request, f"{label}: {error}")
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('home')
        else:
            messages.error(request, 'Неверные учетные данные.')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Вы успешно вышли.')
    return redirect('home')


@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    my_products = Product.objects.filter(seller=request.user).order_by('-created_at')
    my_orders = Order.objects.filter(user=request.user).order_by('-created_at')

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлен.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'profile/detail.html', {
        'form': form,
        'profile': profile,
        'my_products': my_products,
        'my_orders': my_orders,
    })


def public_profile(request, username):
    user_obj = get_object_or_404(User, username=username)
    products = user_obj.products.filter(is_active=True).order_by('-created_at')
    return render(request, 'profile/public_profile.html', {
        'profile_user': user_obj,
        'products': products,
    })


@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            rev = form.save(commit=False)
            rev.product = product
            rev.user = request.user
            try:
                with transaction.atomic():
                    rev.save()
                messages.success(request, "Спасибо за ваш отзыв!")
            except IntegrityError:
                messages.error(request, "Вы уже оставили отзыв на этот товар.")
            return redirect('product_detail', product_id=product.id)
    else:
        form = ReviewForm()

    return render(request, 'products/reviews/add_review.html', {
        'form': form,
        'product': product
    })


# --- Главная и условия ---

def home(request):
    popular_products = Product.objects.filter(is_active=True).only(
        'id', 'title', 'price', 'views', 'image', 'seller_id'
    ).order_by('-views')[:4]
    new_products = Product.objects.filter(is_active=True).only(
        'id', 'title', 'price', 'views', 'image', 'created_at', 'seller_id'
    ).order_by('-created_at')[:4]
    return render(request, 'base/home.html', {
        'popular_products': popular_products,
        'new_products': new_products
    })


def terms_view(request):
    return render(request, 'base/urista.html')


# --- Товары ---

def product_list(request):
    products = Product.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'products/product_list.html', {'products': products})


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    product.views += 1
    product.save(update_fields=['views'])
    return render(request, 'products/product_detail.html', {'product': product})


@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            form.save_m2m()
            messages.success(request, 'Товар успешно добавлен!')
            return redirect('product_list')
        else:
            messages.error(request, 'Ошибки в форме. Исправьте.')
    else:
        form = ProductForm()
    return render(request, 'products/product_form.html', {'form': form})


@login_required
def my_products(request):
    products = Product.objects.filter(seller=request.user)
    return render(request, 'products/product_list.html', {'products': products, 'mine': True})


@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if product.seller != request.user and request.user.role != 'admin' and not request.user.is_superuser:
        return HttpResponseForbidden("Вы не можете редактировать этот товар")
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Товар обновлён")
            return redirect('product_detail', product_id=product.id)
    else:
        form = ProductForm(instance=product)
    return render(request, 'products/product_form.html', {'form': form})


@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not (product.seller == request.user or request.user.role == 'admin' or request.user.is_superuser):
        return HttpResponseForbidden("Вы не можете удалить этот товар")
    if request.method == 'POST':
        product.delete()
        messages.success(request, "Товар удалён")
        return redirect('my_products')
    return render(request, 'product_confirm_delete.html', {'product': product})


def search_view(request):
    query = request.GET.get('q', '').strip()
    product_results = []
    user_results = []

    if query:
        products = Product.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            is_active=True
        ).only('id', 'title', 'description', 'price', 'image', 'views').order_by('-views')

        for p in products:
            product_results.append({
                'id': p.id,
                'title': p.title,
                'description': p.description,
                'price': p.price,
                'image': p.image.url if p.image else '',
                'views': p.views,
            })

        users = User.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        ).only('id', 'username', 'email', 'date_joined').order_by('-date_joined')

        for u in users:
            user_results.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'joined': u.date_joined,
            })

    return render(request, 'search.html', {
        'query': query,
        'product_results': product_results,
        'user_results': user_results,
    })


# --- Корзина и заказы ---

def get_active_cart(user):
    cart = Cart.objects.filter(user=user, is_active=True).first()
    if not cart:
        cart = Cart.objects.create(user=user)
    return cart


@login_required
def view_cart(request):
    cart = get_active_cart(request.user)
    raw_items = list(cart.items.select_related('product'))
    items = []
    removed_count = 0

    for item in raw_items:
        try:
            if item.product and item.product.is_active:
                items.append(item)
            else:
                item.delete()
                removed_count += 1
        except Product.DoesNotExist:
            item.delete()
            removed_count += 1

    if removed_count > 0:
        messages.warning(
            request,
            f"Некоторые товары ({removed_count} шт.) более недоступны и были удалены из вашей корзины."
        )

    return render(request, 'cart/view_cart.html', {
        'cart': cart,
        'items': items,
    })


@login_required
@require_POST
def add_to_cart(request):
    if request.user.role == 'admin':
        return JsonResponse({'success': False, 'error': 'Администраторы не могут пользоваться корзиной.'}, status=403)
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных.'}, status=400)

    cart = get_active_cart(request.user)
    product = get_object_or_404(Product, id=product_id, is_active=True)

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if created:
        item.quantity = max(1, quantity)
    else:
        item.quantity = max(1, item.quantity + quantity)
    item.save()

    return JsonResponse({
        'success': True,
        'cart_count': cart.total_items(),
        'cart_total': f"{cart.total_price():.2f}"
    })


@login_required
@require_POST
def update_cart_item(request):
    try:
        data = json.loads(request.body)
        pid = data.get('product_id')
        action = data.get('action')
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных.'}, status=400)

    cart = get_active_cart(request.user)
    item = get_object_or_404(CartItem, cart=cart, product_id=pid)

    if action == 'increment':
        item.quantity += 1
        item.save()
    elif action == 'decrement':
        if item.quantity > 1:
            item.quantity -= 1
            item.save()
        else:
            item.delete()

    count = cart.total_items()
    total = cart.total_price()

    try:
        qty = CartItem.objects.get(cart=cart, product_id=pid).quantity
    except CartItem.DoesNotExist:
        qty = 0

    return JsonResponse({
        'success': True,
        'cart_count': count,
        'cart_total': f"{total:.2f}",
        'item_quantity': qty,
        'product_id': pid,
    })


@login_required
@require_POST
def remove_from_cart(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Некорректный формат данных.'}, status=400)

    cart = get_active_cart(request.user)
    CartItem.objects.filter(cart=cart, product_id=product_id).delete()

    return JsonResponse({
        'success': True,
        'cart_count': cart.total_items(),
        'cart_total': f"{cart.total_price():.2f}"
    })


@login_required
@require_POST
def clear_cart(request):
    cart = get_active_cart(request.user)
    cart.items.all().delete()

    return JsonResponse({
        'success': True,
        'cart_count': 0,
        'cart_total': "0.00"
    })


@login_required
def checkout(request):
    cart = get_active_cart(request.user)
    if cart.total_items() == 0:
        messages.error(request, "Корзина пуста.")
        return redirect('product_list')

    order = Order.objects.create(
        user=request.user,
        cart=cart,
        total_amount=cart.total_price(),
        created_at=timezone.now()
    )
    order.generate_signature()

    cart.is_active = False
    cart.save(update_fields=['is_active'])

    return redirect('payment', order_id=order.id)


@login_required
def payment_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status != 'pending':
        messages.error(request, "Этот заказ уже обработан или отменён.")
        return redirect('profile')

    if request.method == 'POST':
        form = FakePaymentForm(request.POST)
        if form.is_valid():
            order.status = 'processing'
            order.save(update_fields=['status'])

            success = random.random() < 0.9
            order.status = 'completed' if success else 'cancelled'
            order.save(update_fields=['status'])
            return redirect('payment_result', order_id=order.id)
    else:
        form = FakePaymentForm()

    return render(request, 'checkout/payment.html', {
        'order': order,
        'form': form,
    })


@login_required
def payment_result(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'checkout/result.html', {
        'order': order
    })


@login_required
def generate_receipt(request, transaction_id):
    order = get_object_or_404(
        Order,
        transaction_id=transaction_id,
        user=request.user
    )
    is_valid_sig = order.verify_signature()
    sig_status = "HMAC Verified" if is_valid_sig else "Unverified"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Чек #{escape(str(order.transaction_id))}</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 40px; color: #333; }}
        .receipt-card {{ max-width: 500px; margin: 0 auto; border: 1px solid #e0e0e0; padding: 24px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .header {{ text-align: center; border-bottom: 2px dashed #ccc; padding-bottom: 16px; margin-bottom: 20px; }}
        .title {{ font-size: 22px; font-weight: bold; color: #2c3e50; margin: 0; }}
        .subtitle {{ font-size: 14px; color: #7f8c8d; margin-top: 4px; }}
        .row {{ display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 14px; }}
        .total-row {{ border-top: 2px solid #333; padding-top: 12px; font-size: 18px; font-weight: bold; }}
        .badge {{ display: inline-block; padding: 4px 8px; background: #e8f8f5; color: #27ae60; border-radius: 4px; font-size: 12px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="receipt-card">
        <div class="header">
            <div class="title">Floreal Paris</div>
            <div class="subtitle">Квитанция об оплате заказа</div>
        </div>
        <div class="row"><span>Номер транзакции:</span> <strong>{escape(str(order.transaction_id))}</strong></div>
        <div class="row"><span>Покупатель:</span> <span>{escape(order.user.username if order.user else 'Гость')}</span></div>
        <div class="row"><span>Дата:</span> <span>{order.created_at.strftime('%d.%m.%Y %H:%M')}</span></div>
        <div class="row"><span>Статус подписи:</span> <span class="badge">{sig_status}</span></div>
        <div class="row total-row"><span>Итоговая сумма:</span> <span>{order.total_amount} руб.</span></div>
    </div>
</body>
</html>"""

    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="receipt_{order.transaction_id}.html"'
    return response


# --- Админ функции ---

@login_required
def delete_review(request, review_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        return HttpResponseForbidden("Только администратор может удалять отзывы.")
    review = get_object_or_404(Review, id=review_id)
    product_id = review.product.id
    review.delete()
    messages.success(request, "Отзыв успешно удалён.")
    return redirect('product_detail', product_id=product_id)


def is_admin(user):
    return user.role == 'admin' or user.is_superuser


@login_required
@user_passes_test(is_admin)
def delete_user(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        messages.error(request, "Нельзя удалить самого себя.")
        return redirect('public_profile', username=username)
    if target.is_superuser:
        messages.error(request, "Нельзя удалить главного администратора.")
        return redirect('public_profile', username=username)

    if request.method == 'POST':
        target.delete()
        messages.success(request, f"Пользователь «{username}» и все его данные удалены.")
        return redirect('home')

    return redirect('public_profile', username=username)


# --- Чат ---

@login_required
def chat_list(request):
    rooms = ChatRoom.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user)
    ).order_by('-updated_at')
    return render(request, 'chat/chat_list.html', {'rooms': rooms})


@login_required
def chat_room(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in (room.buyer, room.seller):
        return HttpResponseForbidden()
    return render(request, 'chat/chat_room.html', {'room': room})


@login_required
def chat_messages(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in (room.buyer, room.seller):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    data = []
    for msg in room.messages.order_by('timestamp'):
        data.append({
            'id': msg.id,
            'sender': msg.sender.username,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        })
    return JsonResponse({'messages': data})


@login_required
def send_message(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    if request.user not in (room.buyer, room.seller):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Empty content'}, status=400)

    msg = Message.objects.create(
        chat_room=room,
        sender=request.user,
        content=content
    )
    room.save(update_fields=['updated_at'])

    return JsonResponse({
        'id': msg.id,
        'sender': msg.sender.username,
        'content': msg.content,
        'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
    })


@login_required
def start_chat(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    if product.seller == request.user:
        messages.error(request, "Нельзя писать самому себе.")
        return redirect('product_detail', product_id=product.id)

    room, created = ChatRoom.objects.get_or_create(
        product=product,
        buyer=request.user,
        seller=product.seller
    )
    return redirect('chat_room', room_id=room.id)