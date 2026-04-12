const recommendationForm = document.getElementById('recommendationForm');
const hybridFields = document.querySelectorAll('[data-hybrid-field]');
const hybridFieldState = {};

function normalizeToken(value) {
    return value.trim().replace(/\s+/g, ' ');
}

function splitTokens(value) {
    return value
        .split(',')
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
    const fieldKey = field.dataset.hybridField;
    const input = field.querySelector('[data-hybrid-input]');
    const hiddenInput = field.querySelector('[data-selected-values]');
    const pills = Array.from(field.querySelectorAll('.select-pill'));
    const maxSelections = Number.parseInt(field.dataset.maxSelections || '5', 10);
    const selectedPills = new Map();

    hybridFieldState[fieldKey] = {
        getSelectedValues: () => [...selectedPills.values()],
        getCustomValue: () => input.value.trim(),
    };

    function updatePillUI() {
        pills.forEach((pill) => {
            const key = pill.dataset.pillValue.toLowerCase();
            const isActive = selectedPills.has(key);
            const limitReached = !isActive && selectedPills.size >= maxSelections;

            pill.classList.toggle('is-active', isActive);
            pill.classList.toggle('is-disabled', limitReached);
            pill.setAttribute('aria-pressed', String(isActive));
            pill.disabled = limitReached;
        });
    }

    function syncHiddenInput() {
        hiddenInput.value = [...selectedPills.values()].join(', ');
    }

    function syncCustomInput() {
        input.value = uniqueTokens(splitTokens(input.value)).join(', ');
    }

    function syncFromInputs() {
        const typedTokens = splitTokens(input.value);
        const selectedTokens = splitTokens(hiddenInput.value);

        selectedPills.clear();
        selectedTokens.slice(0, maxSelections).forEach((token) => {
            selectedPills.set(token.toLowerCase(), token);
        });

        input.value = typedTokens
            .filter((token) => !selectedPills.has(token.toLowerCase()))
            .join(', ');
        updatePillUI();
        syncHiddenInput();
    }

    pills.forEach((pill) => {
        pill.addEventListener('click', () => {
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

    input.addEventListener('blur', syncCustomInput);
    syncFromInputs();
}

hybridFields.forEach(initHybridField);

if (recommendationForm) {
    recommendationForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Get form data
        const formData = new FormData(recommendationForm);
        const responses = {
            selected_moods: hybridFieldState.mood ? hybridFieldState.mood.getSelectedValues() : [],
            custom_mood: hybridFieldState.mood ? hybridFieldState.mood.getCustomValue() : "",
            selected_genres: hybridFieldState.genre ? hybridFieldState.genre.getSelectedValues() : [],
            custom_genre: hybridFieldState.genre ? hybridFieldState.genre.getCustomValue() : "",
            artist: formData.get('artist') || "",
            vibe: formData.get('vibe') || "",
        };

        // Show loading state
        showLoading(true);
        hideError();
        hideResults();

        try {
            // Send request to backend
            const response = await fetch('/recommend', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ responses })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Display results
            displayResults(data);
            showLoading(false);
        } catch (error) {
            console.error('Error:', error);
            showError(`Failed to get recommendations: ${error.message}`);
            showLoading(false);
        }
    });
}

// Display results
function displayResults(data) {
    const resultsContainer = document.getElementById('results');
    const summaryDiv = document.getElementById('summary');
    const recommendationsDiv = document.getElementById('recommendations');

    // Display summary
    summaryDiv.innerHTML = `
        <h3>AI Summary</h3>
        <p>${data.summary || 'No summary available'}</p>
    `;

    // Display recommendations
    let recommendationsHTML = '<h3>Recommended Tracks</h3>';
    
    if (Array.isArray(data.recommendations) && data.recommendations.length > 0) {
        data.recommendations.forEach((track, index) => {
            const trackName = track.name || 'Unknown Track';
            const artistName = track.artists && track.artists.length > 0 
                ? track.artists[0].name 
                : 'Unknown Artist';
            
            recommendationsHTML += `
                <div class="recommendation-item">
                    <h4>${index + 1}. ${trackName}</h4>
                    <p>Artist: ${artistName}</p>
                </div>
            `;
        });
    } else {
        recommendationsHTML += '<p>No recommendations available at this time.</p>';
    }

    recommendationsDiv.innerHTML = recommendationsHTML;
    resultsContainer.style.display = 'block';

    // Scroll to results
    resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Show/hide loading state
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

// Show/hide error message
function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function hideError() {
    document.getElementById('error').style.display = 'none';
}

// Hide results
function hideResults() {
    document.getElementById('results').style.display = 'none';
}

const revealElements = document.querySelectorAll('.reveal');

if (revealElements.length > 0) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.18
    });

    revealElements.forEach((element) => revealObserver.observe(element));
}
