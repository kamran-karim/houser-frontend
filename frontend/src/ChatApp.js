import React, { useState, useEffect, useRef } from 'react';
import './ChatApp.css';

function ChatApp() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [sessionContext, setSessionContext] = useState({});
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    setMessages([{
      type: 'bot',
      content: 'Hello,I am your elite real estate advisor. I can help you find premium properties across the UAE, analyze live market data, and compare investment opportunities. What can I discover for you today?',
      timestamp: new Date()
    }]);
  }, []);

  const [selectedProperty, setSelectedProperty] = useState(null);

  const PropertyModal = ({ property, onClose }) => {
    if (!property) return null;
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={e => e.stopPropagation()}>
          <button className="modal-close" onClick={onClose}>✕</button>
          <img className="modal-image" src={property.thumbnail || 'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&w=800&q=80'} alt={property.title} />
          <div className="modal-body">
            <div className="modal-price">AED {property.price.toLocaleString()}</div>
            <h2 className="modal-title">{property.title}</h2>

            <div className="modal-meta">
              <div className="meta-item">
                <div className="meta-icon">🛏️</div>
                <div className="meta-label">{property.beds} BEDS</div>
              </div>
              <div className="meta-item">
                <div className="meta-icon">🚿</div>
                <div className="meta-label">{property.baths} BATHS</div>
              </div>
              <div className="meta-item">
                <div className="meta-icon">📍</div>
                <div className="meta-label">{property.city}</div>
              </div>
            </div>

            <div className="modal-desc">
              <h3>PROPERTY OVERVIEW</h3>
              <p>{property.description}</p>
            </div>

            <div className="modal-footer">
              <div className="source-badge">{property.source} • VERIFIED LISTING</div>
              {property.sourceUrl && (
                <a href={property.sourceUrl} className="modal-view-link" target="_blank" rel="noopener noreferrer">
                  Explore Listing →
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const sendMessage = async (overrideInput = null) => {
    const textToSend = overrideInput || input;
    if (!textToSend.trim() || loading) return;

    const userMsgContent = textToSend.trim();
    const userMessage = {
      type: 'user',
      content: userMsgContent,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setLoadingStatus('Initializing AI Engine...');

    const history = messages.map(m => ({
      role: m.type === 'user' ? 'user' : 'assistant',
      content: m.content
    }));

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsgContent,
          context: { ...sessionContext, history }
        })
      });

      if (!response.body) throw new Error("ReadableStream not supported");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let botContent = "";
      let botResults = [];

      const tempId = Date.now();
      setMessages(prev => [...prev, {
        id: tempId,
        type: 'bot',
        content: '',
        messageType: 'search',
        results: [],
        timestamp: new Date()
      }]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.type === 'intent') {
                setLoadingStatus(`Searching for properties in ${data.filters.area || data.filters.city || 'UAE'}...`);
                setSessionContext(prev => ({ ...prev, filters: data.filters }));
              }
              else if (data.type === 'results') {
                botResults = data.results;
                setMessages(prev => prev.map(m => m.id === tempId ? { ...m, results: botResults } : m));
              }
              else if (data.type === 'search_stats') {
                // attach stats to the temp bot message for non-intrusive display
                setMessages(prev => prev.map(m => m.id === tempId ? { ...m, stats: data.stats, statsSummary: data.summary } : m));
              }
              else if (data.type === 'key_highlights') {
                // structured highlights for quick display
                setMessages(prev => prev.map(m => m.id === tempId ? { ...m, keyHighlights: data.highlights } : m));
              }
              else if (data.type === 'text_chunk') {
                botContent += data.content;
                setMessages(prev => prev.map(m => m.id === tempId ? { ...m, content: botContent } : m));
              }
              else if (data.response) {
                botContent = data.response;
                const mType = data.type || 'info';
                setMessages(prev => prev.map(m => m.id === tempId ? { ...m, content: botContent, messageType: mType } : m));
                if (mType !== 'search') setLoading(false);
              }
              else if (data.type === 'final') {
                setLoadingStatus('Analysis complete.');
                setLoading(false);
                if (botResults.length > 0) {
                  const resultSummary = botResults.slice(0, 5).map(r => `${r.title} (AED ${r.price.toLocaleString()})`).join(', ');
                  setSessionContext(prev => ({
                    ...prev,
                    lastResultsSummary: resultSummary,
                    seen_ids: [...new Set([...(prev.seen_ids || []), ...botResults.map(r => r.id)])]
                  }));
                }
              }
              else if (data.type === 'error') {
                throw new Error(data.response);
              }
            } catch (e) {
              console.error("Error parsing stream chunk", e);
            }
          }
        }
      }
    } catch (err) {
      console.error("Chat Error:", err);
      setMessages(prev => [...prev, {
        type: 'bot',
        content: `Connection Error: ${err.message || 'The Houser Backend is currently unreachable.'}`,
        messageType: 'error',
        timestamp: new Date()
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = async () => {
    try {
      // Clear server-side cache
      await fetch(`${process.env.REACT_APP_API_URL}/api/clear-cache`, { method: 'POST' });
    } catch (err) {
      console.error('Failed to clear server cache:', err);
    }

    setMessages([{
      type: 'bot',
      content: 'Hello, I have cleared our previous session. I am your elite real estate advisor, ready to start a fresh discovery. What can I analyze for you today?',
      timestamp: new Date()
    }]);
    setSessionContext({});
    setInput('');
    setLoading(false);
    setLoadingStatus('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const renderBotContent = (msg) => {
    if (!msg.content) return null;

    // If the AI returned a numbered list or multiple price entries, render as bullets
    const hasNumbered = /\d+\./.test(msg.content);
    const priceMatches = (msg.content.match(/AED\s?[0-9,]+/gi) || []);
    if (msg.results && (hasNumbered || priceMatches.length >= 2)) {
      // split on numbered markers OR before each AED price
      const rawParts = msg.content.split(/(?=\d+\.\s*)|(?=AED\s?[0-9,]+)/i);
      const parts = rawParts.map(p => p.replace(/^\d+\.\s*/, '').trim()).filter(p => p.length > 0);
      return (
        <div className="bot-list">
          <ul>
            {parts.map((p, i) => {
              const cleanedContent = p.replace(/\*\*/g, '');
              return <li key={i} dangerouslySetInnerHTML={{ __html: cleanedContent }} />;
            })}
          </ul>
        </div>
      );
    }

    // fallback: plain paragraph
    return <p>{msg.content}</p>;
  };

  const formatAED = (n) => {
    if (n === null || n === undefined || n === '') return 'AED N/A';
    // If it's already a number
    if (typeof n === 'number') return `AED ${Math.round(n).toLocaleString()}`;
    // If it's a string like 'AED 170,000' or '170,000', strip non-numeric chars
    const cleaned = String(n).replace(/[^0-9.-]+/g, '');
    const num = cleaned === '' ? NaN : Number(cleaned);
    if (isNaN(num)) return 'AED N/A';
    return `AED ${Math.round(num).toLocaleString()}`;
  };

  const extractFeatures = (p) => {
    // Prefer explicit key_features field
    if (p.key_features) {
      if (Array.isArray(p.key_features)) return p.key_features.slice(0, 2);
      if (typeof p.key_features === 'string') {
        return p.key_features.split(/[,;|/]+/).map(s => s.trim()).filter(Boolean).slice(0, 2);
      }
    }
    // Fallback: take first two comma-separated phrases from description
    if (p.description) {
      const parts = p.description.split(/[.\n]+/)[0].split(/[,;|]+/).map(s => s.trim()).filter(Boolean);
      return parts.slice(0, 2);
    }
    return [];
  };

  const renderStructuredResponse = (msg) => {
    const results = msg.results || [];
    if (!results || results.length === 0) return null;

    // 1) Retrieved Listings (Summary)
    const bullets = results.map((r) => {
      const title = r.title || r.property_name || 'Untitled';
      const location = r.location || r.area || r.city || 'Unknown Location';
      const price = formatAED(r.price);
      const beds = (r.beds === 'Studio' || String(r.beds).toLowerCase() === 'studio') ? 'Studio' : `${r.beds || r.bedrooms || 'N/A'}BR`;
      const feats = extractFeatures(r).slice(0,2);
      const featText = feats.length ? ` – ${feats.join(', ')}` : '';
      return `${title} – ${location} – ${price} – ${beds}${featText}`;
    });

    // 2) Key Highlights: use msg.keyHighlights if provided, else compute
    let highlights = msg.keyHighlights;
    if (!highlights) {
      const prices = results.map(r=> Number(r.price) || 0).filter(v=>v>0);
      const count = results.length;
      const avg = prices.length ? Math.round(prices.reduce((a,b)=>a+b,0)/prices.length) : 0;
      const low = prices.length ? Math.min(...prices) : 0;
      const high = prices.length ? Math.max(...prices) : 0;
      highlights = {
        count,
        avg_price: avg,
        lowest_price: low,
        highest_price: high
      };
    }

    return (
      <div>
        <div className="retrieved-summary">
          <h4>Retrieved Listings (Summary)</h4>
          <ul>
            {bullets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>

        <div className="compact-highlights">
          <h4>Key Highlights</h4>
          <div>
            Listings: {highlights.count}  <br/>
            Average Price: {formatAED(highlights.avg_price)}  <br/>
            Price Range: {formatAED(highlights.lowest_price)} – {formatAED(highlights.highest_price)}
          </div>
        </div>
      </div>
    );
  };

  const suggestedQueries = [
    'Summary table of these results',
    'Apartments in Dubai Marina < 1.5M',
    'Villas in Palm Jumeirah for sale',
    '3BR in JLT for rent',
    'Market stats for Business Bay'
  ];

  return (
    <div className="app-container">
      {/* Sidebar - Pro Design */}
      <aside className="sidebar">
        <div className="sidebar-top">
          <button className="new-chat-btn" onClick={handleNewChat}>
            <span>+</span> New chat
          </button>
        </div>

        <nav className="history-list">
          <div className="history-item active">
            <span>💬</span> Kamran's Real Estate Advisor
          </div>
        </nav>

        <div className="sidebar-bottom">
          <div className="user-profile">
            <div className="user-avatar">K</div>
            <div className="user-info">
              <span className="user-name">Kamran</span>
              <span className="user-email">Real Estate Expert</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="main-header">
          <div className="bot-identity">
            <div className="bot-logo">💎</div>
            <h2>Houser AI</h2>
          </div>
        </header>

        <PropertyModal property={selectedProperty} onClose={() => setSelectedProperty(null)} />

        <div className="messages-area" id="scroll-target">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-row ${msg.type === 'bot' ? 'bot-row' : 'user-row'}`}>
              {msg.type === 'bot' && <div className="bot-avatar">💎</div>}
              <div className="chat-bubble">
                {(msg.results && msg.results.length > 0) ? (
                  renderStructuredResponse(msg)
                ) : (
                  renderBotContent(msg)
                )}

                

                {msg.results && msg.results.length > 0 && (
                  <div className="properties-grid">
                    {msg.results.map((property, i) => (
                      <div key={i} className={`property-card ${!property.isExactMatch ? 'supplemental' : ''}`} onClick={() => setSelectedProperty(property)}>
                        <div className="card-img">
                          <img src={property.thumbnail || 'https://images.unsplash.com/photo-1582407947304-fd86f028f716?auto=format&w=800&q=80'} alt={property.title} />
                          <div className="type-tag">{property.type?.toUpperCase()}</div>
                          {!property.isExactMatch && <div className="nearby-tag">🌍 PREMIUM RECOMMENDED</div>}
                        </div>
                        <div className="card-content">
                          {property.priceInsight && (
                            <div className={`price-insight ${property.priceInsight.includes('Great') ? 'deal' : 'luxury'}`}>
                              {property.priceInsight}
                            </div>
                          )}
                          <div className="price-label">AED {property.price.toLocaleString()}</div>
                          <h4>{property.title}</h4>
                          <div className="card-meta">
                            <span>🛏️ {property.beds}</span>
                            <span>🚿 {property.baths}</span>
                            <span>📍 {property.area || property.city}</span>
                          </div>
                          <button className="card-btn">View Details</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {msg.tableData && msg.tableData.length > 0 && (
                  <div className="table-container">
                    <div className="table-header">
                      <span>📊</span>
                      <h4>{msg.tableTitle || 'Property Comparison Matrix'}</h4>
                    </div>
                    <div className="table-wrapper">
                      <table className="comparison-table">
                        <thead>
                          <tr>
                            {(msg.tableColumns || ['Type', 'Price (AED)', 'Beds', 'Key Feature']).map((col, i) => (
                              <th key={i}>{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {msg.tableData.map((row, i) => (
                            <tr key={i}>
                              {/* Handle both object rows and array rows for flexibility */}
                              {Array.isArray(row) ? (
                                row.map((cell, j) => <td key={j} className={j === 1 ? 'table-price' : ''}>{cell}</td>)
                              ) : (
                                <>
                                  <td>{row.type}</td>
                                  <td className="table-price">{row.price}</td>
                                  <td>{row.beds}</td>
                                  <td>{row.feature}</td>
                                </>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {msg.stats && msg.messageType === 'stats' && (
                  <div className="market-stats-card">
                    <h4>MARKET DATA INSIGHTS: {msg.stats.area?.toUpperCase()}</h4>
                    <div className="stats-strip">
                      <div className="stat-unit">
                        <label>Stock</label>
                        <span>{msg.stats.counts.total.toLocaleString()}</span>
                      </div>
                      <div className="stat-unit">
                        <label>Market Avg</label>
                        <span>AED {Math.round(msg.stats.prices.avg).toLocaleString()}</span>
                      </div>
                      <div className="stat-unit">
                        <label>Volatility</label>
                        <span>{Math.round(msg.stats.prices.min / 1000)}k - {Math.round(msg.stats.prices.max / 1000000)}M</span>
                      </div>
                      {msg.stats.prices.total_value > 0 && (
                        <div className="stat-unit highlight">
                          <label>Total Worth</label>
                          <span>AED {Math.round(msg.stats.prices.total_value / 1000000000 * 10) / 10}B</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row bot-row">
              <div className="bot-avatar">💎</div>
              <div className="chat-bubble loading">
                <div className="loader-dots">
                  <span></span><span></span><span></span>
                </div>
                <span className="status-label">{loadingStatus}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-section">
          <div className="quick-options">
            {suggestedQueries.map((query, idx) => (
              <button key={idx} onClick={() => sendMessage(query)} className="opt-chip">
                {query}
              </button>
            ))}
          </div>

          <div className="input-bar-wrapper">
            <div className="input-outer">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me about real estate in Abu Dhabi, Dubai or Sharjah..."
                rows="1"
                disabled={loading}
              />
              <button className="submit-btn" onClick={() => sendMessage()} disabled={loading || !input.trim()}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"></path>
                </svg>
              </button>
            </div>
            <p className="footer-copyright">Houser AI can make mistakes. Consider checking important information.</p>
          </div>
        </div>
      </main>
    </div>
  );
}

export default ChatApp;
