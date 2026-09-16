from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from app_of_floreal_paris.models import Product

User = get_user_model()


class DashboardPermissionsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.buyer = User.objects.create_user(
            username='buyer',
            email='buyer@example.com',
            password='Password123!',
            role='buyer'
        )
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='Password123!',
            role='admin'
        )
        self.superuser = User.objects.create_superuser(
            username='super_admin',
            email='super@example.com',
            password='Password123!'
        )
        self.product = Product.objects.create(
            seller=self.buyer,
            title='Тестовый товар',
            description='Описание товара',
            price=Decimal('100.00')
        )

    def test_buyer_forbidden_from_dashboard(self):
        self.client.login(username='buyer', password='Password123!')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302) # Redirect due to user_passes_test

    def test_admin_can_access_dashboard_and_products(self):
        self.client.login(username='admin_user', password='Password123!')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('dashboard:product_list'), {'q': 'Тестовый'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый товар')

    def test_superuser_user_list_access(self):
        self.client.login(username='super_admin', password='Password123!')
        response = self.client.get(reverse('dashboard:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'buyer')
