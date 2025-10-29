from flask import request
from models import Admin, AdminSession, Player, PlayerSession
from datetime import datetime

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

def require_player_auth():
    """Check if request has valid player authentication"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    session = PlayerSession.query.filter_by(token=token).first()
    
    if not session or session.expires_at < datetime.now():
        return None
    
    return Player.query.get(session.player_id)

def get_authenticated_user():
    """Get authenticated user (either Admin or Player). Returns (user, user_type) or (None, None)"""
    # Check for admin auth first
    admin = require_admin_auth()
    if admin:
        return admin, 'admin'
    
    # Check for player auth
    player = require_player_auth()
    if player:
        return player, 'player'
    
    return None, None

def authorize_player_action(player_id):
    """
    Authorize that the current user can perform an action for the given player_id.
    Returns (authorized_player, error_response) where:
    - If authorized: (Player object, None)
    - If not authorized: (None, (error_json, status_code))
    """
    from flask import jsonify
    
    user, user_type = get_authenticated_user()
    
    if not user:
        return None, (jsonify({'error': 'Authentication required'}), 401)
    
    # Admins can act on behalf of any player
    if user_type == 'admin':
        player = Player.query.get(player_id)
        if not player:
            return None, (jsonify({'error': 'Player not found'}), 404)
        return player, None
    
    # Players can only act on their own behalf
    if user_type == 'player':
        if user.id != player_id:
            return None, (jsonify({'error': 'You can only perform this action for yourself'}), 403)
        return user, None
    
    return None, (jsonify({'error': 'Authorization failed'}), 403)