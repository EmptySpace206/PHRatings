# PHRatings
This is a general purpose ELO rating system, initialy built for Push Hands. This rating system is identical to that used in Chess.

It's goal is to enable rated matches among the player pool, both within tournaments, and outside tournaments. 

Currently, a production server, and client app, haven't yet been built.

## Main Features 
Anyone can request to join as a player, providing age and weight. Admin approval is required. 

### A player can challenge any other player to a match. 
1. A second player, and a judge, are named. The judge can be any player besides the two players. 
2. The named player accepts -> match created. The challenge expires after 10 minutes, if no accept.
3. The judge can log a winner for the match, within 8 hours. The elo gets adjusted for both players. The match details are stored with optional notes, and video link.

### Player's can host and participate in tournaments.
* A tournament name is given, and a start time is set. It lasts 24 hours once started. 
* Players can join until it starts. Players can also leave.
* The host can log match results between any two players in the tournament until it ends. The player's dont need to specifically 'challenge' each other. 
* Tournament matches are identical to non-tournament matches.
* There is no bracket system. This is a convenience feature to streamline match results during a tournament.

### Future iteration
* Auto match scheduling in tournaments based on current elo ratings, or weight\age class. 
* To be a judge\host requires admin certification, beyond just being a player?
* Leagues -- containers for a player pool, and elo ratings. Currently, separate DB instances can be used for leagues. 
* Authentication besides PW (at least for admin account).
* Remove certain objects from DB once they are no longer needed? Accepted and Expired Challenges, Tournaments with no Match results.

## Setup
python scripts/init_db.py
python scripts/create_admin.py

### Manual testing
python run.py

### Automated tests
python tests/run_tests.py




