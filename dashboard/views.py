from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from app_of_floreal_paris.models import User, Product, Review

def is_ga(user):
    return user.is_superuser

def is_admin(user):
    return user.role == 'admin' or user.is_superuser

@login_required
@user_passes_test(is_admin)
def index(request):
    return render(request, 'index.html')

@login_required
@user_passes_test(is_ga)
def user_list(request):
    """
    Если в GET есть id — ищем пользователя ровно по этому ID,
    иначе выводим всех.
    """
    id_q = request.GET.get('id', '').strip()
    if id_q.isdigit():
        sql = "SELECT * FROM app_of_floreal_paris_user WHERE id = %s"
        users = list(User.objects.raw(sql, [id_q]))
    else:
        users = User.objects.all().order_by('-date_joined')
    return render(request, 'users.html', {
        'users': users,
        'search_id': id_q,
    })

@login_required
@user_passes_test(is_ga)
def toggle_admin(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden()
    u = get_object_or_404(User, pk=pk)
    if u.is_superuser:
        return JsonResponse({'error': 'Нельзя менять ГА'}, status=400)
    u.role = 'admin' if u.role != 'admin' else 'buyer'
    u.save(update_fields=['role'])
    return JsonResponse({'success': True, 'new_role': u.role})

@login_required
@user_passes_test(is_admin)
def product_list(request):
    """
    Если в GET есть q — ищем по ключевым словам в названии и описании,
    иначе показываем все товары.
    """
    q = request.GET.get('q', '').strip()
    if q:
        pattern = f'%{q}%'
        sql = """
            SELECT *
              FROM app_of_floreal_paris_product
             WHERE title ILIKE %s OR description ILIKE %s
             ORDER BY views DESC
        """
        products = list(Product.objects.raw(sql, [pattern, pattern]))
    else:
        products = Product.objects.all().order_by('-created_at')
    return render(request, 'products.html', {
        'products': products,
        'query': q,
    })

@login_required
@user_passes_test(is_admin)
def delete_product(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden()
    p = get_object_or_404(Product, pk=pk)
    p.delete()
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_admin)
def review_list(request):
    revs = Review.objects.select_related('product','user').order_by('-created_at')
    return render(request, 'reviews.html', {'reviews': revs})

@login_required
@user_passes_test(is_admin)
def delete_review(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden()
    r = get_object_or_404(Review, pk=pk)
    r.delete()
    return JsonResponse({'success': True})
