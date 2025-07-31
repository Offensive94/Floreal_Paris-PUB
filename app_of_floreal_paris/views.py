from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
import json
from django.db import transaction
from django.db import IntegrityError
from django.db import connection
import random
from django.db.models import Q




from .models import (
    User, Product, Cart, CartItem, Order,
    ChatRoom, Message, UserProfile, Review
)
from .forms import (
    RegisterForm, LoginForm, ProfileForm, ProductForm, ReviewForm, FakePaymentForm
)

# --- Аутентификация и профиль ---

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать, {}!'.format(user.username))
            return redirect('home')
        else:
            # покажем все ошибки формы в виде всплывающих сообщений
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
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
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, title, price, views
              FROM app_of_floreal_paris_product
             WHERE is_active = TRUE
             ORDER BY views DESC
             LIMIT 4
        """)
        rows = cursor.fetchall()
    popular_products = Product.objects.order_by('-views')[:4]
    new_products = Product.objects.order_by('-created_at')[:4]
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
    product.save()
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
    if product.seller != request.user:
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

@login_required()
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not (product.seller == request.user or request.user.role == 'admin'):
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
        # --- Поиск товаров через SQL-шаблон ---
        sql_products = """
            SELECT id, title, description, price, image, views
            FROM app_of_floreal_paris_product
            WHERE title ILIKE %s OR description ILIKE %s
            ORDER BY views DESC
        """
        pattern = f'%{query}%'
        with connection.cursor() as cursor:
            cursor.execute(sql_products, [pattern, pattern])
            rows = cursor.fetchall()
        for id, title, description, price, image, views in rows:
            product_results.append({
                'id': id,
                'title': title,
                'description': description,
                'price': price,
                'image': image,
                'views': views,
            })

        # --- Поиск пользователей через SQL-шаблон ---
        # Таблица пользователей — app_of_floreal_paris_user
        sql_users = """
            SELECT id, username, email, date_joined
            FROM app_of_floreal_paris_user
            WHERE username ILIKE %s OR email ILIKE %s
            ORDER BY date_joined DESC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql_users, [pattern, pattern])
            rows = cursor.fetchall()
        for id, username, email, date_joined in rows:
            user_results.append({
                'id': id,
                'username': username,
                'email': email,
                'joined': date_joined,
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
    items = list(cart.items.select_related('product'))
    # проверяем, что каждый product ещё существует
    removed = []
    for item in items:
        if not Product.objects.filter(pk=item.product_id).exists():
            removed.append(item.product.title)
            item.delete()
    if removed:
        # одно уведомление со всеми удалёнными ((НЕ РАБОТАЕТ!!!))
        messages.warning(
            request,
            "Эти товары были удалены продавцом и убраны из вашей корзины: "
            + ", ".join(removed)
        )
        items = list(cart.items.select_related('product'))

    return render(request, 'cart/view_cart.html', {
        'cart': cart,
        'items': items,
    })


@login_required
@require_POST
def add_to_cart(request):
    if request.user.role == 'admin':
        return JsonResponse({'success': False, 'error': 'Администраторы не могут пользоваться корзиной.'}, status=403)
    data = json.loads(request.body)
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    cart = get_active_cart(request.user)
    product = get_object_or_404(Product, id=product_id, is_active=True)

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if created:
        item.quantity = quantity
    else:
        item.quantity += quantity
    item.save()

    return JsonResponse({
        'success': True,
        'cart_count': cart.total_items(),
        'cart_total': str(cart.total_price())
    })


def update_cart_item(request):
    data = json.loads(request.body)
    pid = data.get('product_id')
    action = data.get('action')  # 'increment' или 'decrement'

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
            # если было 1, то удаляем полностью
            item.delete()

    # пересчитываем
    count = cart.total_items()
    total = cart.total_price()
    # если после декремента удалился, то qty = 0
    try:
        qty = CartItem.objects.get(cart=cart, product_id=pid).quantity
    except CartItem.DoesNotExist:
        qty = 0

    return JsonResponse({
        'success': True,
        'cart_count': count,
        'cart_total': str(total),
        'item_quantity': qty,
        'product_id': pid,
    })


@login_required
@require_POST
def remove_from_cart(request):
    data = json.loads(request.body)
    product_id = data.get('product_id')

    # Берём именно активную корзину
    cart = get_active_cart(request.user)
    # Удаляем элемент(ы)
    CartItem.objects.filter(cart=cart, product_id=product_id).delete()

    return JsonResponse({
        'success': True,
        'cart_count': cart.total_items(),
        'cart_total': str(cart.total_price())
    })

@require_POST
@login_required
def remove_cart_item(request):
    data = json.loads(request.body)
    product_id = data.get("product_id")

    try:
        cart = request.user.cart
        cart.items.filter(product_id=product_id).delete()
        cart.refresh_from_db()
        return JsonResponse({
            "success": True,
            "cart_count": cart.total_items,
            "cart_total": str(cart.total_price),
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@require_POST
def clear_cart(request):
    # Активная корзина
    cart = get_active_cart(request.user)
    # Удаляем все товары
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

    # Создаём заказ
    order = Order.objects.create(
        user=request.user,
        cart=cart,
        total_amount=cart.total_price(),
        created_at=timezone.now()
    )
    order.generate_signature()

    # Деактивируем корзину, чтобы не создать по ней ещё раз
    cart.is_active = False
    cart.save()

    # Перенаправляем на страницу «оплаты»
    return redirect('payment', order_id=order.id)

@login_required
def payment_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status != 'pending':
        messages.error(request, "Этот заказ уже оплачен или отменён.")
        return redirect('profile')

    if request.method == 'POST':
        form = FakePaymentForm(request.POST)
        if form.is_valid():
            # эмулируем отправку на шлюз
            order.status = 'processing'
            order.save(update_fields=['status'])
            # через момент «решаем» случайно успех/отказ (а чё поделать, реальной оплаты то нет)
            success = random.random() < 0.8  # 80% вероятность успеха
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
    # показываем страницу с итоговым статусом
    return render(request, 'checkout/result.html', {
        'order': order
    })


@login_required
def generate_receipt(request, transaction_id):
    # Ищем заказ именно по UUID‑полю transaction_id
    order = get_object_or_404(
        Order,
        transaction_id=transaction_id,
        user=request.user
    )
    html = f"""
    <html><head><title>Чек #{order.transaction_id}</title></head><body>
    <h1>Чек #{order.transaction_id}</h1>
    <p>Сумма: {order.total_amount} руб.</p>
    </body></html>
    """
    response = HttpResponse(html, content_type='text/html')
    response['Content-Disposition'] = (
        f'attachment; filename="receipt_{order.transaction_id}.html"'
    )
    return response

# --- Чат --- (вырезано)

# --- Админ ---

@login_required
def delete_review(request, review_id):
    if request.user.role != 'admin':
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
        return redirect('home')  # или куда хотите после

    return redirect('public_profile', username=username)

@login_required
def chat_list(request):
    # все комнаты, где я — либо buyer, либо seller
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
    """
    Возвращает JSON со всеми сообщениями в комнате.
    """
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
    """
    Принимает POST { content: "...", attachment: file? }
    """
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
    # Обновим updated_at у комнаты, чтобы сортировка в списке работала
    room.save()

    return JsonResponse({
        'id': msg.id,
        'sender': msg.sender.username,
        'content': msg.content,
        'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
    })

@login_required
def start_chat(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    # не сам с собой
    if product.seller == request.user:
        messages.error(request, "Нельзя писать самому себе.")
        return redirect('product_detail', product_id=product.id)

    room, created = ChatRoom.objects.get_or_create(
        product=product,
        buyer=request.user,
        seller=product.seller
    )
    return redirect('chat_room', room_id=room.id)