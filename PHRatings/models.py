from app import db
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets

# Constants
CHALLENGE_TIMEOUT_MINUTES = 10
MATCH_TIMEOUT_HOURS = 8
TOURNAMENT_TIMEOUT_HOURS = 24
ADMIN_SESSION_TIMEOUT_HOURS = 24
PLAYER_SESSION_TIMEOUT_HOURS = 24

# Enums
class PlayerStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"

class ChallengeStatus(Enum):
    PENDING = "pending"
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
        self.expires_at = datetime.now() + timedelta(hours=ADMIN_SESSION_TIMEOUT_HOURS)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    elo = db.Column(db.Float, default=1200)
    age = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(PlayerStatus), default=PlayerStatus.PENDING)
    registration_date = db.Column(db.DateTime, server_default=db.func.now())

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    def get_current_age(self):
        return self.age + int((datetime.now() - self.registration_date).days / 365.25)

    def is_active(self):
        return self.status == PlayerStatus.APPROVED

class PlayerSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __init__(self, player_id, **kwargs):
        super().__init__(**kwargs)
        self.player_id = player_id
        self.token = secrets.token_urlsafe(32)
        self.expires_at = datetime.now() + timedelta(hours=PLAYER_SESSION_TIMEOUT_HOURS)

class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    challenger_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    challenged_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    status = db.Column(db.Enum(ChallengeStatus), default=ChallengeStatus.PENDING)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    accepted_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expires_at = datetime.now() + timedelta(minutes=CHALLENGE_TIMEOUT_MINUTES)

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
    elo_change = db.Column(db.Float)
    notes = db.Column(db.Text)
    video_link = db.Column(db.String(255))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'expires_at' not in kwargs:
            self.expires_at = datetime.now() + timedelta(hours=MATCH_TIMEOUT_HOURS)

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
        self.expires_at = self.start_time + timedelta(hours=TOURNAMENT_TIMEOUT_HOURS)

class TournamentParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    joined_at = db.Column(db.DateTime, server_default=db.func.now())