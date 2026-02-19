import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [query, setQuery] = useState('Show me 2-bedroom apartments under AED 800k in Dubai Marina');
  const [results, setResults] = useState([]);
  const [summary, setSummary] = useState('');
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [greeting, setGreeting] = useState('');
  const [sessionMemory, setSessionMemory] = useState({
    firstQuery: null,
    filters: null
  });
  const [stats, setStats] = useState(null);
  const [showStats, setShowStats] = useState(false);

  // Sample queries for quick testing
  const sampleQueries = [
    'Show me 2-bedroom apartments under AED 800k in Dubai Marina',
    'Find cheapest apartments in Dubai',
    'Most expensive villas in Palm Jumeirah',
    'Show me studios for rent in JLT',
    'Find 3-bedroom apartments in Business Bay'
  ];

  useEffect(() => {
    // Greet on load
    fetch('http://localhost:8000/api/hello?q=hello')
      .then(r => r.json())
      .then(data => setGreeting(data.message))
      .catch(() => setGreeting('Welcome to Houser'));
  }, []);

  const handleSearch = async () => {
    setLoading(true);
    setError('');
    setResults([]);
    setSummary('');
    setStats(null);
    setShowStats(false);

    try {
      const response = await fetch('http://localhost:8000/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          q: query,
          filters: sessionMemory.filters 
        })
      });

      const data = await response.json();

      if (data.message) {
        setError(data.message);
      } else {
        setSummary(data.summary || '');
        setResults(data.results || []);
        setSources(data.sources || []);
        
        // Store session memory (remember first query)
        if (!sessionMemory.firstQuery) {
          setSessionMemory({
            firstQuery: query,
            filters: data.filters || {}
          });
        }
      }
    } catch (err) {
      setError('Failed to connect to backend. Make sure Django is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  const handleStats = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8000/api/stats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          area: 'Dubai Marina',
          city: 'Dubai'
        })
      });

      const data = await response.json();
      setStats(data);
      setShowStats(true);
    } catch (err) {
      setError('Failed to fetch statistics.');
    } finally {
      setLoading(false);
    }
  };

  const useSampleQuery = (sample) => {
    setQuery(sample);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="App">
      <header className="header">
        <h1>🏠 Houser</h1>
        <p className="tagline">Fast UAE Real Estate Search</p>
      </header>

      <main className="container">
        <div className="greeting-box">
          <p>{greeting}</p>
        </div>

        <div className="search-section">
          <div className="search-bar">
            <input 
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about properties..."
              className="search-input"
            />
            <button 
              onClick={handleSearch} 
              disabled={loading}
              className="search-button"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
            <button 
              onClick={handleStats}
              disabled={loading}
              className="stats-button"
            >
              Stats
            </button>
          </div>

          <div className="sample-queries">
            <p className="sample-label">Try these:</p>
            {sampleQueries.map((sample, idx) => (
              <button 
                key={idx}
                onClick={() => useSampleQuery(sample)}
                className="sample-button"
              >
                {sample}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="error-box">
            ⚠️ {error}
          </div>
        )}

        {summary && (
          <div className="summary-box">
            <h3>Summary</h3>
            <p>{summary}</p>
            {sources.length > 0 && (
              <p className="sources">
                <strong>Sources:</strong> {sources.join(', ')}
              </p>
            )}
          </div>
        )}

        {showStats && stats && (
          <div className="stats-box">
            <h3>Statistics for {stats.area}</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.counts.total}</div>
                <div className="stat-label">Total Properties</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.counts.active}</div>
                <div className="stat-label">Active Listings</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">AED {stats.prices.min.toLocaleString()}</div>
                <div className="stat-label">Min Price</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">AED {stats.prices.avg.toLocaleString()}</div>
                <div className="stat-label">Avg Price</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">AED {stats.prices.max.toLocaleString()}</div>
                <div className="stat-label">Max Price</div>
              </div>
            </div>
          </div>
        )}

        <div className="results-section">
          {results.length > 0 && (
            <>
              <h3>Properties ({results.length})</h3>
              <div className="results-grid">
                {results.map((property) => (
                  <div key={property.id} className="property-card">
                    {property.thumbnail && (
                      <img 
                        src={property.thumbnail} 
                        alt={property.title}
                        className="property-image"
                        loading="lazy"
                      />
                    )}
                    <div className="property-details">
                      <h4 className="property-title">{property.title}</h4>
                      <p className="property-price">AED {property.price.toLocaleString()}</p>
                      <div className="property-meta">
                        <span>🛏️ {property.beds} beds</span>
                        <span>🚿 {property.baths} baths</span>
                        <span>📍 {property.area}</span>
                      </div>
                      <div className="property-footer">
                        <span className="property-source">Source: {property.source}</span>
                        {property.sourceUrl && (
                          <a 
                            href={property.sourceUrl} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="view-link"
                          >
                            View →
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {sessionMemory.firstQuery && (
          <div className="memory-indicator">
            💾 Remembering: "{sessionMemory.firstQuery}"
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Houser AI — Accurate, Fast, Smart</p>
        <p className="disclaimer">Data from Bayut, Propertyfinder, Propsearch • Updated every 2 hours</p>
      </footer>
    </div>
  );
}

export default App;
