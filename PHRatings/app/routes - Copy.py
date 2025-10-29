from flask import Blueprint, request, jsonify
from models import db, Admin, AdminSession, Player, Challenge, Match, Tournament, TournamentParticipant, PlayerStatus, ChallengeStatus, MatchStatus, TournamentStatus
from app.auth import require_admin_auth
from app.services import calculate_elo, cleanup_expired_challenges, cleanup_expired_matches, update_tournament_status
from datetime import datetime, timedelta
from sqlalchemy import text

bp = Blueprint('main', __name__)

# Helper Functions
def require_admin():
    """Require admin authentication or return error"""
    admin = require_admin_auth()
    if not admin:
        return None, (jsonify({'error': 'Admin authentication required'}), 401)
    return admin, None

def require_active_player(player_id):
    """Require player to be active or return error"""
    player = Player.query.filter_by(id=player_id, status=PlayerStatus.APPROVED).first()
    if not player:
        return None, (jsonify({'error': 'Player must be approved and active'}), 400)
    return player, None

def get_winner_loser(winner_id, player1_id, player2_id):
    """Get winner and loser from match participants"""
    winner = Player.query.get(winner_id)
    loser_id = player2_id if winner_id == player1_id else player1_id
    loser = Player.query.get(loser_id)
    return winner, loser

def create_match_response(match, winner, loser, message):
    """Create standardized match response with ELO info"""
    response = {
        'message': message,
        'match_id': match.id,
        'winner_new_elo': winner.elo,
        'loser_new_elo': loser.elo
    }
    if match.notes:
        response['notes'] = match.notes
    if match.video_link:
        response['video_link'] = match.video_link
    return response

def validate_required_fields(data, fields):
    """Validate required fields are present"""
    if not all(data.get(field) for field in fields):
        missing = [f for f in fields if not data.get(f)]
        return False, jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
    return True, None, None

def safe_commit():
    """Safely commit database changes with error handling"""
    try:
        db.session.commit()
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, jsonify({'error': 'Database error occurred'}), 500

# Admin Authentication Endpoints
@bp.route('/admin/register', methods=['POST'])
def register_admin():
    """Create admin account (TODO: should be restricted in production)"""
    data = request.json
    
    valid, error_response, status_code = validate_required_fields(data, ['username', 'password'])
    if not valid:
        return error_response, status_code
    
    username, password = data.get('username'), data.get('password')
    
    if Admin.query.filter_by(username=username).first():
        return jsonify({'error': 'Admin username already exists'}), 400
    
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({'message': 'Admin created successfully'})

@bp.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    
    valid, error_response, status_code = validate_required_fields(data, ['username', 'password'])
    if not valid:
        return error_response, status_code
    
    username, password = data.get('username'), data.get('password')
    
    admin = Admin.query.filter_by(username=username).first()
    if not admin or not admin.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Clean up expired sessions
    AdminSession.query.filter(AdminSession.expires_at < datetime.now()).delete()
    
    # Create new session
    session = AdminSession(admin_id=admin.id)
    db.session.add(session)
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({
        'token': session.token,
        'expires_at': session.expires_at.isoformat()
    })

@bp.route('/admin/logout', methods=['POST'])
def admin_logout():
    admin, error = require_admin()
    if error:
        return error
    
    auth_header = request.headers.get('Authorization')
    if not auth_header or ' ' not in auth_header:
        return jsonify({'error': 'Invalid authorization header'}), 400
    
    try:
        token = auth_header.split(' ')[1]
        session = AdminSession.query.filter_by(token=token).first()
        if session:
            db.session.delete(session)
            safe_commit()
    except (IndexError, AttributeError):
        return jsonify({'error': 'Invalid authorization header format'}), 400
    
    return jsonify({'message': 'Logged out successfully'})

# Player Management Endpoints
@bp.route('/players', methods=['POST'])
def register_player():
    data = request.json
    
    valid, error_response, status_code = validate_required_fields(data, ['name', 'age', 'weight'])
    if not valid:
        return error_response, status_code
    
    name, age, weight = data.get('name'), data.get('age'), data.get('weight')
    
    # Check if name already exists for an active player
    existing_player = Player.query.filter_by(name=name).first()
    if existing_player and existing_player.is_active():
        return jsonify({'error': 'Player name already exists'}), 400
    
    player = Player(name=name, age=age, weight=weight)
    db.session.add(player)
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({
        'id': player.id, 
        'name': player.name, 
        'elo': player.elo,
        'age': player.age,
        'weight': player.weight,
        'status': player.status.value
    })

@bp.route('/admin/players/<int:player_id>/approve', methods=['POST'])
def approve_player(player_id):
    admin, error = require_admin()
    if error:
        return error
    
    player = Player.query.get_or_404(player_id)
    if player.status != PlayerStatus.PENDING:
        return jsonify({'error': 'Player is not pending approval'}), 400
    
    player.status = PlayerStatus.APPROVED
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({'message': 'Player approved'})

@bp.route('/admin/players/<int:player_id>/reject', methods=['POST'])
def reject_player(player_id):
    admin, error = require_admin()
    if error:
        return error
    
    player = Player.query.get_or_404(player_id)
    if player.status != PlayerStatus.PENDING:
        return jsonify({'error': 'Player is not pending approval'}), 400
    
    player.status = PlayerStatus.REJECTED
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({'message': 'Player rejected'})

@bp.route('/admin/players/pending', methods=['GET'])
def list_pending_players():
    admin, error = require_admin()
    if error:
        return error
    
    pending_players = Player.query.filter_by(status=PlayerStatus.PENDING).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'age': p.age,
        'weight': p.weight,
        'registration_date': p.registration_date
    } for p in pending_players])

@bp.route('/players/<int:player_id>/unregister', methods=['POST'])
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
        db.session.delete(participant)  # Fixed: was participant.TournamentParticipant
    
    # Cancel any pending challenges involving this player
    Challenge.query.filter(
        ((Challenge.challenger_id == player_id) | 
         (Challenge.challenged_id == player_id) | 
         (Challenge.host_id == player_id)),
        Challenge.status.in_([ChallengeStatus.PENDING, ChallengeStatus.ACCEPTED])
    ).update({'status': ChallengeStatus.EXPIRED})
    
    # Expire any pending matches where this player is involved
    Match.query.filter(
        ((Match.player1_id == player_id) | 
         (Match.player2_id == player_id) | 
         (Match.host_id == player_id)),
        Match.status == MatchStatus.PENDING
    ).update({'status': MatchStatus.EXPIRED})
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({
        'message': 'Player unregistered successfully',
        'note': 'Match history and rating preserved'
    })

@bp.route('/players/<int:player_id>/weight', methods=['PUT'])
def update_weight(player_id):
    player = Player.query.get_or_404(player_id)
    
    if not player.is_active():
        return jsonify({'error': 'Cannot update weight for unregistered player'}), 400
    
    new_weight = request.json.get('weight')
    if not new_weight:
        return jsonify({'error': 'Weight required'}), 400
    
    player.weight = new_weight
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({'message': 'Weight updated', 'new_weight': player.weight})

# Challenge System
@bp.route('/challenges', methods=['POST'])
def create_challenge():
    cleanup_expired_challenges()
    
    data = request.json
    valid, error_response, status_code = validate_required_fields(data, ['challenger_id', 'challenged_id', 'host_id'])
    if not valid:
        return error_response, status_code
    
    challenger_id, challenged_id, host_id = data.get('challenger_id'), data.get('challenged_id'), data.get('host_id')
    
    if challenger_id == challenged_id:
        return jsonify({'error': 'Cannot challenge yourself'}), 400
    
    # Host must not be one of the players
    if host_id in [challenger_id, challenged_id]:
        return jsonify({'error': 'Host cannot be one of the players'}), 400
    
    # Verify all players exist and are approved (active) - More efficient single query
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
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({
        'challenge_id': challenge.id,
        'expires_at': challenge.expires_at.isoformat()
    })

@bp.route('/challenges/<int:challenge_id>/accept', methods=['POST'])
def accept_challenge(challenge_id):
    cleanup_expired_challenges()
    
    challenge = Challenge.query.get_or_404(challenge_id)
    player_id = request.json.get('player_id')
    
    # Verify player is still active
    player, error = require_active_player(player_id)
    if error:
        return error
    
    if challenge.status != ChallengeStatus.PENDING:
        return jsonify({'error': 'Challenge is no longer pending'}), 400
    
    if datetime.now() > challenge.expires_at:
        challenge.status = ChallengeStatus.EXPIRED
        safe_commit()
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
        
        success, error = safe_commit()
        if not success:
            return error
        
        return jsonify({
            'message': 'Match created',
            'match_id': match.id
        })
    else:
        challenge.status = ChallengeStatus.ACCEPTED
        success, error = safe_commit()
        if not success:
            return error
        
        return jsonify({'message': 'Challenge accepted, waiting for other party'})

# Tournament System
@bp.route('/tournaments', methods=['POST'])
def create_tournament():
    data = request.json
    
    valid, error_response, status_code = validate_required_fields(data, ['name', 'host_id', 'start_time'])
    if not valid:
        return error_response, status_code
    
    name, host_id, start_time_str = data.get('name'), data.get('host_id'), data.get('start_time')
    
    try:
        start_time = datetime.fromisoformat(start_time_str)
    except ValueError:
        return jsonify({'error': 'Invalid start_time format. Use ISO format.'}), 400
    
    if start_time <= datetime.now():
        return jsonify({'error': 'Start time must be in the future'}), 400
    
    host, error = require_active_player(host_id)
    if error:
        return error
    
    tournament = Tournament(name=name, host_id=host_id, start_time=start_time)
    db.session.add(tournament)
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({
        'tournament_id': tournament.id,
        'name': tournament.name,
        'start_time': tournament.start_time.isoformat()
    })

@bp.route('/tournaments/<int:tournament_id>/join', methods=['POST'])
def join_tournament(tournament_id):
    update_tournament_status()
    
    tournament = Tournament.query.get_or_404(tournament_id)
    player_id = request.json.get('player_id')
    
    if tournament.status != TournamentStatus.REGISTRATION_OPEN:
        return jsonify({'error': 'Tournament registration is closed'}), 400
    
    # Tournament host cannot participate in their own tournament
    if player_id == tournament.host_id:
        return jsonify({'error': 'Tournament host cannot participate in their own tournament'}), 400
    
    player, error = require_active_player(player_id)
    if error:
        return error
    
    # Check if already joined
    existing = TournamentParticipant.query.filter_by(
        tournament_id=tournament_id,
        player_id=player_id
    ).first()
    
    if existing:
        return jsonify({'error': 'Player already joined tournament'}), 400
    
    participant = TournamentParticipant(tournament_id=tournament_id, player_id=player_id)
    db.session.add(participant)
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({'message': 'Successfully joined tournament'})

@bp.route('/tournaments/<int:tournament_id>/leave', methods=['DELETE'])
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
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({'message': 'Successfully left tournament'})

@bp.route('/tournaments/<int:tournament_id>/record-match', methods=['POST'])
def record_tournament_match(tournament_id):
    """Host records a match result between any two tournament participants"""
    update_tournament_status()
    
    tournament = Tournament.query.get_or_404(tournament_id)
    data = request.json
    
    valid, error_response, status_code = validate_required_fields(data, ['host_id', 'player1_id', 'player2_id', 'winner_id'])
    if not valid:
        return error_response, status_code
    
    host_id, player1_id, player2_id, winner_id = data.get('host_id'), data.get('player1_id'), data.get('player2_id'), data.get('winner_id')
    notes, video_link = data.get('notes'), data.get('video_link')
    
    # Verify host is the tournament host
    if host_id != tournament.host_id:
        return jsonify({'error': 'Only the tournament host can record results'}), 400
    
    # Verify host is still active
    host, error = require_active_player(host_id)
    if error:
        return error
    
    # Verify tournament is active
    if tournament.status != TournamentStatus.ACTIVE:
        return jsonify({'error': 'Tournament is not active'}), 400
    
    # Check if tournament has expired
    if datetime.now() > tournament.expires_at:
        tournament.status = TournamentStatus.EXPIRED
        safe_commit()
        return jsonify({'error': 'Tournament has expired'}), 400
    
    if player1_id == player2_id:
        return jsonify({'error': 'Players must be different'}), 400
    
    if winner_id not in [player1_id, player2_id]:
        return jsonify({'error': 'Winner must be one of the two players'}), 400
    
    # Verify both players are tournament participants - Single query optimization
    participants = TournamentParticipant.query.filter(
        TournamentParticipant.tournament_id == tournament_id,
        TournamentParticipant.player_id.in_([player1_id, player2_id])
    ).count()
    
    if participants != 2:
        return jsonify({'error': 'Both players must be tournament participants'}), 400
    
    # Get players for ELO calculation
    winner, loser = get_winner_loser(winner_id, player1_id, player2_id)
    
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
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify(create_match_response(match, winner, loser, 'Tournament match result recorded'))

@bp.route('/tournaments/<int:tournament_id>/participants', methods=['GET'])
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
@bp.route('/matches/<int:match_id>/result', methods=['POST'])
def record_match_result(match_id):
    cleanup_expired_matches()
    
    match = Match.query.get_or_404(match_id)
    data = request.json
    
    valid, error_response, status_code = validate_required_fields(data, ['host_id', 'winner_id'])
    if not valid:
        return error_response, status_code
    
    host_id, winner_id = data.get('host_id'), data.get('winner_id')
    notes, video_link = data.get('notes'), data.get('video_link')
    
    if match.host_id != host_id:
        return jsonify({'error': 'Only the match host can record results'}), 400
    
    # Verify host is still active
    host, error = require_active_player(host_id)
    if error:
        return error
    
    if match.status != MatchStatus.PENDING:
        return jsonify({'error': 'Match is not pending'}), 400
    
    # Check expiration only if expires_at is set
    if match.expires_at and datetime.now() > match.expires_at:
        match.status = MatchStatus.EXPIRED
        safe_commit()
        return jsonify({'error': 'Match has expired'}), 400
    
    if winner_id not in [match.player1_id, match.player2_id]:
        return jsonify({'error': 'Winner must be one of the match players'}), 400
    
    # Get players for ELO calculation
    winner, loser = get_winner_loser(winner_id, match.player1_id, match.player2_id)
    
    # Calculate ELO change
    elo_change = calculate_elo(winner, loser)
    
    # Update match with result and optional fields
    match.winner_id = winner_id
    match.status = MatchStatus.COMPLETED
    match.completed_at = datetime.now()
    match.notes = notes
    match.video_link = video_link
    match.elo_change = elo_change
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify(create_match_response(match, winner, loser, 'Match result recorded'))

@bp.route('/matches/undo', methods=['POST'])
def undo_last_match():
    """Undo the last match recorded by a host"""
    host_id = request.json.get('host_id')
    if not host_id:
        return jsonify({'error': 'Host ID required'}), 400
        
    # Verify host is an active player
    host, error = require_active_player(host_id)
    if error:
        return error
    
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
    winner, loser = get_winner_loser(last_match.winner_id, last_match.player1_id, last_match.player2_id)
    
    winner.elo -= last_match.elo_change
    loser.elo += last_match.elo_change
    
    # Update match status
    last_match.status = MatchStatus.UNDONE
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({
        'message': 'Last match undone successfully',
        'match_id': last_match.id,
        'winner_reverted_elo': winner.elo,
        'loser_reverted_elo': loser.elo
    })

# Legacy/Backwards Compatibility
@bp.route('/matches', methods=['POST'])
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
    
    success, error = safe_commit()
    if not success:
        return error
    
    return jsonify({'match_id': match.id})

# Listing Endpoints
@bp.route('/matches', methods=['GET'])
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

@bp.route('/players', methods=['GET'])
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

@bp.route('/tournaments', methods=['GET'])
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

@bp.route('/challenges', methods=['GET'])
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

@bp.route('/sql', methods=['POST'])
def run_sql():
    query = request.json.get('query')
    result = db.session.execute(text(query))
    return jsonify([dict(row) for row in result])