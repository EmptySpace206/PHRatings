from models import db, Player, Challenge, Match, Tournament, ChallengeStatus, MatchStatus, TournamentStatus
from datetime import datetime

def calculate_elo(winner, loser, k=32):
    """
    Calculate and apply Elo rating changes based on match result.
    Uses the standard Elo rating system (as used in Chess).
    
    Formula:
    - Expected score: E = 1 / (1 + 10^((opponent_rating - player_rating) / 400))
    - Rating change: ΔR = K × (actual_score - expected_score)
    
    Args:
        winner: Player object who won the match
        loser: Player object who lost the match
        k: K-factor (default 32, standard for active chess players)
    
    Returns:
        elo_change: The rating points transferred from loser to winner
    """
    # Calculate winner's expected score (probability of winning)
    expected_win = 1 / (1 + 10 ** ((loser.elo - winner.elo) / 400))
    
    # Calculate rating change for winner (actual_score = 1 for win)
    elo_change = k * (1 - expected_win)
    
    # Update ratings (zero-sum: winner gains what loser loses)
    winner.elo += elo_change
    loser.elo -= elo_change
    
    return elo_change

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
        Match.expires_at != None,  # Only check matches with expiration
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