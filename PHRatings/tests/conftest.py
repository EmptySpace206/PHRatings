"""Pytest configuration and shared fixtures for testing"""
import pytest
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, Admin, Player, PlayerSession, AdminSession, Tournament, Challenge, Match, PlayerStatus, TournamentStatus, ChallengeStatus, MatchStatus

@pytest.fixture(scope='function')
def app():
    """Create and configure a test app instance"""
    test_app = create_app()
    test_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    })
    
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Create a test client"""
    return app.test_client()

@pytest.fixture(scope='function')
def admin_user(app):
    """Create an admin user for testing"""
    with app.app_context():
        admin = Admin(username='testadmin')
        admin.set_password('testpassword')
        db.session.add(admin)
        db.session.commit()
        # Return dict to avoid session detachment
        return {
            'id': admin.id,
            'username': admin.username,
            'password': 'testpassword'
        }

@pytest.fixture(scope='function')
def admin_token(client, admin_user):
    """Get admin authentication token"""
    response = client.post('/admin/login', json={
        'username': admin_user['username'],
        'password': admin_user['password']
    })
    return response.json['token']

@pytest.fixture(scope='function')
def approved_player(app):
    """Create an approved player for testing"""
    with app.app_context():
        player = Player(name='TestPlayer', age=25, weight=180.0, password_hash='', status=PlayerStatus.APPROVED)
        player.set_password('password123')
        db.session.add(player)
        db.session.commit()
        # Return dict to avoid session detachment
        return {
            'id': player.id,
            'name': player.name,
            'age': player.age,
            'weight': player.weight,
            'password': 'password123',
            'status': player.status.value
        }

@pytest.fixture(scope='function')
def pending_player(app):
    """Create a pending player for testing"""
    with app.app_context():
        player = Player(name='PendingPlayer', age=22, weight=170.0, password_hash='', status=PlayerStatus.PENDING)
        player.set_password('password123')
        db.session.add(player)
        db.session.commit()
        # Return dict to avoid session detachment
        return {
            'id': player.id,
            'name': player.name,
            'age': player.age,
            'weight': player.weight,
            'password': 'password123',
            'status': player.status.value
        }

@pytest.fixture(scope='function')
def player_token(client, approved_player):
    """Get player authentication token"""
    response = client.post('/player/login', json={
        'name': approved_player['name'],
        'password': approved_player['password']
    })
    return response.json['token']

@pytest.fixture(scope='function')
def multiple_approved_players(app):
    """Create multiple approved players for testing"""
    with app.app_context():
        players_data = []
        for i in range(1, 4):
            player = Player(
                name=f'Player{i}',
                age=20 + i,
                weight=150.0 + i * 10,
                password_hash='',
                status=PlayerStatus.APPROVED
            )
            player.set_password(f'password{i}')
            db.session.add(player)
            db.session.flush()  # Get IDs without committing
            players_data.append({
                'id': player.id,
                'name': player.name,
                'age': player.age,
                'weight': player.weight,
                'password': f'password{i}',
                'status': player.status.value
            })
        db.session.commit()
        return players_data

@pytest.fixture(scope='function')
def tournament(app, approved_player):
    """Create a tournament for testing"""
    with app.app_context():
        tournament = Tournament(
            name='Test Tournament',
            host_id=approved_player['id'],
            start_time=datetime.now() + timedelta(hours=2)
        )
        db.session.add(tournament)
        db.session.commit()
        # Return dict to avoid session detachment
        return {
            'id': tournament.id,
            'name': tournament.name,
            'host_id': tournament.host_id,
            'start_time': tournament.start_time.isoformat(),
            'status': tournament.status.value
        }

@pytest.fixture(scope='function')
def challenge(app, multiple_approved_players):
    """Create a challenge for testing"""
    with app.app_context():
        players = multiple_approved_players
        challenge = Challenge(
            challenger_id=players[0]['id'],
            challenged_id=players[1]['id'],
            host_id=players[2]['id']
        )
        db.session.add(challenge)
        db.session.commit()
        # Return dict to avoid session detachment
        return {
            'id': challenge.id,
            'challenger_id': challenge.challenger_id,
            'challenged_id': challenge.challenged_id,
            'host_id': challenge.host_id,
            'status': challenge.status.value,
            'expires_at': challenge.expires_at.isoformat()
        }

@pytest.fixture(scope='function')
def pending_match(app, multiple_approved_players):
    """Create a pending match for testing"""
    with app.app_context():
        players = multiple_approved_players
        match = Match(
            player1_id=players[0]['id'],
            player2_id=players[1]['id'],
            host_id=players[2]['id']
        )
        db.session.add(match)
        db.session.commit()
        # Return dict to avoid session detachment
        return {
            'id': match.id,
            'player1_id': match.player1_id,
            'player2_id': match.player2_id,
            'host_id': match.host_id,
            'status': match.status.value
        }