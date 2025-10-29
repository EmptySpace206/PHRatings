"""Tests for player authentication endpoints"""
import pytest
from models import PlayerStatus

class TestPlayerLogin:
    """Test player login endpoint"""
    
    def test_player_login_success(self, client, approved_player):
        """Test successful player login"""
        response = client.post('/player/login', json={
            'name': approved_player['name'],
            'password': approved_player['password']
        })
        
        assert response.status_code == 200
        data = response.json
        assert 'token' in data
        assert 'expires_at' in data
        assert data['user_type'] == 'player'
        assert data['player_id'] == approved_player['id']
        assert data['player_name'] == approved_player['name']
        
    def test_player_login_invalid_credentials(self, client, approved_player):
        """Test player login with invalid credentials"""
        response = client.post('/player/login', json={
            'name': approved_player['name'],
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 401
        assert 'error' in response.json
        
    def test_player_login_pending_status(self, client, pending_player):
        """Test player login when status is pending"""
        response = client.post('/player/login', json={
            'name': pending_player['name'],
            'password': pending_player['password']
        })
        
        assert response.status_code == 403
        assert 'not approved' in response.json['error'].lower()
        
    def test_player_login_missing_fields(self, client):
        """Test player login with missing fields"""
        response = client.post('/player/login', json={
            'name': 'TestPlayer'
        })
        
        assert response.status_code == 400

class TestPlayerLogout:
    """Test player logout endpoint"""
    
    def test_player_logout_success(self, client, player_token):
        """Test successful player logout"""
        response = client.post('/player/logout',
                              headers={'Authorization': f'Bearer {player_token}'})
        
        assert response.status_code == 200
        assert response.json['message'] == 'Logged out successfully'
        
    def test_player_logout_without_auth(self, client):
        """Test player logout without authentication"""
        response = client.post('/player/logout')
        
        assert response.status_code == 401