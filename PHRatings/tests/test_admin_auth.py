"""Tests for admin authentication endpoints"""
import pytest
from models import db, Admin, AdminSession

class TestAdminLogin:
    """Test admin login endpoint"""
    
    def test_admin_login_success(self, client, admin_user):
        """Test successful admin login"""
        response = client.post('/admin/login', json={
            'username': 'testadmin',
            'password': 'testpassword'
        })
        
        assert response.status_code == 200
        data = response.json
        assert 'token' in data
        assert 'expires_at' in data
        assert data['user_type'] == 'admin'
        
    def test_admin_login_invalid_credentials(self, client, admin_user):
        """Test admin login with invalid credentials"""
        response = client.post('/admin/login', json={
            'username': 'testadmin',
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 401
        assert 'error' in response.json
        
    def test_admin_login_missing_fields(self, client):
        """Test admin login with missing fields"""
        response = client.post('/admin/login', json={
            'username': 'testadmin'
        })
        
        assert response.status_code == 400
        assert 'error' in response.json
        
    def test_admin_login_nonexistent_user(self, client):
        """Test admin login with non-existent username"""
        response = client.post('/admin/login', json={
            'username': 'nonexistent',
            'password': 'password'
        })
        
        assert response.status_code == 401

class TestAdminLogout:
    """Test admin logout endpoint"""
    
    def test_admin_logout_success(self, client, admin_token):
        """Test successful admin logout"""
        response = client.post('/admin/logout', 
                              headers={'Authorization': f'Bearer {admin_token}'})
        
        assert response.status_code == 200
        assert response.json['message'] == 'Logged out successfully'
        
    def test_admin_logout_without_auth(self, client):
        """Test admin logout without authentication"""
        response = client.post('/admin/logout')
        
        assert response.status_code == 401
        
    def test_admin_logout_invalid_token(self, client):
        """Test admin logout with invalid token"""
        response = client.post('/admin/logout',
                              headers={'Authorization': 'Bearer invalidtoken'})
        
        assert response.status_code == 401