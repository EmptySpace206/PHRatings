"""Tests for tournament system endpoints"""
import pytest
from models import Tournament, TournamentParticipant, TournamentStatus
from datetime import datetime, timedelta

class TestCreateTournament:
    """Test create tournament endpoint"""
    
    def test_create_tournament_success(self, client, player_token, approved_player):
        """Test successful tournament creation"""
        future_time = (datetime.now() + timedelta(hours=2)).isoformat()
        
        response = client.post('/tournaments',
                              headers={'Authorization': f'Bearer {player_token}'},
                              json={
                                  'name': 'New Tournament',
                                  'host_id': approved_player['id'],
                                  'start_time': future_time
                              })
        
        assert response.status_code == 200
        assert 'tournament_id' in response.json
        assert response.json['name'] == 'New Tournament'
        
    def test_create_tournament_duplicate_name(self, client, player_token, approved_player, tournament):
        """Test creating tournament with duplicate name"""
        future_time = (datetime.now() + timedelta(hours=2)).isoformat()
        
        response = client.post('/tournaments',
                              headers={'Authorization': f'Bearer {player_token}'},
                              json={
                                  'name': tournament['name'],
                                  'host_id': approved_player['id'],
                                  'start_time': future_time
                              })
        
        assert response.status_code == 400
        assert 'already exists' in response.json['error'].lower()
        
    def test_create_tournament_past_time(self, client, player_token, approved_player):
        """Test creating tournament with past start time"""
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        
        response = client.post('/tournaments',
                              headers={'Authorization': f'Bearer {player_token}'},
                              json={
                                  'name': 'Past Tournament',
                                  'host_id': approved_player['id'],
                                  'start_time': past_time
                              })
        
        assert response.status_code == 400
        assert 'future' in response.json['error'].lower()

class TestJoinTournament:
    """Test join tournament endpoint"""
    
    def test_join_tournament_success(self, client, tournament, multiple_approved_players):
        """Test successfully joining a tournament"""
        # Login as player 2
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[1]['name'],
            'password': multiple_approved_players[1]['password']
        })
        token = login_response.json['token']
        
        response = client.post(f'/tournaments/{tournament["id"]}/join',
                              headers={'Authorization': f'Bearer {token}'},
                              json={})
        
        assert response.status_code == 200
        
        # Verify participant was added
        with client.application.app_context():
            participant = TournamentParticipant.query.filter_by(
                tournament_id=tournament['id'],
                player_id=multiple_approved_players[1]['id']
            ).first()
            assert participant is not None
            
    def test_join_tournament_as_host(self, client, player_token, tournament):
        """Test host trying to join their own tournament"""
        response = client.post(f'/tournaments/{tournament["id"]}/join',
                              headers={'Authorization': f'Bearer {player_token}'},
                              json={})
        
        assert response.status_code == 400
        assert 'host cannot participate' in response.json['error'].lower()
        
    def test_join_tournament_twice(self, client, tournament, multiple_approved_players):
        """Test joining same tournament twice"""
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[1]['name'],
            'password': multiple_approved_players[1]['password']
        })
        token = login_response.json['token']
        
        # Join first time
        client.post(f'/tournaments/{tournament["id"]}/join',
                   headers={'Authorization': f'Bearer {token}'},
                   json={})
        
        # Try to join again
        response = client.post(f'/tournaments/{tournament["id"]}/join',
                              headers={'Authorization': f'Bearer {token}'},
                              json={})
        
        assert response.status_code == 400
        assert 'already joined' in response.json['error'].lower()

class TestLeaveTournament:
    """Test leave tournament endpoint"""
    
    def test_leave_tournament_success(self, client, tournament, multiple_approved_players):
        """Test successfully leaving a tournament"""
        # Join tournament first
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[1]['name'],
            'password': multiple_approved_players[1]['password']
        })
        token = login_response.json['token']
        
        client.post(f'/tournaments/{tournament["id"]}/join',
                   headers={'Authorization': f'Bearer {token}'},
                   json={})
        
        # Now leave
        response = client.delete(f'/tournaments/{tournament["id"]}/leave',
                                headers={'Authorization': f'Bearer {token}'},
                                json={})
        
        assert response.status_code == 200
        
        # Verify participant was removed
        with client.application.app_context():
            participant = TournamentParticipant.query.filter_by(
                tournament_id=tournament['id'],
                player_id=multiple_approved_players[1]['id']
            ).first()
            assert participant is None
            
    def test_leave_tournament_not_joined(self, client, tournament, multiple_approved_players):
        """Test leaving tournament when not a participant"""
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[1]['name'],
            'password': multiple_approved_players[1]['password']
        })
        token = login_response.json['token']
        
        response = client.delete(f'/tournaments/{tournament["id"]}/leave',
                                headers={'Authorization': f'Bearer {token}'},
                                json={})
        
        assert response.status_code == 400
        assert 'not registered' in response.json['error'].lower()

class TestListTournaments:
    """Test list tournaments endpoint"""
    
    def test_list_tournaments(self, client, tournament):
        """Test listing all tournaments"""
        response = client.get('/tournaments')
        
        assert response.status_code == 200
        data = response.json
        assert len(data) >= 1
        assert any(t['name'] == tournament['name'] for t in data)
        
    def test_get_tournament_participants(self, client, tournament, multiple_approved_players):
        """Test getting tournament participants"""
        # Add a participant
        with client.application.app_context():
            participant = TournamentParticipant(
                tournament_id=tournament['id'],
                player_id=multiple_approved_players[1]['id']
            )
            from models import db
            db.session.add(participant)
            db.session.commit()
        
        response = client.get(f'/tournaments/{tournament["id"]}/participants')
        
        assert response.status_code == 200
        data = response.json
        assert len(data) >= 1
        assert any(p['player_name'] == multiple_approved_players[1]['name'] for p in data)