"""Tests for challenge system endpoints"""
import pytest
from models import Challenge, ChallengeStatus, Match
from datetime import datetime

class TestCreateChallenge:
    """Test create challenge endpoint"""
    
    def test_create_challenge_success(self, client, multiple_approved_players):
        """Test successful challenge creation"""
        players = multiple_approved_players
        
        # Login as player 1 (challenger)
        login_response = client.post('/player/login', json={
            'name': players[0]['name'],
            'password': players[0]['password']
        })
        token = login_response.json['token']
        
        response = client.post('/challenges',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                  'challenger_id': players[0]['id'],
                                  'challenged_id': players[1]['id'],
                                  'host_id': players[2]['id']
                              })
        
        assert response.status_code == 200
        assert 'challenge_id' in response.json
        assert 'expires_at' in response.json
        
    def test_create_challenge_self_challenge(self, client, approved_player):
        """Test creating challenge to self"""
        # Login first
        login_response = client.post('/player/login', json={
            'name': approved_player['name'],
            'password': approved_player['password']
        })
        token = login_response.json['token']
        
        response = client.post('/challenges',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                  'challenger_id': approved_player['id'],
                                  'challenged_id': approved_player['id'],
                                  'host_id': approved_player['id']
                              })
        
        assert response.status_code == 400
        assert 'cannot challenge yourself' in response.json['error'].lower()
        
    def test_create_challenge_host_is_player(self, client, multiple_approved_players):
        """Test creating challenge where host is one of the players"""
        players = multiple_approved_players
        
        login_response = client.post('/player/login', json={
            'name': players[0]['name'],
            'password': players[0]['password']
        })
        token = login_response.json['token']
        
        response = client.post('/challenges',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                  'challenger_id': players[0]['id'],
                                  'challenged_id': players[1]['id'],
                                  'host_id': players[0]['id']  # Host is challenger
                              })
        
        assert response.status_code == 400
        assert 'host cannot be one of the players' in response.json['error'].lower()
        
    def test_create_challenge_unauthorized(self, client, multiple_approved_players):
        """Test creating challenge as non-challenger"""
        players = multiple_approved_players
        
        # Login as player 2, but try to create challenge as player 1
        login_response = client.post('/player/login', json={
            'name': players[1]['name'],
            'password': players[1]['password']
        })
        token = login_response.json['token']
        
        response = client.post('/challenges',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                  'challenger_id': players[0]['id'],
                                  'challenged_id': players[1]['id'],
                                  'host_id': players[2]['id']
                              })
        
        assert response.status_code == 403

class TestAcceptChallenge:
    """Test accept challenge endpoint"""
    
    def test_accept_challenge_success(self, client, challenge, multiple_approved_players):
        """Test successful challenge acceptance"""
        # Login as challenged player (player 2)
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[1]['name'],
            'password': multiple_approved_players[1]['password']
        })
        token = login_response.json['token']
        
        response = client.post(f'/challenges/{challenge["id"]}/accept',
                              headers={'Authorization': f'Bearer {token}'},
                              json={})
        
        assert response.status_code == 200
        assert 'match_id' in response.json
        
        # Verify match was created
        with client.application.app_context():
            match = Match.query.filter_by(challenge_id=challenge['id']).first()
            assert match is not None
            
    def test_accept_challenge_wrong_player(self, client, challenge, multiple_approved_players):
        """Test accepting challenge as wrong player"""
        # Login as player 1 (challenger, not challenged)
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[0]['name'],
            'password': multiple_approved_players[0]['password']
        })
        token = login_response.json['token']
        
        response = client.post(f'/challenges/{challenge["id"]}/accept',
                              headers={'Authorization': f'Bearer {token}'},
                              json={})
        
        assert response.status_code == 403

class TestListChallenges:
    """Test list challenges endpoint"""
    
    def test_list_challenges(self, client, challenge):
        """Test listing all challenges"""
        response = client.get('/challenges')
        
        assert response.status_code == 200
        data = response.json
        assert len(data) >= 1
        assert any(c['id'] == challenge['id'] for c in data)