// JavaScript implementation was developed with AI-assisted debugging support from OpenAI ChatGPT, 
// mainly for Spotify Web Playback SDK state handling and refresh behavior


// Browser behavior for form tabs, MusicMe AI chat, recommendations rendering,
// and Spotify Web Playback SDK controls
const recommendationForm = document.getElementById("recommendationForm");
const hybridFields = document.querySelectorAll("[data-hybrid-field]");
const hybridFieldState = {};
const recommendationsContainer = document.getElementById("recommendations");
const initialRecommendations = window.__INITIAL_RECOMMENDATIONS__ || null;
const homeTabButtons = document.querySelectorAll("[data-tab-trigger]");
const homeTabPanels = document.querySelectorAll("[data-tab-panel]");
const aiInterviewContainer = document.querySelector("[data-ai-interview]");

// Shared Spotify SDK state; UI rendering reads from this single object
const spotifyState = {
    player: null,
    deviceId: "",
    sdkLoading: false,
    isAuthenticated: false,
    isPaused: false,
    isActive: false,
    currentTrack: {
        name: "",
        album: {
            images: [{ url: "" }],
        },
        artists: [{ name: "" }],
    },
};

function escapeHtml(value) {
    // Recommendation data and model output are rendered as HTML strings below
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function normalizeToken(value) {
    return value.trim().replace(/\s+/g, " ");
}

function splitTokens(value) {
    return value
        .split(",")
        .map(normalizeToken)
        .filter(Boolean);
}

function uniqueTokens(tokens) {
    const seen = new Set();

    return tokens.filter((token) => {
        const key = token.toLowerCase();

        if (seen.has(key)) {
            return false;
        }

        seen.add(key);
        return true;
    });
}

function initHybridField(field) {
    // Hybrid fields combine clickable pills with custom comma-separated text
    const fieldKey = field.dataset.hybridField;
    const input = field.querySelector("[data-hybrid-input]");
    const hiddenInput = field.querySelector("[data-selected-values]");
    const pills = Array.from(field.querySelectorAll(".select-pill"));
    const maxSelections = Number.parseInt(field.dataset.maxSelections || "5", 10);
    const selectedPills = new Map();

    hybridFieldState[fieldKey] = {
        getSelectedValues: () => [...selectedPills.values()],
        getCustomValue: () => input.value.trim(),
    };

    function updatePillUI() {
        // Disable unselected pills once the per-field selection cap is reached
        pills.forEach((pill) => {
            const key = pill.dataset.pillValue.toLowerCase();
            const isActive = selectedPills.has(key);
            const limitReached = !isActive && selectedPills.size >= maxSelections;

            pill.classList.toggle("is-active", isActive);
            pill.classList.toggle("is-disabled", limitReached);
            pill.setAttribute("aria-pressed", String(isActive));
            pill.disabled = limitReached;
        });
    }

    function syncHiddenInput() {
        hiddenInput.value = [...selectedPills.values()].join(", ");
    }

    function syncCustomInput() {
        input.value = uniqueTokens(splitTokens(input.value)).join(", ");
    }

    function syncFromInputs() {
        // Rehydrate state when Flask re-renders a failed form submission
        const typedTokens = splitTokens(input.value);
        const selectedTokens = splitTokens(hiddenInput.value);

        selectedPills.clear();
        selectedTokens.slice(0, maxSelections).forEach((token) => {
            selectedPills.set(token.toLowerCase(), token);
        });

        input.value = typedTokens
            .filter((token) => !selectedPills.has(token.toLowerCase()))
            .join(", ");
        updatePillUI();
        syncHiddenInput();
    }

    pills.forEach((pill) => {
        pill.addEventListener("click", () => {
            const value = pill.dataset.pillValue;
            const key = value.toLowerCase();

            if (selectedPills.has(key)) {
                selectedPills.delete(key);
            } else if (selectedPills.size < maxSelections) {
                selectedPills.set(key, value);
            }

            updatePillUI();
            syncHiddenInput();
        });
    });

    input.addEventListener("blur", syncCustomInput);
    syncFromInputs();
}

function getSpotifyElements() {
    // Return null-safe element handles; this script also runs on pages without playback
    return {
        authCard: document.getElementById("spotifyAuthCard"),
        authMessage: document.getElementById("spotifyAuthMessage"),
        loginButton: document.getElementById("spotifyLoginButton"),
        logoutButton: document.getElementById("spotifyLogoutButton"),
        playerCard: document.getElementById("spotifyPlayerCard"),
        playerStatus: document.getElementById("spotifyPlayerStatus"),
        deviceBadge: document.getElementById("spotifyDeviceBadge"),
        nowPlayingCover: document.getElementById("nowPlayingCover"),
        nowPlayingName: document.getElementById("nowPlayingName"),
        nowPlayingArtist: document.getElementById("nowPlayingArtist"),
        previousButton: document.getElementById("previousTrackButton"),
        toggleButton: document.getElementById("togglePlayButton"),
        nextButton: document.getElementById("nextTrackButton"),
    };
}

async function fetchSpotifyToken() {
    const response = await fetch("/auth/token", {
        headers: { Accept: "application/json" },
    });
    const data = await response.json();
    return data.access_token || "";
}

function renderSpotifyAuthState() {
    const elements = getSpotifyElements();
    if (!elements.authCard) {
        return;
    }

    if (!spotifyState.isAuthenticated) {
        elements.authMessage.textContent = "Log in with Spotify to enable browser playback for recommended tracks.";
        elements.loginButton.style.display = "inline-flex";
        elements.logoutButton.style.display = "none";
        elements.playerCard.style.display = "none";
        return;
    }

    elements.authMessage.textContent = "Spotify is connected. Choose MusicMe Web Player and press play on any recommended track.";
    elements.loginButton.style.display = "none";
    elements.logoutButton.style.display = "inline-flex";
    elements.playerCard.style.display = "block";
}

function setPlayerStatus(message, isReady = false) {
    const elements = getSpotifyElements();
    if (!elements.playerStatus || !elements.deviceBadge) {
        return;
    }

    elements.playerStatus.textContent = message;
    elements.deviceBadge.textContent = isReady ? "Ready" : "Offline";
    elements.deviceBadge.classList.toggle("is-ready", isReady);
}

function reportSpotifySdkError(message, keepReadyBadge = false) {
    console.error("Spotify SDK error:", message);
    showError(message);
    setPlayerStatus(message, keepReadyBadge);
}

function updateNowPlayingUI() {
    const elements = getSpotifyElements();
    if (!elements.nowPlayingName) {
        return;
    }

    const currentTrack = spotifyState.currentTrack;
    const imageUrl = currentTrack.album?.images?.[0]?.url || "";
    const artistName = currentTrack.artists?.map((artist) => artist.name).filter(Boolean).join(", ")
        || "Choose a recommendation to start playback";

    elements.nowPlayingName.textContent = currentTrack.name || "No track selected";
    elements.nowPlayingArtist.textContent = artistName;
    elements.nowPlayingCover.src = imageUrl;
    elements.nowPlayingCover.alt = currentTrack.name ? `Album art for ${currentTrack.name}` : "";
    elements.toggleButton.textContent = spotifyState.isPaused ? "Play" : "Pause";

    const controlsEnabled = Boolean(spotifyState.player) && spotifyState.isActive;
    elements.previousButton.disabled = !controlsEnabled;
    elements.toggleButton.disabled = !controlsEnabled;
    elements.nextButton.disabled = !controlsEnabled;
}

async function ensureSpotifySdk() {
    // The SDK is loaded only after auth is confirmed and only on the recommendations page
    if (!document.getElementById("spotifyPlaybackPanel") || !spotifyState.isAuthenticated || spotifyState.player || spotifyState.sdkLoading) {
        return;
    }

    spotifyState.sdkLoading = true;

    const script = document.createElement("script");
    script.src = "https://sdk.scdn.co/spotify-player.js";
    script.async = true;
    document.body.appendChild(script);

    window.onSpotifyWebPlaybackSDKReady = () => {
        spotifyState.sdkLoading = false;

        const player = new window.Spotify.Player({
            name: "MusicMe Web Player",
            getOAuthToken: async (callback) => {
                const token = await fetchSpotifyToken();
                callback(token);
            },
            volume: 0.5,
        });

        spotifyState.player = player;

        player.addListener("initialization_error", ({ message }) => {
            reportSpotifySdkError(`Spotify player initialization failed: ${message}`);
        });

        player.addListener("authentication_error", ({ message }) => {
            reportSpotifySdkError(`Spotify authentication failed: ${message}`);
        });

        player.addListener("account_error", ({ message }) => {
            reportSpotifySdkError(`Spotify account error: ${message}. A Premium account is required for browser playback.`);
        });

        player.addListener("playback_error", ({ message }) => {
            reportSpotifySdkError(`Spotify playback error: ${message}`, true);
        });

        player.addListener("autoplay_failed", () => {
            reportSpotifySdkError("Browser autoplay blocked Spotify playback. Click Play In Browser again or use the player controls.");
        });

        player.addListener("ready", ({ device_id: deviceId }) => {
            spotifyState.deviceId = deviceId;
            setPlayerStatus("Ready for browser playback. Select any recommended track to start.", true);
            updateNowPlayingUI();
        });

        player.addListener("not_ready", ({ device_id: deviceId }) => {
            if (spotifyState.deviceId === deviceId) {
                spotifyState.deviceId = "";
            }
            spotifyState.isActive = false;
            setPlayerStatus("The browser player went offline. Refresh the page to reconnect.", false);
            updateNowPlayingUI();
        });

        player.addListener("player_state_changed", (state) => {
            // Null state means Spotify has no active SDK state for this browser device
            if (!state) {
                spotifyState.isActive = false;
                updateNowPlayingUI();
                return;
            }

            spotifyState.currentTrack = state.track_window.current_track;
            spotifyState.isPaused = state.paused;

            player.getCurrentState().then((currentState) => {
                spotifyState.isActive = Boolean(currentState);
                updateNowPlayingUI();
            });
        });

        player.connect().then((connected) => {
            if (!connected) {
                setPlayerStatus("Spotify could not connect the browser player.", false);
            }
        });
    };
}

async function bootstrapSpotifyAuth() {
    // Recommendations can render without auth; playback controls activate only after login
    if (!document.getElementById("spotifyPlaybackPanel")) {
        return;
    }

    try {
        const token = await fetchSpotifyToken();
        spotifyState.isAuthenticated = Boolean(token);
        renderSpotifyAuthState();

        // Recommendations may render before the async auth check completes on refresh
        // Re-render them after auth state is known so playback buttons stay available
        if (initialRecommendations) {
            displayResults(initialRecommendations);
        }

        if (spotifyState.isAuthenticated) {
            setPlayerStatus("Connecting to Spotify...", false);
            await ensureSpotifySdk();
        }
    } catch (error) {
        console.error("Spotify auth bootstrap failed:", error);
        setPlayerStatus("Spotify login status could not be loaded.", false);
    }
}

async function playTrackInBrowser(uri) {
    if (!spotifyState.isAuthenticated) {
        showError("Log in with Spotify before trying browser playback.");
        return;
    }

    if (!spotifyState.player || !spotifyState.deviceId) {
        showError("Spotify Web Player is not ready yet. Wait a moment and try again.");
        return;
    }

    try {
        // Browser playback must be activated from a user gesture before Spotify will play
        if (typeof spotifyState.player.activateElement === "function") {
            await spotifyState.player.activateElement();
        }

        const response = await fetch("/player/play", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                uri,
                device_id: spotifyState.deviceId,
            }),
        });

        const data = await response.json();
        if (!response.ok) {
            const details = data.details ? ` ${data.details}` : "";
            throw new Error((data.error || `Playback failed with status ${response.status}`) + details);
        }

        hideError();
        setPlayerStatus("Playback requested from Spotify. If nothing starts, confirm that MusicMe Web Player is selected in Spotify Connect.", true);
    } catch (error) {
        console.error("Playback error:", error);
        showError(error.message);
    }
}

function displayResults(data) {
    // Server-rendered recommendation payloads are converted into interactive cards here
    if (!recommendationsContainer) {
        return;
    }

    const resultsContainer = document.getElementById("results");
    const summaryDiv = document.getElementById("summary");
    const sdkMeta = data.spotify_sdk || {};
    const parsedIntent = data.parsed_intent || {};
    const modeLabel = data.mode_label || "Regular Recommender";
    const summaryTitle = data.mode === "ai" ? "MusicMe AI Summary" : "Recommendation Summary";
    const parsedTags = [
        ...(Array.isArray(parsedIntent.mood) ? parsedIntent.mood : []),
        ...(Array.isArray(parsedIntent.genre) ? parsedIntent.genre : []),
        ...(Array.isArray(parsedIntent.vibe) ? parsedIntent.vibe : []),
    ].filter(Boolean);
    const audioTargets = [
        Number.isFinite(parsedIntent.energy) ? `energy ${Math.round(parsedIntent.energy * 100)}%` : "",
        Number.isFinite(parsedIntent.valence) ? `mood ${Math.round(parsedIntent.valence * 100)}% bright` : "",
        Number.isFinite(parsedIntent.danceability) ? `dance ${Math.round(parsedIntent.danceability * 100)}%` : "",
    ].filter(Boolean);
    const intentMarkup = data.mode === "ai" && (parsedTags.length || audioTargets.length)
        ? `<p class="field-hint">Interpreted from free-text: ${escapeHtml([...parsedTags, ...audioTargets].join(" • "))}</p>`
        : "";

    summaryDiv.innerHTML = `
        <h3>${escapeHtml(summaryTitle)}</h3>
        <p>${escapeHtml(data.summary || "No summary available")}</p>
        ${intentMarkup}
        <div class="sdk-meta">
            <span>${escapeHtml(modeLabel)}</span>
            <span>Source: ${escapeHtml(sdkMeta.provider || "Spotify")}</span>
            <span>${Number.isFinite(sdkMeta.track_count) ? sdkMeta.track_count : 0} tracks scanned</span>
            <span>${spotifyState.isAuthenticated ? "Playback login active" : "Playback login inactive"}</span>
        </div>
    `;

    let recommendationsHTML = "<h3>Recommended Tracks</h3>";

    if (Array.isArray(data.recommendations) && data.recommendations.length > 0) {
        data.recommendations.forEach((track, index) => {
            const trackName = track.name || "Unknown Track";
            const artistName = track.artists && track.artists.length > 0
                ? track.artists[0].name
                : "Unknown Artist";
            const albumName = track.album && track.album.name ? track.album.name : "Unknown Album";
            const spotifyUrl = track.spotify_url || "";
            const previewUrl = track.preview_url || "";
            const trackUri = track.uri || "";

            recommendationsHTML += `
                <article class="recommendation-item recommendation-card">
                    <div class="recommendation-copy">
                        <div class="recommendation-header">
                            <h4>${index + 1}. ${escapeHtml(trackName)}</h4>
                        </div>
                        <p>Artist: ${escapeHtml(artistName)}</p>
                        <p>Album: ${escapeHtml(albumName)}</p>
                        <div class="recommendation-actions">
                            ${spotifyState.isAuthenticated && trackUri
                                ? `<button type="button" class="btn-secondary btn-inline play-track-button" data-track-uri="${escapeHtml(trackUri)}">Play In Browser</button>`
                                : '<span class="preview-badge preview-badge-muted">Spotify login required</span>'}
                            ${spotifyUrl
                                ? `<a href="${escapeHtml(spotifyUrl)}" target="_blank" rel="noopener noreferrer" class="spotify-link">Open in Spotify</a>`
                                : ""}
                            ${previewUrl
                                ? `<a href="${escapeHtml(previewUrl)}" target="_blank" rel="noopener noreferrer" class="preview-link">Open Preview</a>`
                                : '<span class="preview-badge preview-badge-muted">No Spotify preview</span>'}
                        </div>
                        ${previewUrl
                            ? `<audio controls preload="none" class="preview-player">
                                <source src="${escapeHtml(previewUrl)}" type="audio/mpeg">
                               </audio>`
                            : '<p class="preview-unavailable">Preview unavailable for this track. Browser playback requires Spotify login.</p>'}
                    </div>
                </article>
            `;
        });
    } else {
        recommendationsHTML += "<p>No recommendations available at this time.</p>";
    }

    recommendationsContainer.innerHTML = recommendationsHTML;
    resultsContainer.style.display = "block";
}

function showError(message) {
    const errorDiv = document.getElementById("error");
    if (!errorDiv) {
        return;
    }
    errorDiv.textContent = message;
    errorDiv.style.display = "block";
}

function hideError() {
    const errorDiv = document.getElementById("error");
    if (!errorDiv) {
        return;
    }
    errorDiv.style.display = "none";
}

function initializeRecommendationsPage() {
    // Flask injects the latest payload into window__INITIAL_RECOMMENDATIONS__
    if (initialRecommendations) {
        displayResults(initialRecommendations);
    }
}

function setActiveHomeTab(tabName) {
    // Tabs are client-side only; each panel still posts to a separate Flask route
    homeTabButtons.forEach((button) => {
        const isActive = button.dataset.tabTrigger === tabName;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-selected", String(isActive));
    });

    homeTabPanels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.tabPanel === tabName);
    });
}

const fallbackAiInterviewQuestions = [
    "What are you doing or getting ready for while listening?",
    "How should the music make you feel?",
    "What sounds, genres, or artists should guide the recommendations?",
];

const aiInterviewState = {
    // History is sent to Flask so Ollama can ask one contextual follow-up at a time
    history: [],
    currentQuestion: "",
    initialRequest: "",
    fallbackIndex: 0,
    isComplete: false,
    isLoading: false,
};

function getAiInterviewElements() {
    return {
        messages: document.getElementById("aiInterviewMessages"),
        answers: document.getElementById("aiInterviewAnswers"),
        input: document.getElementById("aiInterviewInput"),
        initialRequest: document.getElementById("natural_language_request"),
        replyButton: document.getElementById("aiInterviewReplyButton"),
        submitButton: aiInterviewContainer?.closest("form")?.querySelector('button[type="submit"]'),
    };
}

function appendAiChatMessage(role, text) {
    const elements = getAiInterviewElements();
    if (!elements.messages) {
        return;
    }

    const message = document.createElement("div");
    message.className = `ai-chat-message ai-chat-message-${role}`;
    message.textContent = text;
    elements.messages.appendChild(message);
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

function syncAiInterviewHiddenAnswers() {
    const elements = getAiInterviewElements();
    if (!elements.answers) {
        return;
    }

    // Hidden inputs let the regular form submission carry chat answers to Flask
    const followUpTurns = aiInterviewState.history.filter((turn) => !turn.isInitialRequest);
    elements.answers.innerHTML = followUpTurns.map((turn, index) => `
        <input type="hidden" name="ai_answer_${index + 1}" value="${escapeHtml(turn.answer)}">
    `).join("");
}

function setAiInterviewControls() {
    const elements = getAiInterviewElements();
    if (!elements.input || !elements.replyButton || !elements.submitButton) {
        return;
    }

    elements.input.disabled = aiInterviewState.isComplete || aiInterviewState.isLoading;
    elements.replyButton.disabled = aiInterviewState.isComplete || aiInterviewState.isLoading;
    // Prevent submitting incomplete AI interviews with no useful preference signal
    elements.submitButton.disabled = !aiInterviewState.isComplete;
    elements.submitButton.textContent = aiInterviewState.isComplete ? "Launch MusicMe AI" : "Finish Interview First";
    elements.input.placeholder = aiInterviewState.initialRequest ? "Type your answer..." : "Tell MusicMe AI what you want to hear...";
}

function fallbackNextAiQuestion() {
    // Local fallback keeps the interview usable when Ollama or the route is unavailable
    const followUpCount = aiInterviewState.history.filter((turn) => !turn.isInitialRequest).length;
    const nextIndex = Math.max(aiInterviewState.fallbackIndex, followUpCount);
    if (nextIndex >= fallbackAiInterviewQuestions.length) {
        return { is_complete: true, question: "" };
    }

    const question = fallbackAiInterviewQuestions[nextIndex];
    aiInterviewState.fallbackIndex = nextIndex + 1;
    return { is_complete: false, question };
}

async function requestNextAiQuestion() {
    // Each turn posts the whole short history; the server decides whether to stop
    aiInterviewState.isLoading = true;
    setAiInterviewControls();
    const elements = getAiInterviewElements();
    const initialRequest = normalizeToken(aiInterviewState.initialRequest || elements.initialRequest?.value || aiInterviewContainer?.dataset.existingRequest || "");

    try {
        const response = await fetch("/interview-next", {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                history: aiInterviewState.history,
                initial_request: initialRequest,
            }),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `Interview request failed with status ${response.status}`);
        }

        return data;
    } catch (error) {
        console.error("MusicMe AI interview turn failed:", error);
        return fallbackNextAiQuestion();
    } finally {
        aiInterviewState.isLoading = false;
    }
}

async function advanceAiInterview() {
    // Move from assistant question to completion state after enough answers are collected
    const nextTurn = await requestNextAiQuestion();

    if (nextTurn.is_complete) {
        aiInterviewState.isComplete = true;
        aiInterviewState.currentQuestion = "";
        appendAiChatMessage("assistant", "I have enough to build your recommendations.");
        syncAiInterviewHiddenAnswers();
        setAiInterviewControls();
        return;
    }

    aiInterviewState.currentQuestion = nextTurn.question || fallbackNextAiQuestion().question;
    appendAiChatMessage("assistant", aiInterviewState.currentQuestion);
    setAiInterviewControls();
}

async function submitAiInterviewReply() {
    // Enter without Shift acts like a chat send; Shift+Enter still creates a newline
    const elements = getAiInterviewElements();
    const answer = normalizeToken(elements.input?.value || "");

    if (!answer || !aiInterviewState.currentQuestion) {
        return;
    }

    appendAiChatMessage("user", answer);
    if (!aiInterviewState.initialRequest) {
        aiInterviewState.initialRequest = answer;
        if (elements.initialRequest) {
            elements.initialRequest.value = answer;
        }
        aiInterviewState.history.push({
            question: aiInterviewState.currentQuestion,
            answer,
            isInitialRequest: true,
        });
        elements.input.value = "";
        syncAiInterviewHiddenAnswers();
        await advanceAiInterview();
        return;
    }

    aiInterviewState.history.push({
        question: aiInterviewState.currentQuestion,
        answer,
    });
    elements.input.value = "";
    syncAiInterviewHiddenAnswers();
    await advanceAiInterview();
}

function initializeAiInterview() {
    // Initialize only on the homepage AI tab; other pages do not include chat elements
    if (!aiInterviewContainer) {
        return;
    }

    const elements = getAiInterviewElements();
    if (elements.messages) {
        elements.messages.innerHTML = "";
    }

    const existingRequest = normalizeToken(elements.initialRequest?.value || aiInterviewContainer.dataset.existingRequest || "");
    if (existingRequest) {
        aiInterviewState.initialRequest = existingRequest;
        aiInterviewState.history.push({
            question: "What do you want to hear right now?",
            answer: existingRequest,
            isInitialRequest: true,
        });
        appendAiChatMessage("user", existingRequest);
        advanceAiInterview();
    } else {
        aiInterviewState.currentQuestion = "What do you want to hear right now?";
        appendAiChatMessage("assistant", aiInterviewState.currentQuestion);
    }

    if (elements.replyButton) {
        elements.replyButton.addEventListener("click", submitAiInterviewReply);
    }

    if (elements.input) {
        elements.input.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submitAiInterviewReply();
            }
        });
    }

    setAiInterviewControls();
}

hybridFields.forEach(initHybridField);
initializeAiInterview();
bootstrapSpotifyAuth();
initializeRecommendationsPage();

if (homeTabButtons.length > 0) {
    // Home tabs are progressive enhancement over server-rendered default panels
    homeTabButtons.forEach((button) => {
        button.addEventListener("click", () => {
            setActiveHomeTab(button.dataset.tabTrigger || "standard");
        });
    });
}

if (recommendationsContainer) {
    // Recommendation cards delegate playback clicks from dynamically rendered markup
    recommendationsContainer.addEventListener("click", async (event) => {
        const playButton = event.target.closest(".play-track-button");
        if (!playButton) {
            return;
        }

        await playTrackInBrowser(playButton.dataset.trackUri || "");
    });
}

const spotifyLogoutButton = document.getElementById("spotifyLogoutButton");
if (spotifyLogoutButton) {
    spotifyLogoutButton.addEventListener("click", async () => {
        await fetch("/auth/logout", {
            method: "POST",
        });
        window.location.reload();
    });
}

const previousTrackButton = document.getElementById("previousTrackButton");
const togglePlayButton = document.getElementById("togglePlayButton");
const nextTrackButton = document.getElementById("nextTrackButton");

if (previousTrackButton) {
    previousTrackButton.addEventListener("click", () => {
        if (spotifyState.player) {
            spotifyState.player.previousTrack();
        }
    });
}

if (togglePlayButton) {
    togglePlayButton.addEventListener("click", () => {
        if (spotifyState.player) {
            spotifyState.player.togglePlay();
        }
    });
}

if (nextTrackButton) {
    nextTrackButton.addEventListener("click", () => {
        if (spotifyState.player) {
            spotifyState.player.nextTrack();
        }
    });
}

const revealElements = document.querySelectorAll(".reveal");

if (revealElements.length > 0) {
    // About-page reveal animation is opt-in via the reveal class
    const revealObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.18,
    });

    revealElements.forEach((element) => revealObserver.observe(element));
}
