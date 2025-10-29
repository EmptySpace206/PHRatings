"""Tests for player management endpoints"""
import pytest
from models import db, Player, PlayerStatus

class TestPlayerRegistration:
    """Test player registration endpoint"""
    
    def test_register_player_success(self, client):
        """Test successful player registration"""
        response = client.post('/players', json={
            'name': 'NewPlayer',
            'age': 25,
            'weight': 180.5,
            'password': 'securepassword'
        })
        
        assert response.status_code == 200
        data = response.json
        assert data['name'] == 'NewPlayer'
        assert data['age'] == 25
        assert data['weight'] == 180.5
        assert data['status'] == 'pending'
        assert data['elo'] == 1200
        
    def test_register_player_duplicate_name(self, client, approved_player):
        """Test registration with duplicate name"""
        response = client.post('/players', json={
            'name': approved_player['name'],
            'age': 25,
            'weight': 180.5,
            'password': 'password'
        })
        
        assert response.status_code == 400
        assert 'already exists' in response.json['error'].lower()
        
    def test_register_player_missing_fields(self, client):
        """Test registration with missing fields"""
        response = client.post('/players', json={
            'name': 'NewPlayer',
            'age': 25
        })
        
        assert response.status_code == 400
        assert 'missing required fields' in response.json['error'].lower()

class TestPlayerApproval:
    """Test player approval endpoints"""
    
    def test_approve_player_success(self, client, admin_token, pending_player):
        """Test successful player approval"""
        response = client.post(f'/admin/players/{pending_player["id"]}/approve',
                              headers={'Authorization': f'Bearer {admin_token}'})
        
        assert response.status_code == 200
        assert response.json['message'] == 'Player approved'
        
        # Verify player status changed
        with client.application.app_context():
            player = Player.query.get(pending_player['id'])
            assert player.status == PlayerStatus.APPROVED
            
    def test_approve_player_not_pending(self, client, admin_token, approved_player):
        """Test approving already approved player"""
        response = client.post(f'/admin/players/{approved_player["id"]}/approve',
                              headers={'Authorization': f'Bearer {admin_token}'})
        
        assert response.status_code == 400
        assert 'not pending' in response.json['error'].lower()
        
    def test_approve_player_without_auth(self, client, pending_player):
        """Test approval without admin authentication"""
        response = client.post(f'/admin/players/{pending_player["id"]}/approve')
        
        assert response.status_code == 401

class TestPlayerRejection:
    """Test player rejection endpoints"""
    
    def test_reject_player_success(self, client, admin_token, pending_player):
        """Test successful player rejection"""
        player_id = pending_player['id']
        response = client.delete(f'/admin/players/{player_id}/reject',
                                headers={'Authorization': f'Bearer {admin_token}'})
        
        assert response.status_code == 200
        assert 'rejected' in response.json['message'].lower()
        
        # Verify player was deleted
        with client.application.app_context():
            player = Player.query.get(player_id)
            assert player is None
            
    def test_reject_approved_player(self, client, admin_token, approved_player):
        """Test rejecting already approved player"""
        response = client.delete(f'/admin/players/{approved_player["id"]}/reject',
                                headers={'Authorization': f'Bearer {admin_token}'})
        
        assert response.status_code == 400

class TestListPlayers:
    """Test list players endpoint"""
    
    def test_list_all_players(self, client, multiple_approved_players):
        """Test listing all players"""
        response = client.get('/players')
        
        assert response.status_code == 200
        data = response.json
        assert len(data) >= 3
        assert all('name' in player for player in data)
        assert all('elo' in player for player in data)
        
    def test_list_pending_players_as_admin(self, client, admin_token, pending_player):
        """Test listing pending players as admin"""
        response = client.get('/admin/players/pending',
                             headers={'Authorization': f'Bearer {admin_token}'})
        
        assert response.status_code == 200
        data = response.json
        assert len(data) >= 1
        assert any(p['name'] == pending_player['name'] for p in data)
        
    def test_list_pending_players_without_auth(self, client):
        """Test listing pending players without authentication"""
        response = client.get('/admin/players/pending')
        
        assert response.status_code == 401

class TestUpdateWeight:
    """Test update weight endpoint"""
    
    def test_update_weight_as_player(self, client, player_token, approved_player):
        """Test player updating their own weight"""
        response = client.put('/players/weight',
                             headers={'Authorization': f'Bearer {player_token}'},
                             json={'weight': 185.5})
        
        assert response.status_code == 200
        assert response.json['new_weight'] == 185.5
        
    def test_update_weight_as_admin(self, client, admin_token, approved_player):
        """Test admin updating player weight"""
        response = client.put('/players/weight',
                             headers={'Authorization': f'Bearer {admin_token}'},
                             json={'weight': 190.0, 'player_id': approved_player['id']})
        
        assert response.status_code == 200
        assert response.json['new_weight'] == 190.0
        
    def test_update_weight_without_auth(self, client):
        """Test updating weight without authentication"""
        response = client.put('/players/weight', json={'weight': 185.5})
        
        assert response.status_code == 401
        
    def test_update_weight_missing_weight(self, client, player_token):
        """Test updating weight without providing weight value"""
        response = client.put('/players/weight',
                             headers={'Authorization': f'Bearer {player_token}'},
                             json={})
        
        assert response.status_code == 400