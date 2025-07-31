from .models import Cart

def cart_summary(request):
    if request.user.is_authenticated:
        # берём или создаём активную корзину
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if not cart:
            cart = Cart.objects.create(user=request.user)
        count = cart.total_items()
        total = cart.total_price()
    else:
        count = 0
        total = 0
    return {
        'cart_count': count,
        'cart_total': total
    }
