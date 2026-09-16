import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from app_of_floreal_paris.models import Product, Cart, CartItem, Order, UserProfile, Review

User = get_user_model()


class UserModelTests(TestCase):
    def test_user_creation_creates_profile(self):
        user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='Password123!'
        )
        self.assertEqual(user.role, 'buyer')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, UserProfile)


class ProductModelTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@example.com',
            password='Password123!',
            role='seller'
        )

    def test_product_creation(self):
        product = Product.objects.create(
            seller=self.seller,
            title='Красные розы',
            description='Букет из 101 розы',
            price=Decimal('5000.00'),
            status='in_stock'
        )
        self.assertEqual(product.title, 'Красные розы')
        self.assertEqual(product.price, Decimal('5000.00'))
        self.assertTrue(product.is_active)


class CartAndOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            email='buyer@example.com',
            password='Password123!'
        )
        self.seller = User.objects.create_user(
            username='seller2',
            email='seller2@example.com',
            password='Password123!',
            role='seller'
        )
        self.product1 = Product.objects.create(
            seller=self.seller,
            title='Тюльпаны',
            description='Свежие тюльпаны',
            price=Decimal('150.00'),
            status='in_stock'
        )
        self.product2 = Product.objects.create(
            seller=self.seller,
            title='Пионы',
            description='Розовые пионы',
            price=Decimal('300.00'),
            status='in_stock'
        )

    def test_cart_totals_calculation(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product1, quantity=3) # 450
        CartItem.objects.create(cart=cart, product=self.product2, quantity=2) # 600

        self.assertEqual(cart.total_items(), 5)
        self.assertEqual(cart.total_price(), Decimal('1050.00'))

    def test_order_signature_generation_and_verification(self):
        cart = Cart.objects.create(user=self.user)
        order = Order.objects.create(
            user=self.user,
            cart=cart,
            total_amount=Decimal('1050.00')
        )
        order.generate_signature()

        self.assertTrue(bool(order.digital_signature))
        self.assertTrue(order.verify_signature())

        # Проверка отлова подделки
        order.total_amount = Decimal('1.00')
        self.assertFalse(order.verify_signature())


class ViewsIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='buyer_test',
            email='buyer_test@example.com',
            password='Password123!'
        )
        self.seller = User.objects.create_user(
            username='seller_test',
            email='seller_test@example.com',
            password='Password123!',
            role='seller'
        )
        self.product = Product.objects.create(
            seller=self.seller,
            title='Орхидея Белая',
            description='Красивая орхидея в горшке',
            price=Decimal('1200.00'),
            status='in_stock'
        )

    def test_search_view(self):
        response = self.client.get(reverse('search'), {'q': 'Орхидея'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Орхидея Белая')

    def test_add_to_cart_ajax(self):
        self.client.login(username='buyer_test', password='Password123!')
        response = self.client.post(
            reverse('add_to_cart'),
            data=json.dumps({'product_id': self.product.id, 'quantity': 2}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cart_count'], 2)
        self.assertEqual(data['cart_total'], '2400.00')

    def test_review_submission_unique_constraint(self):
        self.client.login(username='buyer_test', password='Password123!')
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            comment='Прекрасно!'
        )
        response = self.client.post(
            reverse('add_review', kwargs={'product_id': self.product.id}),
            {'rating': 4, 'comment': 'Второй отзыв'}
        )
        self.assertEqual(Review.objects.filter(product=self.product, user=self.user).count(), 1)
