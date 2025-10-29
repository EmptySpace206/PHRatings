from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///elo.db'
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change in production
db = SQLAlchemy(app)

# Enums
class PlayerStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNREGISTERED = "unregistered"

class ChallengeStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    MATCH_CREATED = "match_created"

class MatchStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    UNDONE = "undone"

class TournamentStatus(Enum):
    REGISTRATION_OPEN = "registration_open"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"

# Models
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

class AdminSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __init__(self, admin_id, **kwargs):
        super().__init__(**kwargs)
        self.admin_id = admin_id
        self.token = secrets.token_urlsafe(32)
        self.expires_at = datetime.now() + timedelta(hours=24)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    elo = db.Column(db.Float, default=1200)
    age = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(PlayerStatus), default=PlayerStatus.PENDING)
    registration_date = db.Column(db.DateTime, server_default=db.func.now())
    unregistration_date = db.Column(db.DateTime)

    def get_current_age(self):
        return self.age + int((datetime.now() - self.registration_date).days / 365.25)

    def is_active(self):
        return self.status in [PlayerStatus.PENDING, PlayerStatus.APPROVED]

class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    challenger_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    challenged_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    status = db.Column(db.Enum(ChallengeStatus), default=ChallengeStatus.PENDING)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    challenged_accepted_at = db.Column(db.DateTime)
    host_accepted_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expires_at = datetime.now() + timedelta(minutes=10)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player1_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    host_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'))
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'))
    status = db.Column(db.Enum(MatchStatus), default=MatchStatus.PENDING)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    video_link = db.Column(db.String(500))
    elo_change = db.Column(db.Float)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'expires_at' not in kwargs:
            self.expires_at = datetime.now() + timedelta(hours=24)

class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(TournamentStatus), default=TournamentStatus.REGISTRATION_OPEN)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    expires_at = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expires_at = self.start_time + timedelta(hours=24)

class TournamentParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    joined_at = db.Column(db.DateTime, server_default=db.func.now())

# Elo calculation
def calculate_elo(winner, loser, k=32):
    expected_win = 1 / (1 + 10 ** ((loser.elo - winner.elo) / 400))
    elo_change = k * (1 - expected_win)
    winner.elo += elo_change
    loser.elo -= elo_change
    return elo_change

# Authentication helpers
def require_admin_auth():
    """Check if request has valid admin authentication"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    session = AdminSession.query.filter_by(token=token).first()
    
    if not session or session.expires_at < datetime.now():
        return None
    
    return Admin.query.get(session.admin_id)

# Helper functions
def cleanup_expired_challenges():
    expired_challenges = Challenge.query.filter(
        Challenge.expires_at < datetime.now(),
        Challenge.status == ChallengeStatus.PENDING
    ).all()
    for challenge in expired_challenges:
        challenge.status = ChallengeStatus.EXPIRED
    db.session.commit()

def cleanup_expired_matches():
    expired_matches = Match.query.filter(
        Match.expires_at < datetime.now(),
        Match.status == MatchStatus.PENDING
    ).all()
    for match in expired_matches:
        match.status = MatchStatus.EXPIRED
    db.session.commit()

def update_tournament_status():
    # Start tournaments
    tournaments_to_start = Tournament.query.filter(
        Tournament.start_time <= datetime.now(),
        Tournament.status == TournamentStatus.REGISTRATION_OPEN
    ).all()
    for tournament in tournaments_to_start:
        tournament.status = TournamentStatus.ACTIVE

    # Expire tournaments
    expired_tournaments = Tournament.query.filter(
        Tournament.expires_at < datetime.now(),
        Tournament.status == TournamentStatus.ACTIVE
    ).all()
    for tournament in expired_tournaments:
        tournament.status = TournamentStatus.EXPIRED

    db.session.commit()

# Admin Authentication Endpoints

@app.route('/admin/register', methods=['POST'])
def register_admin():
    """Create admin account (should be restricted in production)"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'error': 'Username and password required'}), 400
    
    if Admin.query.filter_by(username=username).first():
        return jsonify({'error': 'Admin username already exists'}), 400
    
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    
    return jsonify({'message': 'Admin created successfully'})

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not all([username, password]):
        return jsonify({'error': 'Username and password required'}), 400
    
    admin = Admin.query.filter_by(username=username).first()
    if not admin or not admin.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Clean up expired sessions
    AdminSession.query.filter(AdminSession.expires_at < datetime.now()).delete()
    
    # Create new session
    session = AdminSession(admin_id=admin.id)
    db.session.add(session)
    db.session.commit()
    
    return jsonify({
        'token': session.token,
        'expires_at': session.expires_at.isoformat()
    })

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    admin = require_admin_auth()
    if not admin:
        return jsonify({'error': 'Authentication required'}), 401
    
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(' ')[1]
    session = AdminSession.query.filter_by(token=token).first()
    if session:
        db.session.delete(session)
        db.session.commit()
    
    return jsonify({'message': 'Logged out successfully'})

# Player Management Endpoints

@app.route('/players', methods=['POST'])
def register_player():
    data = request.json
    name = data.get('name')
    age = data.get('age')
    weight = data.get('weight')
    
    if not all([name, age, weight]):
        return jsonify({'error': 'Name, age, and weight required'}), 400
    
    # Check if name already exists for an active player
    existing_player = Player.query.filter_by(name=name).first()
    if existing_player and existing_player.is_active():
        return jsonify({'error': 'Player name already exists'}), 400
    
    player = Player(name=name, age=age, weight=weight)
    db.session.add(player)
    db.session.commit()
    return jsonify({
        'id': player.id, 
        'name': player.name, 
        'elo': player.elo,
        'age': player.age,
        'weight': player.weight,
        'status': player.status.value
    })

@app.route('/admin/players/<int:player_id>/approve', methods=['POST'])
def approve_player(player_id):
    admin = require_admin_auth()
    if not admin:
        return jsonify({'error': 'Admin authentication required'}), 401
    
    player = Player.query.get_or_404(player_id)
    if player.status != PlayerStatus.PENDING:
        return jsonify({'error': 'Player is not pending approval'}), 400
    
    player.status = PlayerStatus.APPROVED
    db.session.commit()
    return jsonify({'message': 'Player approved'})

@app.route('/admin/players/<int:player_id>/reject', methods=['POST'])
def reject_player(player_id):
    admin = require_admin_auth()
    if not admin:
        return jsonify({'error': 'Admin authentication required'}), 401
    
    player = Player.query.get_or_404(player_id)
    if player.status != PlayerStatus.PENDING:
        return jsonify({'error': 'Player is not pending approval'}), 400
    
    player.status = PlayerStatus.REJECTED
    db.session.commit()
    return jsonify({'message': 'Player rejected'})

@app.route('/admin/players/pending', methods=['GET'])
def list_pending_players():
    admin = require_admin_auth()
    if not admin:
        return jsonify({'error': 'Admin authentication required'}), 401
    
    pending_players = Player.query.filter_by(status=PlayerStatus.PENDING).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'age': p.age,
        'weight': p.weight,
        'registration_date': p.registration_date
    } for p in pending_players])

@app.route('/players/<int:player_id>/unregister', methods=['POST'])
def unregister_player(player_id):
    player = Player.query.get_or_404(player_id)
    
    if not player.is_active():
        return jsonify({'error': 'Player is not currently registered'}), 400
    
    # Set player status to unregistered
    player.status = PlayerStatus.UNREGISTERED
    player.unregistration_date = datetime.now()
    
    # Remove player from any pending tournaments they're registered for
    pending_tournaments = db.session.query(TournamentParticipant, Tournament).join(
        Tournament, TournamentParticipant.tournament_id == Tournament.id
    ).filter(
        TournamentParticipant.player_id == player_id,
        Tournament.status == TournamentStatus.REGISTRATION_OPEN
    ).all()
    
    for participant, tournament in pending_tournaments:
        db.session.delete(participant.TournamentParticipant)
    
    # Cancel any pending challenges involving this player
    pending_challenges = Challenge.query.filter(
        ((Challenge.challenger_id == player_id) | 
         (Challenge.challenged_id == player_id) | 
         (Challenge.host_id == player_id)),
        Challenge.status.in_([ChallengeStatus.PENDING, ChallengeStatus.ACCEPTED])
    ).all()
    
    for challenge in pending_challenges:
        challenge.status = ChallengeStatus.EXPIRED
    
    # Expire any pending matches where this player is involved
    pending_matches = Match.query.filter(
        ((Match.player1_id == player_id) | 
         (Match.player2_id == player_id) | 
         (Match.host_id == player_id)),
        Match.status == MatchStatus.PENDING
    ).all()
    
    for match in pending_matches:
        match.status = MatchStatus.EXPIRED
    
    db.session.commit()
    
    return jsonify({
        'message': 'Player unregistered successfully',
        'note': 'Match history and rating preserved'
    })

@app.route('/players/<int:player_id>/weight', methods=['PUT'])
def update_weight(player_id):
    player = Player.query.get_or_404(player_id)
    
    if not player.is_active():
        return jsonify({'error': 'Cannot update weight for unregistered player'}), 400
    
    new_weight = request.json.get('weight')
    if not new_weight:
        return jsonify({'error': 'Weight required'}), 400
    
    player.weight = new_weight
    db.session.commit()
    return jsonify({'message': 'Weight updated', 'new_weight': player.weight})

# Challenge System

@app.route('/challenges', methods=['POST'])
def create_challenge():
    cleanup_expired_challenges()
    
    data = request.json
    challenger_id = data.get('challenger_id')
    challenged_id = data.get('challenged_id')
    host_id = data.get('host_id')
    
    if not all([challenger_id, challenged_id, host_id]):
        return jsonify({'error': 'Challenger, challenged, and host IDs required'}), 400
    
    if challenger_id == challenged_id:
        return jsonify({'error': 'Cannot challenge yourself'}), 400
    
    # Host must not be one of the players
    if host_id in [challenger_id, challenged_id]:
        return jsonify({'error': 'Host cannot be one of the players'}), 400
    
    # Verify all players exist and are approved (active)
    players = Player.query.filter(
        Player.id.in_([challenger_id, challenged_id, host_id]),
        Player.status == PlayerStatus.APPROVED
    ).all()
    
    if len(players) != 3:
        return jsonify({'error': 'All players must exist and be approved'}), 400
    
    challenge = Challenge(
        challenger_id=challenger_id,
        challenged_id=challenged_id,
        host_id=host_id
    )
    db.session.add(challenge)
    db.session.commit()
    
    return jsonify({
        'challenge_id': challenge.id,
        'expires_at': challenge.expires_at.isoformat()
    })

@app.route('/challenges/<int:challenge_id>/accept', methods=['POST'])
def accept_challenge(challenge_id):
    cleanup_expired_challenges()
    
    challenge = Challenge.query.get_or_404(challenge_id)
    player_id = request.json.get('player_id')
    
    # Verify player is still active
    player = Player.query.filter_by(id=player_id, status=PlayerStatus.APPROVED).first()
    if not player:
        return jsonify({'error': 'Player must be approved and active'}), 400
    
    if challenge.status != ChallengeStatus.PENDING:
        return jsonify({'error': 'Challenge is no longer pending'}), 400
    
    if datetime.now() > challenge.expires_at:
        challenge.status = ChallengeStatus.EXPIRED
        db.session.commit()
        return jsonify({'error': 'Challenge has expired'}), 400
    
    if player_id == challenge.challenged_id:
        challenge.challenged_accepted_at = datetime.now()
    elif player_id == challenge.host_id:
        challenge.host_accepted_at = datetime.now()
    else:
        return jsonify({'error': 'Only the challenged player or host can accept'}), 400
    
    # Check if both have accepted
    if challenge.challenged_accepted_at and challenge.host_accepted_at:
        challenge.status = ChallengeStatus.MATCH_CREATED
        
        # Create the match with a 24-hour expiration for the host to log the result
        match = Match(
            player1_id=challenge.challenger_id,
            player2_id=challenge.challenged_id,
            host_id=challenge.host_id,
            challenge_id=challenge.id
        )
        db.session.add(match)
        db.session.commit()
        
        return jsonify({
            'message': 'Match created',
            'match_id': match.id
        })
    else:
        challenge.status = ChallengeStatus.ACCEPTED
        db.session.commit()
        return jsonify({'message': 'Challenge accepted, waiting for other party'})

# Tournament System

@app.route('/tournaments', methods=['POST'])
def create_tournament():
    data = request.json
    name = data.get('name')
    host_id = data.get('host_id')
    start_time_str = data.get('start_time')
    
    if not all([name, host_id, start_time_str]):
        return jsonify({'error': 'Name, host_id, and start_time required'}), 400
    
    try:
        start_time = datetime.fromisoformat(start_time_str)
    except ValueError:
        return jsonify({'error': 'Invalid start_time format. Use ISO format.'}), 400
    
    if start_time <= datetime.now():
        return jsonify({'error': 'Start time must be in the future'}), 400
    
    host = Player.query.filter_by(id=host_id, status=PlayerStatus.APPROVED).first()
    if not host:
        return jsonify({'error': 'Host must be an approved and active player'}), 400
    
    tournament = Tournament(name=name, host_id=host_id, start_time=start_time)
    db.session.add(tournament)
    db.session.commit()
    
    return jsonify({
        'tournament_id': tournament.id,
        'name': tournament.name,
        'start_time': tournament.start_time.isoformat()
    })

@app.route('/tournaments/<int:tournament_id>/join', methods=['POST'])
def join_tournament(tournament_id):
    update_tournament_status()
    
    tournament = Tournament.query.get_or_404(tournament_id)
    player_id = request.json.get('player_id')
    
    if tournament.status != TournamentStatus.REGISTRATION_OPEN:
        return jsonify({'error': 'Tournament registration is closed'}), 400
    
    # Tournament host cannot participate in their own tournament
    if player_id == tournament.host_id:
        return jsonify({'error': 'Tournament host cannot participate in their own tournament'}), 400
    
    player = Player.query.filter_by(id=player_id, status=PlayerStatus.APPROVED).first()
    if not player:
        return jsonify({'error': 'Player must be approved and active'}), 400
    
    # Check if already joined
    existing = TournamentParticipant.query.filter_by(
        tournament_id=tournament_id,
        player_id=player_id
    ).first()
    
    if existing:
        return jsonify({'error': 'Player already joined tournament'}), 400
    
    participant = TournamentParticipant(tournament_id=tournament_id, player_id=player_id)
    db.session.add(participant)
    db.session.commit()
    
    return jsonify({'message': 'Successfully joined tournament'})

@app.route('/tournaments/<int:tournament_id>/leave', methods=['DELETE'])
def leave_tournament(tournament_id):
    update_tournament_status()
    
    tournament = Tournament.query.get_or_404(tournament_id)
    player_id = request.json.get('player_id')
    
    if not player_id:
        return jsonify({'error': 'Player ID required'}), 400
    
    if tournament.status != TournamentStatus.REGISTRATION_OPEN:
        return jsonify({'error': 'Cannot leave tournament after registration closes'}), 400
    
    # Find the participant record
    participant = TournamentParticipant.query.filter_by(
        tournament_id=tournament_id,
        player_id=player_id
    ).first()
    
    if not participant:
        return jsonify({'error': 'Player is not registered for this tournament'}), 400
    
    # Remove the participant
    db.session.delete(participant)
    db.session.commit()
    
    return jsonify({'message': 'Successfully left tournament'})

@app.route('/tournaments/<int:tournament_id>/record-match', methods=['POST'])
def record_tournament_match(tournament_id):
    """Host records a match result between any two tournament participants"""
    update_tournament_status()
    
    tournament = Tournament.query.get_or_404(tournament_id)
    data = request.json
    
    host_id = data.get('host_id')
    player1_id = data.get('player1_id')
    player2_id = data.get('player2_id')
    winner_id = data.get('winner_id')
    notes = data.get('notes')
    video_link = data.get('video_link')
    
    if not all([host_id, player1_id, player2_id, winner_id]):
        return jsonify({'error': 'Host ID, both player IDs, and winner ID required'}), 400
    
    # Verify host is the tournament host
    if host_id != tournament.host_id:
        return jsonify({'error': 'Only the tournament host can record results'}), 400
    
    # Verify host is still active
    host = Player.query.filter_by(id=host_id, status=PlayerStatus.APPROVED).first()
    if not host:
        return jsonify({'error': 'Host must be approved and active'}), 400
    
    # Verify tournament is active
    if tournament.status != TournamentStatus.ACTIVE:
        return jsonify({'error': 'Tournament is not active'}), 400
    
    # Check if tournament has expired
    if datetime.now() > tournament.expires_at:
        tournament.status = TournamentStatus.EXPIRED
        db.session.commit()
        return jsonify({'error': 'Tournament has expired'}), 400
    
    if player1_id == player2_id:
        return jsonify({'error': 'Players must be different'}), 400
    
    if winner_id not in [player1_id, player2_id]:
        return jsonify({'error': 'Winner must be one of the two players'}), 400
    
    # Verify both players are tournament participants
    participant1 = TournamentParticipant.query.filter_by(
        tournament_id=tournament_id, player_id=player1_id
    ).first()
    participant2 = TournamentParticipant.query.filter_by(
        tournament_id=tournament_id, player_id=player2_id
    ).first()
    
    if not (participant1 and participant2):
        return jsonify({'error': 'Both players must be tournament participants'}), 400
    
    # Get players for ELO calculation
    winner = Player.query.get(winner_id)
    loser_id = player2_id if winner_id == player1_id else player1_id
    loser = Player.query.get(loser_id)
    
    # Calculate ELO change
    elo_change = calculate_elo(winner, loser)
    
    # Create and complete the match immediately
    match = Match(
        player1_id=player1_id,
        player2_id=player2_id,
        winner_id=winner_id,
        host_id=host_id,
        tournament_id=tournament_id,
        status=MatchStatus.COMPLETED,
        completed_at=datetime.now(),
        notes=notes,
        video_link=video_link,
        elo_change=elo_change,
        expires_at=None
    )
    
    db.session.add(match)
    db.session.commit()
    
    response_data = {
        'message': 'Tournament match result recorded',
        'match_id': match.id,
        'winner_new_elo': winner.elo,
        'loser_new_elo': loser.elo
    }
    
    if notes:
        response_data['notes'] = notes
    if video_link:
        response_data['video_link'] = video_link
    
    return jsonify(response_data)

@app.route('/tournaments/<int:tournament_id>/participants', methods=['GET'])
def get_tournament_participants(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    
    participants = db.session.query(TournamentParticipant, Player).join(
        Player, TournamentParticipant.player_id == Player.id
    ).filter(TournamentParticipant.tournament_id == tournament_id).all()
    
    return jsonify([{
        'player_id': participant.Player.id,
        'player_name': participant.Player.name,
        'player_elo': participant.Player.elo,
        'player_status': participant.Player.status.value,
        'joined_at': participant.TournamentParticipant.joined_at
    } for participant in participants])

# Match Result Recording

@app.route('/matches/<int:match_id>/result', methods=['POST'])
def record_match_result(match_id):
    cleanup_expired_matches()
    
    match = Match.query.get_or_404(match_id)
    data = request.json
    host_id = data.get('host_id')
    winner_id = data.get('winner_id')
    notes = data.get('notes')
    video_link = data.get('video_link')
    
    if not all([host_id, winner_id]):
        return jsonify({'error': 'Host ID and winner ID required'}), 400
    
    if match.host_id != host_id:
        return jsonify({'error': 'Only the match host can record results'}), 400
    
    # Verify host is still active
    host = Player.query.filter_by(id=host_id, status=PlayerStatus.APPROVED).first()
    if not host:
        return jsonify({'error': 'Host must be approved and active'}), 400
    
    if match.status != MatchStatus.PENDING:
        return jsonify({'error': 'Match is not pending'}), 400
    
    # Check expiration only if expires_at is set
    if match.expires_at and datetime.now() > match.expires_at:
        match.status = MatchStatus.EXPIRED
        db.session.commit()
        return jsonify({'error': 'Match has expired'}), 400
    
    if winner_id not in [match.player1_id, match.player2_id]:
        return jsonify({'error': 'Winner must be one of the match players'}), 400
    
    # Get players for ELO calculation
    winner = Player.query.get(winner_id)
    loser_id = match.player2_id if winner_id == match.player1_id else match.player1_id
    loser = Player.query.get(loser_id)
    
    # Calculate ELO change
    elo_change = calculate_elo(winner, loser)
    
    # Update match with result and optional fields
    match.winner_id = winner_id
    match.status = MatchStatus.COMPLETED
    match.completed_at = datetime.now()
    match.notes = notes
    match.video_link = video_link
    match.elo_change = elo_change
    
    db.session.commit()
    
    response_data = {
        'message': 'Match result recorded',
        'winner_new_elo': winner.elo,
        'loser_new_elo': loser.elo
    }
    
    if notes:
        response_data['notes'] = notes
    if video_link:
        response_data['video_link'] = video_link
    
    return jsonify(response_data)

@app.route('/matches/undo', methods=['POST'])
def undo_last_match():
    """Undo the last match recorded by a host"""
    host_id = request.json.get('host_id')
    if not host_id:
        return jsonify({'error': 'Host ID required'}), 400
        
    # Verify host is an active player
    host = Player.query.filter_by(id=host_id, status=PlayerStatus.APPROVED).first()
    if not host:
        return jsonify({'error': 'Host must be an approved and active player'}), 400
    
    # Find the last completed match recorded by this host
    last_match = Match.query.filter_by(
        host_id=host_id,
        status=MatchStatus.COMPLETED
    ).order_by(Match.completed_at.desc()).first()
    
    if not last_match:
        return jsonify({'error': 'No completed match found for this host to undo'}), 404
    
    # Check if the match was completed within the last 10 minutes
    if datetime.now() > last_match.completed_at + timedelta(minutes=10):
        return jsonify({'error': 'Undo time limit (10 minutes) has passed'}), 403
    
    # Revert ELO changes
    winner = Player.query.get(last_match.winner_id)
    loser_id = last_match.player2_id if last_match.winner_id == last_match.player1_id else last_match.player1_id
    loser = Player.query.get(loser_id)
    
    winner.elo -= last_match.elo_change
    loser.elo += last_match.elo_change
    
    # Update match status
    last_match.status = MatchStatus.UNDONE
    
    db.session.commit()
    
    return jsonify({
        'message': 'Last match undone successfully',
        'match_id': last_match.id,
        'winner_reverted_elo': winner.elo,
        'loser_reverted_elo': loser.elo
    })

# Legacy/Backwards Compatibility

@app.route('/matches', methods=['POST'])
def record_match():
    # Keep original endpoint for backwards compatibility
    data = request.json

    # Resolve player 1
    p1 = None
    if 'player1_id' in data:
        p1 = Player.query.get(data['player1_id'])
    elif 'player1_name' in data:
        p1 = Player.query.filter_by(name=data['player1_name']).first()

    # Resolve player 2
    p2 = None
    if 'player2_id' in data:
        p2 = Player.query.get(data['player2_id'])
    elif 'player2_name' in data:
        p2 = Player.query.filter_by(name=data['player2_name']).first()

    # Resolve winner
    winner = None
    if 'winner_id' in data:
        winner = Player.query.get(data['winner_id'])
    elif 'winner_name' in data:
        winner = Player.query.filter_by(name=data['winner_name']).first()

    if not all([p1, p2, winner]):
        return jsonify({'error': 'Invalid player identifiers'}), 400

    # Ensure player1 and player2 are not the same player, and the winner is one of them.
    if p1.id == p2.id:
        return jsonify({'error': 'player1 and player2 must be different players'}), 400
    if winner.id not in [p1.id, p2.id]:
        return jsonify({'error': 'Winner must be one of the input players'}), 400

    # Get optional fields
    notes = data.get('notes')
    video_link = data.get('video_link')

    # Create a new match and update Elo
    loser = p2 if winner.id == p1.id else p1
    elo_change = calculate_elo(winner, loser)
    match = Match(
        player1_id=p1.id, 
        player2_id=p2.id, 
        winner_id=winner.id,
        host_id=winner.id,  # Default to winner as host for backwards compatibility
        status=MatchStatus.COMPLETED,
        completed_at=datetime.now(),
        notes=notes,
        video_link=video_link,
        elo_change=elo_change,
        expires_at=None
    )
    db.session.add(match)
    db.session.commit()
    return jsonify({'match_id': match.id})

# Listing Endpoints

@app.route('/matches', methods=['GET'])
def list_matches():
    player_id = request.args.get('player_id')
    tournament_id = request.args.get('tournament_id')
    
    query = Match.query
    if player_id:
        query = query.filter((Match.player1_id == player_id) | (Match.player2_id == player_id))
    if tournament_id:
        query = query.filter(Match.tournament_id == tournament_id)
    
    matches = query.all()
    return jsonify([{
        'id': m.id,
        'player1_id': m.player1_id,
        'player2_id': m.player2_id,
        'winner_id': m.winner_id,
        'host_id': m.host_id,
        'tournament_id': m.tournament_id,
        'challenge_id': m.challenge_id,
        'status': m.status.value,
        'created_at': m.created_at,
        'completed_at': m.completed_at,
        'notes': m.notes,
        'video_link': m.video_link
    } for m in matches])

@app.route('/players', methods=['GET'])
def list_players():
    # By default, only show active players
    include_unregistered = request.args.get('include_unregistered', 'false').lower() == 'true'
    
    if include_unregistered:
        players = Player.query.all()
    else:
        players = Player.query.filter(Player.status != PlayerStatus.UNREGISTERED).all()
    
    return jsonify([{
        'id': p.id, 
        'name': p.name, 
        'elo': p.elo,
        'age': p.age,
        'current_age': p.get_current_age(),
        'weight': p.weight,
        'status': p.status.value,
        'unregistration_date': p.unregistration_date
    } for p in players])

@app.route('/tournaments', methods=['GET'])
def list_tournaments():
    update_tournament_status()
    tournaments = Tournament.query.all()
    result = []
    for t in tournaments:
        participants = TournamentParticipant.query.filter_by(tournament_id=t.id).all()
        result.append({
            'id': t.id,
            'name': t.name,
            'host_id': t.host_id,
            'start_time': t.start_time,
            'status': t.status.value,
            'participant_count': len(participants)
        })
    return jsonify(result)

@app.route('/challenges', methods=['GET'])
def list_challenges():
    cleanup_expired_challenges()
    challenges = Challenge.query.all()
    return jsonify([{
        'id': c.id,
        'challenger_id': c.challenger_id,
        'challenged_id': c.challenged_id,
        'host_id': c.host_id,
        'status': c.status.value,
        'created_at': c.created_at,
        'expires_at': c.expires_at
    } for c in challenges])

@app.route('/sql', methods=['POST'])
def run_sql():
    query = request.json.get('query')
    result = db.session.execute(text(query))
    return jsonify([dict(row) for row in result])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default admin if none exists
        if not Admin.query.first():
            default_admin = Admin(username='admin')
            default_admin.set_password('admin123')  # Change this in production!
            db.session.add(default_admin)
            db.session.commit()
            print("Default admin created: username='admin', password='admin123'")
    
    app.run(debug=True)