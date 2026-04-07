// Form submission handler
document.getElementById('recommendationForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    // Get form data
    const formData = new FormData(document.getElementById('recommendationForm'));
    const responses = Object.fromEntries(formData);

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

// Update energy level display
document.getElementById('energy').addEventListener('input', (e) => {
    document.getElementById('energyValue').textContent = e.target.value;
});

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
