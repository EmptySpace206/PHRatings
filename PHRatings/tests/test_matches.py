"""Tests for match system endpoints"""
import pytest
from models import Match, MatchStatus
from datetime import datetime, timedelta

class TestRecordMatchResult:
    """Test record match result endpoint"""
    
    def test_record_match_success(self, client, pending_match, multiple_approved_players):
        """Test successfully recording match result"""
        # Login as host (player 3)
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[2]['name'],
            'password': multiple_approved_players[2]['password']
        })
        token = login_response.json['token']
        
        response = client.post('/matches/result',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                  'host_id': multiple_approved_players[2]['id'],
                                  'player1_id': multiple_approved_players[0]['id'],
                                  'player2_id': multiple_approved_players[1]['id'],
                                  'winner_id': multiple_approved_players[0]['id']
                              })
        
        assert response.status_code == 200
        assert 'winner_new_elo' in response.json
        assert 'loser_new_elo' in response.json
        
        # Verify match was updated
        with client.application.app_context():
            match = Match.query.get(pending_match['id'])
            assert match.status == MatchStatus.COMPLETED
            assert match.winner_id == multiple_approved_players[0]['id']
            
    def test_record_match_wrong_host(self, client, pending_match, multiple_approved_players):
        """Test recording match as wrong host"""
        # Login as player 1 (not the host)
        # The pending_match fixture has host_id = Player 3
        # Player 1 tries to claim they are the host, but the match belongs to Player 3
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[0]['name'],
            'password': multiple_approved_players[0]['password']
        })
        token = login_response.json['token']
        
        response = client.post('/matches/result',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                  'host_id': multiple_approved_players[0]['id'],
                                  'player1_id': multiple_approved_players[0]['id'],
                                  'player2_id': multiple_approved_players[1]['id'],
                                  'winner_id': multiple_approved_players[0]['id']
                              })
        
        # Expect 400 because the match found belongs to Player 3, not Player 1
        assert response.status_code == 400
        assert 'only the match host can record results' in response.json['error'].lower()
        
    def test_record_match_no_pending_match(self, client, multiple_approved_players):
        """Test recording result when no pending match exists"""
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[2]['name'],
            'password': multiple_approved_players[2]['password']
        })
        token = login_response.json['token']
        
        response = client.post('/matches/result',
                              headers={'Authorization': f'Bearer {token}'},
                              json={
                                  'host_id': multiple_approved_players[2]['id'],
                                  'player1_id': multiple_approved_players[0]['id'],
                                  'player2_id': multiple_approved_players[1]['id'],
                                  'winner_id': multiple_approved_players[0]['id']
                              })
        
        assert response.status_code == 404

class TestUndoMatch:
    """Test undo match endpoint"""
    
    def test_undo_match_success(self, client, multiple_approved_players):
        """Test successfully undoing a match"""
        # First complete a match
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[2]['name'],
            'password': multiple_approved_players[2]['password']
        })
        token = login_response.json['token']
        
        # Create and complete a match
        with client.application.app_context():
            from models import db
            match = Match(
                player1_id=multiple_approved_players[0]['id'],
                player2_id=multiple_approved_players[1]['id'],
                host_id=multiple_approved_players[2]['id'],
                winner_id=multiple_approved_players[0]['id'],
                status=MatchStatus.COMPLETED,
                completed_at=datetime.now(),
                elo_change=20.0
            )
            db.session.add(match)
            db.session.commit()
            match_id = match.id
        
        # Undo the match
        response = client.post('/matches/undo',
                              headers={'Authorization': f'Bearer {token}'},
                              json={})
        
        assert response.status_code == 200
        assert 'winner_reverted_elo' in response.json
        
        # Verify match status changed
        with client.application.app_context():
            match = Match.query.get(match_id)
            assert match.status == MatchStatus.UNDONE
            
    def test_undo_match_expired(self, client, multiple_approved_players):
        """Test undoing match after time limit"""
        login_response = client.post('/player/login', json={
            'name': multiple_approved_players[2]['name'],
            'password': multiple_approved_players[2]['password']
        })
        token = login_response.json['token']
        
        # Create a match completed 11 minutes ago
        with client.application.app_context():
            from models import db
            match = Match(
                player1_id=multiple_approved_players[0]['id'],
                player2_id=multiple_approved_players[1]['id'],
                host_id=multiple_approved_players[2]['id'],
                winner_id=multiple_approved_players[0]['id'],
                status=MatchStatus.COMPLETED,
                completed_at=datetime.now() - timedelta(minutes=11),
                elo_change=20.0
            )
            db.session.add(match)
            db.session.commit()
        
        response = client.post('/matches/undo',
                              headers={'Authorization': f'Bearer {token}'},
                              json={})
        
        assert response.status_code == 403
        assert 'time limit' in response.json['error'].lower()

class TestListMatches:
    """Test list matches endpoint"""
    
    def test_list_all_matches(self, client, pending_match):
        """Test listing all matches"""
        response = client.get('/matches')
        
        assert response.status_code == 200
        data = response.json
        assert len(data) >= 1
        
    def test_list_matches_by_player(self, client, pending_match, multiple_approved_players):
        """Test listing matches for specific player"""
        player_id = multiple_approved_players[0]['id']
        response = client.get(f'/matches?player_id={player_id}')
        
        assert response.status_code == 200
        data = response.json
        assert all(
            m['player1_id'] == player_id or m['player2_id'] == player_id
            for m in data
        )