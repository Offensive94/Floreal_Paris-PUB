from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from app_of_floreal_paris.models import User, Product, Review


def is_ga(user):
    return user.is_authenticated and user.is_superuser


def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


@login_required
@user_passes_test(is_admin)
def index(request):
    return render(request, 'index.html')


@login_required
@user_passes_test(is_ga)
def user_list(request):
    id_q = request.GET.get('id', '').strip()
    if id_q.isdigit():
        users = User.objects.filter(pk=int(id_q))
    else:
        users = User.objects.all().order_by('-date_joined')
    return render(request, 'users.html', {
        'users': users,
        'search_id': id_q,
    })


@login_required
@require_POST
@user_passes_test(is_ga)
def toggle_admin(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u.is_superuser:
        return JsonResponse({'error': 'Нельзя менять роли главного администратора'}, status=400)
    u.role = 'admin' if u.role != 'admin' else 'buyer'
    u.save(update_fields=['role'])
    return JsonResponse({'success': True, 'new_role': u.role})


@login_required
@user_passes_test(is_admin)
def product_list(request):
    q = request.GET.get('q', '').strip()
    if q:
        products = Product.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        ).select_related('seller').only(
            'id', 'title', 'description', 'price', 'views', 'created_at', 'seller__username'
        ).order_by('-views')
    else:
        products = Product.objects.select_related('seller').only(
            'id', 'title', 'description', 'price', 'views', 'created_at', 'seller__username'
        ).order_by('-created_at')
    return render(request, 'products.html', {
        'products': products,
        'query': q,
    })


@login_required
@require_POST
@user_passes_test(is_admin)
def delete_product(request, pk):
    p = get_object_or_404(Product, pk=pk)
    p.delete()
    return JsonResponse({'success': True})


@login_required
@user_passes_test(is_admin)
def review_list(request):
    revs = Review.objects.select_related('product', 'user').order_by('-created_at')
    return render(request, 'reviews.html', {'reviews': revs})


@login_required
@require_POST
@user_passes_test(is_admin)
def delete_review(request, pk):
    r = get_object_or_404(Review, pk=pk)
    r.delete()
    return JsonResponse({'success': True})
