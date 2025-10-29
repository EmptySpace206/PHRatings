// Global variables
let authToken = localStorage.getItem('authToken') || null;
let userType = localStorage.getItem('userType') || null;
let userName = localStorage.getItem('userName') || null;
let userId = localStorage.getItem('userId') || null;

// Update token display on page load
document.addEventListener('DOMContentLoaded', function () {
    updateTokenDisplay();
    updateUserInfo();
});

function updateTokenDisplay() {
    const tokenDisplay = document.getElementById('currentToken');
    if (authToken) {
        tokenDisplay.textContent = authToken.substring(0, 20) + '...';
        tokenDisplay.className = 'success';
    } else {
        tokenDisplay.textContent = 'Not logged in';
        tokenDisplay.className = 'error';
    }
}

function updateUserInfo() {
    const userInfoDisplay = document.getElementById('userInfo');
    if (authToken && userType && userName) {
        let displayText = `${userType.toUpperCase()} - ${userName}`;
        if (userId) {
            displayText += ` (ID: ${userId})`;
        }
        userInfoDisplay.textContent = displayText;
        userInfoDisplay.className = 'success';
    } else {
        userInfoDisplay.textContent = 'Not logged in';
        userInfoDisplay.className = 'error';
    }
}

function clearToken() {
    authToken = null;
    userType = null;
    userName = null;
    userId = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('userType');
    localStorage.removeItem('userName');
    localStorage.removeItem('userId');
    updateTokenDisplay();
    updateUserInfo();
}

// Utility function to make API calls
async function makeApiCall(url, method = 'GET', data = null, needsAuth = false) {
    const options = {
        method: method,
        headers: {}
    };

    if (needsAuth && authToken) {
        options.headers['Authorization'] = `Bearer ${authToken}`;
    }

    if (data) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        const result = await response.json();

        return {
            status: response.status,
            data: result,
            success: response.ok
        };
    } catch (error) {
        return {
            status: 0,
            data: { error: error.message },
            success: false
        };
    }
}

function displayResponse(elementId, response) {
    const element = document.getElementById(elementId);
    const statusClass = response.success ? 'success' : 'error';
    element.innerHTML = `<span class="${statusClass}">Status: ${response.status}</span>\n${JSON.stringify(response.data, null, 2)}`;
}

// Admin Authentication Functions
async function loginAdmin() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    const response = await makeApiCall('/admin/login', 'POST', {
        username: username,
        password: password
    });

    if (response.success && response.data.token) {
        authToken = response.data.token;
        userType = response.data.user_type;
        userName = username;
        userId = null;
        localStorage.setItem('authToken', authToken);
        localStorage.setItem('userType', userType);
        localStorage.setItem('userName', userName);
        updateTokenDisplay();
        updateUserInfo();
    }

    displayResponse('loginResponse', response);
}

async function logoutAdmin() {
    const response = await makeApiCall('/admin/logout', 'POST', null, true);

    if (response.success) {
        clearToken();
    }

    displayResponse('logoutResponse', response);
}

// Player Authentication Functions
async function loginPlayer() {
    const name = document.getElementById('playerLoginName').value;
    const password = document.getElementById('playerLoginPassword').value;

    const response = await makeApiCall('/player/login', 'POST', {
        name: name,
        password: password
    });

    if (response.success && response.data.token) {
        authToken = response.data.token;
        userType = response.data.user_type;
        userName = response.data.player_name;
        userId = response.data.player_id;
        localStorage.setItem('authToken', authToken);
        localStorage.setItem('userType', userType);
        localStorage.setItem('userName', userName);
        localStorage.setItem('userId', userId);
        updateTokenDisplay();
        updateUserInfo();
    }

    displayResponse('playerLoginResponse', response);
}

async function logoutPlayer() {
    const response = await makeApiCall('/player/logout', 'POST', null, true);

    if (response.success) {
        clearToken();
    }

    displayResponse('playerLogoutResponse', response);
}

// Player Management Functions
async function registerPlayer() {
    const name = document.getElementById('playerName').value;
    const age = parseInt(document.getElementById('playerAge').value);
    const weight = parseFloat(document.getElementById('playerWeight').value);
    const password = document.getElementById('playerPassword').value;

    const response = await makeApiCall('/players', 'POST', {
        name: name,
        age: age,
        weight: weight,
        password: password
    });

    displayResponse('regPlayerResponse', response);
}

async function listPlayers() {
    const response = await makeApiCall('/players');
    displayResponse('playersResponse', response);
}

async function listPendingPlayers() {
    const response = await makeApiCall('/admin/players/pending', 'GET', null, true);
    displayResponse('adminPlayerResponse', response);
}

async function approvePlayer() {
    const playerId = document.getElementById('approvePlayerId').value;
    const response = await makeApiCall(`/admin/players/${playerId}/approve`, 'POST', null, true);
    displayResponse('adminPlayerResponse', response);
}

async function rejectPlayer() {
    const playerId = document.getElementById('rejectPlayerId').value;
    const response = await makeApiCall(`/admin/players/${playerId}/reject`, 'DELETE', null, true);
    displayResponse('adminPlayerResponse', response);
}

async function updateWeight() {
    const weight = parseFloat(document.getElementById('newWeight').value);

    const data = { weight: weight };

    // If admin, they need to provide player_id in the request
    // This should be added manually for admin testing

    const response = await makeApiCall(`/players/weight`, 'PUT', data, true);

    displayResponse('updateWeightResponse', response);
}

// Challenge System Functions
async function createChallenge() {
    const challengerId = parseInt(document.getElementById('challengerId').value);
    const challengedId = parseInt(document.getElementById('challengedId').value);
    const hostId = parseInt(document.getElementById('challengeHostId').value);

    const response = await makeApiCall('/challenges', 'POST', {
        challenger_id: challengerId,
        challenged_id: challengedId,
        host_id: hostId
    }, true);

    displayResponse('createChallengeResponse', response);
}

async function acceptChallenge() {
    const challengeId = document.getElementById('acceptChallengeId').value;

    const response = await makeApiCall(`/challenges/${challengeId}/accept`, 'POST', {}, true);

    displayResponse('acceptChallengeResponse', response);
}

async function listChallenges() {
    const response = await makeApiCall('/challenges');
    displayResponse('challengesResponse', response);
}

// Tournament System Functions
async function createTournament() {
    const name = document.getElementById('tournamentName').value;
    const hostId = parseInt(document.getElementById('tournamentHostId').value);
    const startTime = document.getElementById('tournamentStartTime').value;

    const response = await makeApiCall('/tournaments', 'POST', {
        name: name,
        host_id: hostId,
        start_time: startTime
    }, true);

    displayResponse('createTournamentResponse', response);
}

async function joinTournament() {
    const tournamentId = document.getElementById('joinTournamentId').value;

    // Player joins themselves - no need to specify player_id
    const response = await makeApiCall(`/tournaments/${tournamentId}/join`, 'POST', {}, true);

    displayResponse('tournamentActionsResponse', response);
}

async function leaveTournament() {
    const tournamentId = document.getElementById('leaveTournamentId').value;

    // Player leaves themselves - no need to specify player_id
    const response = await makeApiCall(`/tournaments/${tournamentId}/leave`, 'DELETE', {}, true);

    displayResponse('tournamentActionsResponse', response);
}

async function listTournaments() {
    const response = await makeApiCall('/tournaments');
    displayResponse('tournamentsResponse', response);
}

async function getTournamentParticipants() {
    const tournamentId = document.getElementById('participantsTournamentId').value;
    const response = await makeApiCall(`/tournaments/${tournamentId}/participants`);
    displayResponse('tournamentsResponse', response);
}

// Match System Functions
async function recordMatchResult() {
    const player1Id = parseInt(document.getElementById('matchPlayer1Id').value);
    const player2Id = parseInt(document.getElementById('matchPlayer2Id').value);
    const hostId = parseInt(document.getElementById('matchHostId').value);
    const winnerId = parseInt(document.getElementById('winnerId').value);
    const notes = document.getElementById('matchNotes').value;
    const videoLink = document.getElementById('videoLink').value;

    const data = {
        player1_id: player1Id,
        player2_id: player2Id,
        host_id: hostId,
        winner_id: winnerId
    };

    if (notes) data.notes = notes;
    if (videoLink) data.video_link = videoLink;

    const response = await makeApiCall('/matches/result', 'POST', data, true);
    displayResponse('matchResponse', response);
}

async function recordTournamentMatch() {
    const tournamentId = document.getElementById('tournMatchTournamentId').value;
    const hostId = parseInt(document.getElementById('tournMatchHostId').value);
    const player1Id = parseInt(document.getElementById('tournMatchPlayer1Id').value);
    const player2Id = parseInt(document.getElementById('tournMatchPlayer2Id').value);
    const winnerId = parseInt(document.getElementById('tournMatchWinnerId').value);

    const response = await makeApiCall(`/tournaments/${tournamentId}/record-match`, 'POST', {
        host_id: hostId,
        player1_id: player1Id,
        player2_id: player2Id,
        winner_id: winnerId
    }, true);

    displayResponse('matchResponse', response);
}

async function undoLastMatch() {
    // Logged in player undoes their own match - no need to specify host_id
    const response = await makeApiCall('/matches/undo', 'POST', {}, true);

    displayResponse('matchResponse', response);
}

async function listMatches() {
    const response = await makeApiCall('/matches');
    displayResponse('matchResponse', response);
}

async function listMatchesByPlayer() {
    const playerId = document.getElementById('matchesPlayerId').value;
    const response = await makeApiCall(`/matches?player_id=${playerId}`);
    displayResponse('matchResponse', response);
}

async function listMatchesByTournament() {
    const tournamentId = document.getElementById('matchesTournamentId').value;
    const response = await makeApiCall(`/matches?tournament_id=${tournamentId}`);
    displayResponse('matchResponse', response);
}

// SQL Query Function
async function runSqlQuery() {
    const query = document.getElementById('sqlQuery').value;

    const response = await makeApiCall('/sql', 'POST', {
        query: query
    }, true);

    displayResponse('sqlResponse', response);
}