import json
from rest_framework.test import APITestCase, APIClient
from clients.models import User
from django.contrib.auth.hashers import check_password


# Login
class LoginTests(APITestCase):
    def test_authenticate_valid(self):
        user = User(email="fabricio@asap.uy", is_active=True)
        user.set_password("1234")
        user.save()

        response = self.client.post('/api/userauth/authenticate/', {'email': 'fabricio@asap.uy', 'password': '1234'})
        self.assertEqual(response.status_code, 200)

    def test_authenticate_invalid(self):
        user = User(email="fabricio@asap.uy", password="1234", is_active=True)
        user.save()

        response = self.client.post('/api/userauth/authenticate/', {'email': 'fabricio@asap.uy', 'password': '1234'})
        self.assertEqual(response.status_code, 403)

    def test_authenticate_invalid_username_not_provided(self):
        response = self.client.post('/api/userauth/authenticate/', {'password': '1234'})
        self.assertEqual(response.status_code, 400)
        content = response.data
        self.assertEqual(len(content['detail']['email']), 1)

    def test_authenticate_invalid_password_not_provided(self):
        user = User(email="fabricio@asap.uy", password="1234", is_active=True)
        user.set_password("1234")
        user.save()
        response = self.client.post('/api/userauth/authenticate/', {'email': 'fabricio@asap.uy'})
        self.assertEqual(response.status_code, 400)
        content = response.data
        self.assertEqual(len(content['detail']['password']), 1)


# Authenticate token
class AuthenticateTokenTests(APITestCase):
    def test_authenticate_token_valid(self):
        user = User(email="fabricio@asap.uy", is_active=True)
        user.set_password("1234")
        user.save()

        response = self.client.post('/api/userauth/authenticate/', {'email': 'fabricio@asap.uy', 'password': '1234'})
        self.assertEqual(response.status_code, 200)

        content = response.data
        token = content['token']
        response = self.client.post('/api/userauth/authenticatetoken/', {'token': token})
        self.assertEqual(response.status_code, 200)

    def test_authenticate_token_invalid(self):
        response = self.client.post('/api/userauth/authenticatetoken/', {'token': 'token'})
        self.assertEqual(response.status_code, 403)

    def test_authenticate_token_invalid_token_not_provided(self):
        response = self.client.post('/api/userauth/authenticatetoken/')
        self.assertEqual(response.status_code, 400)


# Change password
class ChangePassword(APITestCase):
    def test_change_password_valid(self):
        user = User(email="fabricio@asap.uy", is_active=True)
        user.set_password("1234")
        user.save()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post('/api/userauth/changepassword/', {'old_password': '1234', 'new_password': 'Asapadmin1!'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(check_password("Asapadmin1!", User.objects.get().password), True)

    def test_change_password_invalid_old_password(self):
        user = User(email="fabricio@asap.uy", is_active=True)
        user.set_password("1234")
        user.save()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post('/api/userauth/changepassword/',
                               {'old_password': '12345678', 'new_password': 'Asapadmin1!'})
        self.assertEqual(response.status_code, 400)
        content = response.data
        self.assertEqual(len(content['detail']['old_password']), 1)

    def test_change_password_invalid_old_password_not_provided(self):
        user = User(email="fabricio@asap.uy", is_active=True)
        user.set_password("1234")
        user.save()

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post('/api/userauth/changepassword/', {'new_password': 'Asapadmin1!'})
        self.assertEqual(response.status_code, 400)
        content = response.data
        self.assertEqual(len(content['detail']['old_password']), 1)
