import React, { useState, useEffect, useRef } from 'react';

const PAGE_SIZE = 10;
const REFRESH_INTERVAL_MS = 10000;

export default function App() {
  const [activeTab, setActiveTab] = useState('settings'); // 'settings' | 'search' | 'info'
  const [health, setHealth] = useState({ article_count: 0, mode: '', llm_model: '', llm_active: false });
  const [settings, setSettings] = useState({ mode: 'ticker', poll_interval_sec: 600, llm_analysis_mode: 'manual', llm_analysis_concurrency: 3, active_tiers: [1, 2, 3, 4] });
  const [watchlist, setWatchlist] = useState([]);
  const [newTickerInput, setNewTickerInput] = useState('');
  const [providers, setProviders] = useState([]);
  const [feeds, setFeeds] = useState([]);
  const [pollStatus, setPollStatus] = useState(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // Search & News Panel state
  const [searchQ, setSearchQ] = useState('');
  const [watchlistChips, setWatchlistChips] = useState([]);
  const [selectedChip, setSelectedChip] = useState(null);
  const [activeView, setActiveView] = useState('latest'); // 'latest' | 'watchlist'
  const [filterDate, setFilterDate] = useState('');
  const [filterTiers, setFilterTiers] = useState([1, 2, 3, 4]);
  const [filterProvider, setFilterProvider] = useState('all');
  const [availableProviders, setAvailableProviders] = useState([]);
  
  // Articles list & local pagination
  const [articles, setArticles] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingArticles, setLoadingArticles] = useState(false);
  const [analyzingUrls, setAnalyzingUrls] = useState({}); // link -> boolean
  const [expandedThreads, setExpandedThreads] = useState({}); // threadId -> ThreadDetail object

  // Info Panel state
  const [infoTab, setInfoTab] = useState('db'); // 'db' | 'flow' | 'feeds'
  const [infoFeeds, setInfoFeeds] = useState([]);

  // Toast notifications
  const [toast, setToast] = useState(null);
  const [pollingBtnText, setPollingBtnText] = useState('Poll now');

  // Backfill tab state
  const [backfillStatus, setBackfillStatus] = useState([]);
  const [selectedBkTicker, setSelectedBkTicker] = useState(null);
  const [bkTickerNews, setBkTickerNews] = useState([]);
  const [bkNewsDateFrom, setBkNewsDateFrom] = useState('');
  const [bkNewsDateTo, setBkNewsDateTo] = useState('');
  const [bkNewsSearch, setBkNewsSearch] = useState('');
  const [loadingBkNews, setLoadingBkNews] = useState(false);
  const [backfillingTickers, setBackfillingTickers] = useState({});

  const showToast = (message) => {
    setToast(message);
    setTimeout(() => setToast(null), 4000);
  };

  const api = async (path, opts = {}) => {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch (_) {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  };

  // Load health data
  const loadHealth = async () => {
    try {
      const data = await api('/health');
      setHealth({
        article_count: data.article_count,
        mode: data.mode,
        llm_model: data.llm_model,
        llm_active: data.llm_active,
      });
    } catch (e) {
      setHealth({ article_count: 'offline', mode: 'offline', llm_model: '', llm_active: false });
    }
  };

  // Load settings
  const loadSettings = async () => {
    try {
      const data = await api('/settings');
      setSettings({
        mode: data.mode,
        poll_interval_sec: data.poll_interval_sec,
        llm_analysis_mode: data.llm_analysis_mode,
        llm_analysis_concurrency: data.llm_analysis_concurrency,
        active_tiers: data.active_tiers || [1, 2, 3, 4],
      });
    } catch (e) {
      showToast('Failed to load settings: ' + e.message);
    }
  };

  // Load watchlist
  const loadWatchlist = async () => {
    try {
      const data = await api('/watchlist/tickers');
      setWatchlist(data.tickers || []);
      setWatchlistChips(data.tickers || []);
    } catch (e) {
      showToast('Failed to load watchlist: ' + e.message);
    }
  };

  // Load providers (Yahoo, FMP etc)
  const loadProviders = async () => {
    try {
      const data = await api('/providers');
      setProviders(data.providers || []);
    } catch (e) {
      showToast('Failed to load providers: ' + e.message);
    }
  };

  // Load RSS feed checks
  const loadFeeds = async () => {
    try {
      const data = await api('/feeds?all=true');
      setFeeds(data.feeds || []);
      // Populate unique sources list for the filters drop-down
      if (data.feeds) {
        const uniqueSources = Array.from(new Set(data.feeds.map(f => f.source))).sort();
        setAvailableProviders(uniqueSources);
      }
    } catch (e) {
      showToast('Failed to load RSS feeds: ' + e.message);
    }
  };

  // Load poll status
  const loadPollStatus = async () => {
    try {
      const data = await api('/poll/status');
      setPollStatus(data);
    } catch (e) {
      // Ignore transient failures
    }
  };

  // Trigger manual poll
  const triggerPoll = async () => {
    setPollingBtnText('Polling...');
    try {
      const data = await api('/ingest/trigger', { method: 'POST' });
      const s = data.summary;
      showToast(`Ingestion complete: Inserted ${s.inserted} articles · mode ${s.mode}`);
      loadHealth();
      loadPollStatus();
    } catch (e) {
      showToast('Ingestion failed: ' + e.message);
    } finally {
      setPollingBtnText('Poll now');
    }
  };

  // Save specific settings parameters
  const updateSettingField = async (fields) => {
    try {
      const data = await api('/settings', {
        method: 'PATCH',
        body: JSON.stringify(fields),
      });
      setSettings(prev => ({ ...prev, ...data }));
      loadHealth();
    } catch (e) {
      showToast('Failed to update settings: ' + e.message);
    }
  };

  // Add Watchlist tickers
  const handleAddTickers = async () => {
    const raw = newTickerInput.trim();
    if (!raw) return;
    const tickers = raw.split(/[,\s]+/).map(t => t.trim().toUpperCase()).filter(Boolean);
    try {
      await api('/watchlist/tickers', {
        method: 'POST',
        body: JSON.stringify({ tickers }),
      });
      setNewTickerInput('');
      loadWatchlist();
      loadHealth();
    } catch (e) {
      showToast('Failed to add tickers: ' + e.message);
    }
  };

  // Delete Watchlist ticker
  const handleRemoveTicker = async (ticker) => {
    try {
      await api(`/watchlist/tickers/${encodeURIComponent(ticker)}`, {
        method: 'DELETE',
      });
      loadWatchlist();
      loadHealth();
    } catch (e) {
      showToast('Failed to remove ticker: ' + e.message);
    }
  };

  // Toggle feeds
  const handleToggleFeed = async (feedId, enabled) => {
    try {
      await api(`/feeds/${encodeURIComponent(feedId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      });
      loadFeeds();
    } catch (e) {
      showToast('Failed to toggle feed: ' + e.message);
    }
  };

  // Toggle providers
  const handleToggleProvider = async (providerId, enabled) => {
    try {
      await api(`/providers/${encodeURIComponent(providerId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      });
      loadProviders();
    } catch (e) {
      showToast('Failed to toggle provider: ' + e.message);
    }
  };

  // Fetch news articles based on filters
  const fetchFilteredNews = async () => {
    setLoadingArticles(true);
    let url = '/latest?limit=200';
    if (filterDate) {
      url += `&date=${encodeURIComponent(filterDate)}`;
    }
    if (filterProvider && filterProvider !== 'all') {
      url += `&provider=${encodeURIComponent(filterProvider)}`;
    }
    if (filterTiers.length && filterTiers.length < 4) {
      url += `&tiers=${encodeURIComponent(filterTiers.join(','))}`;
    }

    try {
      const data = await api(url);
      setArticles(data.data || []);
      setCurrentPage(1);
    } catch (e) {
      showToast('Failed to load news: ' + e.message);
    } finally {
      setLoadingArticles(false);
    }
  };

  // Fetch watchlist news
  const fetchWatchlistNews = async () => {
    setLoadingArticles(true);
    try {
      const data = await api('/watchlist/news?days=7&limit=200');
      setArticles(data.data || []);
      setCurrentPage(1);
    } catch (e) {
      showToast('Failed to load watchlist news: ' + e.message);
    } finally {
      setLoadingArticles(false);
    }
  };

  // Fetch ticker specific news (on chip click)
  const fetchTickerNews = async (symbol) => {
    setLoadingArticles(true);
    try {
      const data = await api(`/ticker/${encodeURIComponent(symbol)}?days=7&limit=200`);
      setArticles(data.data || []);
      setCurrentPage(1);
    } catch (e) {
      showToast('Failed to load ticker news: ' + e.message);
    } finally {
      setLoadingArticles(false);
    }
  };

  // Backfill: load status
  const loadBackfillStatus = async () => {
    try {
      const data = await api('/backfill/status');
      setBackfillStatus(data.backfill_status || []);
    } catch (e) {
      showToast('Failed to load backfill status: ' + e.message);
    }
  };

  // Backfill: toggle ticker
  const toggleBackfillTicker = async (ticker, enabled) => {
    try {
      await api(`/backfill/${encodeURIComponent(ticker)}/toggle`, {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      });
      loadBackfillStatus();
    } catch (e) {
      showToast('Failed to toggle backfill: ' + e.message);
    }
  };

  // Backfill: poll a background job until it finishes
  const pollBackfillJob = async (jobId) => {
    while (true) {
      await new Promise(r => setTimeout(r, 2000));
      const job = await api(`/backfill/job/${encodeURIComponent(jobId)}`);
      if (job.status === 'running') continue;
      return job;
    }
  };

  // Backfill: trigger single ticker
  const triggerBackfillSingle = async (ticker) => {
    setBackfillingTickers(prev => ({ ...prev, [ticker]: true }));
    try {
      const data = await api(`/backfill/trigger?ticker=${encodeURIComponent(ticker)}`, {
        method: 'POST',
      });
      const jobId = data.summary && data.summary.job_id;
      const job = await pollBackfillJob(jobId);
      if (job.status === 'failed') {
        showToast(`${ticker}: backfill failed (${job.error || 'unknown error'})`);
      } else {
        const result = job.results && job.results[0];
        showToast(`${ticker}: ${result?.status} (${result?.articles_fetched || 0} articles)`);
      }
      loadBackfillStatus();
    } catch (e) {
      showToast('Backfill failed: ' + e.message);
    } finally {
      setBackfillingTickers(prev => ({ ...prev, [ticker]: false }));
    }
  };

  // Backfill: trigger all enabled
  const triggerBackfillAll = async () => {
    setBackfillingTickers(prev => {
      const all = {};
      backfillStatus.forEach(s => { all[s.ticker] = true; });
      return all;
    });
    try {
      const data = await api('/backfill/trigger', { method: 'POST' });
      const jobId = data.summary && data.summary.job_id;
      const job = await pollBackfillJob(jobId);
      if (job.status === 'failed') {
        showToast(`Backfill all failed: ${job.error || 'unknown error'}`);
      } else {
        const results = job.results || [];
        const done = results.filter(r => r.status === 'completed').length;
        const total = results.length;
        showToast(`Backfill complete: ${done}/${total} tickers done`);
      }
      loadBackfillStatus();
    } catch (e) {
      showToast('Backfill all failed: ' + e.message);
    } finally {
      setBackfillingTickers({});
    }
  };

  // Backfill: fetch ticker news
  const fetchBkTickerNews = async (ticker, fromDate, toDate) => {
    setLoadingBkNews(true);
    try {
      let url = `/ticker/${encodeURIComponent(ticker)}?limit=500`;
      if (fromDate && toDate) {
        const fromTs = Math.floor(new Date(fromDate).getTime() / 1000);
        const toTs = Math.floor(new Date(toDate + 'T23:59:59').getTime() / 1000);
        url += `&from=${fromTs}&to=${toTs}`;
      } else if (fromDate) {
        url += `&from=${Math.floor(new Date(fromDate).getTime() / 1000)}`;
      } else if (toDate) {
        url += `&to=${Math.floor(new Date(toDate + 'T23:59:59').getTime() / 1000)}`;
      } else {
        url += '&days=3650';
      }
      const data = await api(url);
      let articles = data.data || [];
      if (bkNewsSearch.trim()) {
        const q = bkNewsSearch.toLowerCase();
        articles = articles.filter(a =>
          (a.headline || '').toLowerCase().includes(q) ||
          (a.summary || '').toLowerCase().includes(q)
        );
      }
      setBkTickerNews(articles);
    } catch (e) {
      showToast('Failed to load ticker news: ' + e.message);
    } finally {
      setLoadingBkNews(false);
    }
  };

  // Backfill: select ticker, load its news
  const selectBkTicker = (ticker) => {
    setSelectedBkTicker(ticker);
    setBkNewsDateFrom('');
    setBkNewsDateTo('');
    setBkNewsSearch('');
    fetchBkTickerNews(ticker, '', '');
  };

  // Trigger search query
  const handleSearch = async () => {
    const query = searchQ.trim();
    if (!query) return;
    setLoadingArticles(true);
    setSelectedChip(null);
    try {
      const data = await api(`/search?q=${encodeURIComponent(query)}&limit=200`);
      setArticles(data.data || []);
      setCurrentPage(1);
    } catch (e) {
      showToast('Search failed: ' + e.message);
    } finally {
      setLoadingArticles(false);
    }
  };

  // Run on-demand LLM Analysis
  const runLlmAnalysis = async (url) => {
    setAnalyzingUrls(prev => ({ ...prev, [url]: true }));
    try {
      const data = await api('/news/analyze', {
        method: 'POST',
        body: JSON.stringify({ url_or_id: url }),
      });
      // Replace the article object in state with the newly enriched analysis
      setArticles(prev =>
        prev.map(art =>
          art.link === url ? { ...art, llm_analysis: JSON.stringify(data.analysis) } : art
        )
      );
      showToast('Deep LLM Analysis completed.');
    } catch (e) {
      showToast('LLM Analysis failed: ' + e.message);
    } finally {
      setAnalyzingUrls(prev => ({ ...prev, [url]: false }));
    }
  };

  // Expand thread detail
  const toggleThread = async (threadId) => {
    if (expandedThreads[threadId]) {
      setExpandedThreads(prev => {
        const next = { ...prev };
        delete next[threadId];
        return next;
      });
      return;
    }

    try {
      const data = await api(`/threads/${encodeURIComponent(threadId)}?limit=10`);
      setExpandedThreads(prev => ({ ...prev, [threadId]: data }));
    } catch (e) {
      showToast('Failed to fetch thread timeline: ' + e.message);
    }
  };

  // Info Tab - Feeds Loading
  const loadInfoFeeds = async () => {
    try {
      const data = await api('/feeds');
      setInfoFeeds(data.feeds || []);
    } catch (e) {
      showToast('Failed to load feeds list: ' + e.message);
    }
  };

  // Sync Watchlist from shared path
  const handleSyncWatchlist = async () => {
    try {
      const res = await api('/watchlist/sync', { method: 'POST' });
      showToast(`Watchlist synced: Added ${res.added || 0} tickers`);
      loadWatchlist();
      loadHealth();
    } catch (e) {
      showToast('Watchlist sync failed: ' + e.message);
    }
  };

  // Time counting countdown
  useEffect(() => {
    if (!pollStatus || !pollStatus.next_poll_at) return;
    const interval = setInterval(() => {
      const remaining = pollStatus.next_poll_at - Math.floor(Date.now() / 1000);
      setRemainingSeconds(remaining > 0 ? remaining : 0);
    }, 1000);
    return () => clearInterval(interval);
  }, [pollStatus]);

  // Initial load
  useEffect(() => {
    loadHealth();
    loadSettings();
    loadWatchlist();
    loadProviders();
    loadFeeds();
    loadPollStatus();
    
    const hInterval = setInterval(loadHealth, REFRESH_INTERVAL_MS);
    const pInterval = setInterval(loadPollStatus, REFRESH_INTERVAL_MS);
    return () => {
      clearInterval(hInterval);
      clearInterval(pInterval);
    };
  }, []);

  // Sync search/latest tab data fetches
  useEffect(() => {
    if (activeTab === 'search') {
      if (activeView === 'watchlist') {
        fetchWatchlistNews();
      } else {
        fetchFilteredNews();
      }
    }
  }, [activeTab, activeView, filterDate, filterTiers, filterProvider]);

  // Handle Info sub-tab switching
  useEffect(() => {
    if (activeTab === 'info') {
      if (infoTab === 'feeds') {
        loadInfoFeeds();
      } else if (infoTab === 'flow' && window.mermaid) {
        setTimeout(() => {
          try {
            window.mermaid.run({
              nodes: document.querySelectorAll('.mermaid'),
            });
          } catch (e) {
            console.error('Mermaid render error: ', e);
          }
        }, 100);
      }
    }
  }, [activeTab, infoTab]);

  // Helpers for display
  const relTime = (ts) => {
    if (!ts) return '';
    const sec = Math.floor(Date.now() / 1000 - ts);
    if (sec < 60) return 'just now';
    if (sec < 3600) return Math.floor(sec / 60) + 'm ago';
    if (sec < 86400) return Math.floor(sec / 3600) + 'h ago';
    return Math.floor(sec / 86400) + 'd ago';
  };

  const formatClockTime = (ts) => {
    if (!ts) return '—';
    return new Date(ts * 1000).toLocaleTimeString();
  };

  const renderLlmColumn = (art) => {
    const isAnalyzing = analyzingUrls[art.link];
    if (isAnalyzing) {
      return (
        <div style={{ flex: 1, padding: '1.5rem', background: '#1e1b4b', border: '1px dashed #4f46e5', borderRadius: '8px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', minHeight: '120px' }}>
          <span style={{ fontSize: '0.85rem', color: '#818cf8', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <svg className="animate-spin" viewBox="0 0 50 50" style={{ width: '16px', height: '16px', stroke: '#818cf8', fill: 'none', strokeWidth: 5, strokeLinecap: 'round' }}>
              <circle cx="25" cy="25" r="20"></circle>
            </svg>
            Analyzing with LLM...
          </span>
        </div>
      );
    }

    if (art.llm_analysis) {
      try {
        const parsed = JSON.parse(art.llm_analysis);
        return (
          <div style={{ flex: 1, padding: '1rem 1.25rem', background: 'rgba(109, 40, 217, 0.05)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '8px', fontSize: '0.85rem', color: '#ddd' }}>
            <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', fontWeight: 700, color: '#c084fc', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              🧠 Deep LLM Analysis
            </h4>
            <p style={{ margin: '0 0 0.75rem 0', lineHeight: 1.5, color: '#e5e7eb' }}>{parsed.summary || ""}</p>
            <div style={{ fontSize: '0.78rem', color: '#a78bfa', fontWeight: 600, display: 'flex', flexDirection: 'column', gap: '0.35rem', borderTop: '1px dashed rgba(167, 139, 250, 0.3)', paddingTop: '0.5rem' }}>
              <div>Sentiment Score: <strong style={{ color: '#fff' }}>{parsed.sentiment_score}</strong></div>
              <div>Confidence: <strong style={{ color: '#fff' }}>{parsed.confidence}%</strong></div>
              {parsed.risk_flags && parsed.risk_flags.length ? (
                <div>Risk Flags: <span style={{ color: '#f43f5e' }}>{parsed.risk_flags.join(', ')}</span></div>
              ) : null}
            </div>
          </div>
        );
      } catch (e) {
        console.error("Failed to parse llm_analysis JSON:", e);
      }
    }

    return (
      <div style={{ flex: 1, padding: '1.5rem', background: 'rgba(255, 255, 255, 0.02)', border: '1px dashed var(--border-color)', borderRadius: '8px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', minHeight: '120px' }}>
        <span style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>🧠</span>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '0.75rem' }}>No LLM analysis cached for this article</span>
        <button
          className="btn-primary"
          style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
          onClick={() => runLlmAnalysis(art.link)}
        >
          Run LLM Analysis
        </button>
      </div>
    );
  };

  // Pagination bounds
  const totalArticles = articles.length;
  const totalPages = Math.max(1, Math.ceil(totalArticles / PAGE_SIZE));
  const activePage = Math.min(currentPage, totalPages);
  const pagedArticles = articles.slice((activePage - 1) * PAGE_SIZE, activePage * PAGE_SIZE);

  return (
    <div className="wrap" style={{ maxWidth: '1200px', margin: '0 auto', padding: '1.5rem 1rem' }}>
      {/* Toast Alert */}
      {toast && (
        <div className="animate-fade-in" style={{ position: 'fixed', bottom: '1.5rem', left: '50%', transform: 'translateX(-50%)', background: '#312e81', border: '1px solid #4f46e5', color: '#e0e7ff', padding: '0.75rem 1.5rem', borderRadius: '8px', fontSize: '0.9rem', boxShadow: 'var(--shadow-xl)', zIndex: 1000, fontWeight: 600 }}>
          {toast}
        </div>
      )}

      {/* Header bar */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '2rem' }}>⚡</span>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0, letterSpacing: '-0.025em', background: 'linear-gradient(to right, #fff, #9ca3af)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              vinu-news
            </h1>
            <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-dim)' }}>Core Financial Ingester Dashboard</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className={`health ${health.mode === 'offline' ? 'err' : 'ok'}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem', borderRadius: '999px', background: health.mode === 'offline' ? 'var(--danger-bg)' : 'var(--success-bg)', color: health.mode === 'offline' ? 'var(--danger)' : 'var(--success)', fontWeight: 600, border: `1px solid ${health.mode === 'offline' ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}` }}>
            {health.article_count} articles · {health.mode}
          </span>
          {health.llm_model && (
            <span className={`health ${health.llm_active ? 'ok' : 'err'}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem', borderRadius: '999px', background: health.llm_active ? 'var(--success-bg)' : 'var(--danger-bg)', color: health.llm_active ? 'var(--success)' : 'var(--danger)', fontWeight: 600, border: `1px solid ${health.llm_active ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
              LLM: {health.llm_model} · {health.llm_active ? 'active' : 'unavailable'}
            </span>
          )}
        </div>
      </header>

      {/* Tabs */}
      <nav className="tabs" style={{ display: 'flex', gap: '0.25rem', borderBottom: '1px solid var(--border-color)', marginBottom: '1.5rem', paddingBottom: '1px' }}>
        <button
          type="button"
          className={`info-menu-btn ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
          style={{ padding: '0.75rem 1.25rem', border: 'none', background: 'none', cursor: 'pointer', fontSize: '0.95rem', fontWeight: activeTab === 'settings' ? 700 : 500, color: activeTab === 'settings' ? 'var(--primary)' : 'var(--text-muted)', borderBottom: `2px solid ${activeTab === 'settings' ? 'var(--primary)' : 'transparent'}`, transition: 'all 0.2s ease', outline: 'none' }}
        >
          ⚙️ Settings
        </button>
        <button
          type="button"
          className={`info-menu-btn ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
          style={{ padding: '0.75rem 1.25rem', border: 'none', background: 'none', cursor: 'pointer', fontSize: '0.95rem', fontWeight: activeTab === 'search' ? 700 : 500, color: activeTab === 'search' ? 'var(--primary)' : 'var(--text-muted)', borderBottom: `2px solid ${activeTab === 'search' ? 'var(--primary)' : 'transparent'}`, transition: 'all 0.2s ease', outline: 'none' }}
        >
          🔍 Search &amp; News
        </button>
        <button
          type="button"
          className={`info-menu-btn ${activeTab === 'info' ? 'active' : ''}`}
          onClick={() => setActiveTab('info')}
          style={{ padding: '0.75rem 1.25rem', border: 'none', background: 'none', cursor: 'pointer', fontSize: '0.95rem', fontWeight: activeTab === 'info' ? 700 : 500, color: activeTab === 'info' ? 'var(--primary)' : 'var(--text-muted)', borderBottom: `2px solid ${activeTab === 'info' ? 'var(--primary)' : 'transparent'}`, transition: 'all 0.2s ease', outline: 'none' }}
        >
          📂 Information
        </button>
        <button
          type="button"
          className={`info-menu-btn ${activeTab === 'backfill' ? 'active' : ''}`}
          onClick={() => { setActiveTab('backfill'); loadBackfillStatus(); }}
          style={{ padding: '0.75rem 1.25rem', border: 'none', background: 'none', cursor: 'pointer', fontSize: '0.95rem', fontWeight: activeTab === 'backfill' ? 700 : 500, color: activeTab === 'backfill' ? 'var(--primary)' : 'var(--text-muted)', borderBottom: `2px solid ${activeTab === 'backfill' ? 'var(--primary)' : 'transparent'}`, transition: 'all 0.2s ease', outline: 'none' }}
        >
          📥 Backfill
        </button>
      </nav>

      {/* PANEL: SETTINGS */}
      {activeTab === 'settings' && (
        <div className="animate-fade-in" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.25rem' }}>
          {/* Mode configuration */}
          <div className="glass-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              🎯 Collection Mode
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500 }}>
                <input
                  type="radio"
                  name="settings-mode"
                  value="ticker"
                  checked={settings.mode === 'ticker'}
                  onChange={() => updateSettingField({ mode: 'ticker' })}
                  style={{ width: '16px', height: '16px', accentColor: 'var(--primary)' }}
                />
                Ticker only — save watchlist matches
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500 }}>
                <input
                  type="radio"
                  name="settings-mode"
                  value="all"
                  checked={settings.mode === 'all'}
                  onChange={() => updateSettingField({ mode: 'all' })}
                  style={{ width: '16px', height: '16px', accentColor: 'var(--primary)' }}
                />
                All news — save everything from RSS
              </label>
            </div>
            
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              Poll interval (seconds, min 60)
            </label>
            <input
              type="number"
              min="60"
              value={settings.poll_interval_sec}
              onChange={(e) => updateSettingField({ poll_interval_sec: parseInt(e.target.value, 10) })}
              style={{ width: '100%', marginBottom: '0.5rem' }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Applies after the current ingest sleep cycle ends.</span>
          </div>

          {/* LLM Configuration */}
          <div className="glass-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              🧠 Deep LLM Analysis
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500 }}>
                <input
                  type="radio"
                  name="settings-llm-mode"
                  value="auto"
                  checked={settings.llm_analysis_mode === 'auto'}
                  onChange={() => updateSettingField({ llm_analysis_mode: 'auto' })}
                  style={{ width: '16px', height: '16px', accentColor: 'var(--primary)' }}
                />
                Auto — analyze every new article in the background
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500 }}>
                <input
                  type="radio"
                  name="settings-llm-mode"
                  value="manual"
                  checked={settings.llm_analysis_mode === 'manual'}
                  onChange={() => updateSettingField({ llm_analysis_mode: 'manual' })}
                  style={{ width: '16px', height: '16px', accentColor: 'var(--primary)' }}
                />
                Manual — only analyze via "Run LLM Analysis" button
              </label>
            </div>

            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              Background analysis concurrency (1-20)
            </label>
            <input
              type="number"
              min="1"
              max="20"
              value={settings.llm_analysis_concurrency}
              onChange={(e) => updateSettingField({ llm_analysis_concurrency: parseInt(e.target.value, 10) })}
              style={{ width: '100%', marginBottom: '0.5rem' }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Max concurrent LLM queries when Auto is active.</span>
          </div>

          {/* Watchlist management */}
          <div className="glass-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              ⭐ Watchlist
            </h3>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <input
                type="text"
                placeholder="AAPL, NVDA, TSLA"
                value={newTickerInput}
                onChange={(e) => setNewTickerInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddTickers()}
                style={{ flex: 1 }}
              />
              <button type="button" className="btn-primary" onClick={handleAddTickers}>
                Add
              </button>
            </div>
            
            {/* Sync Watchlist */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>Synchronize shared watchlist files:</span>
              <button type="button" className="btn-secondary" style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }} onClick={handleSyncWatchlist}>
                🔄 Sync File
              </button>
            </div>

            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '180px', overflowY: 'auto' }}>
              {watchlist.length === 0 ? (
                <li style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No tickers in watchlist.</li>
              ) : (
                watchlist.map(ticker => (
                  <li key={ticker} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.4rem 0.6rem', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-main)' }}>{ticker}</span>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', border: '1px solid rgba(239,68,68,0.2)', color: 'var(--danger)', background: 'var(--danger-bg)' }}
                      onClick={() => handleRemoveTicker(ticker)}
                    >
                      Remove
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>

          {/* RSS Tiers, Providers and Feeds selection */}
          <div className="glass-card" style={{ gridColumn: '1 / -1' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              🔌 News Sources &amp; Configuration
            </h3>

            {/* RSS Tiers */}
            <div style={{ marginBottom: '1.25rem' }}>
              <span style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Active RSS Tiers
              </span>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {[1, 2, 3, 4].map(tier => {
                  const isActive = settings.active_tiers.includes(tier);
                  return (
                    <label key={tier} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: '0.88rem' }}>
                      <input
                        type="checkbox"
                        checked={isActive}
                        onChange={(e) => {
                          let nextTiers = [...settings.active_tiers];
                          if (e.target.checked) {
                            if (!nextTiers.includes(tier)) nextTiers.push(tier);
                          } else {
                            nextTiers = nextTiers.filter(t => t !== tier);
                          }
                          if (nextTiers.length === 0) {
                            showToast("At least one tier must remain active.");
                            return;
                          }
                          updateSettingField({ active_tiers: nextTiers });
                        }}
                        style={{ accentColor: 'var(--primary)' }}
                      />
                      Tier {tier}
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Providers */}
            <div style={{ marginBottom: '1.25rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
              <span style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Stock/Ticker News Providers
              </span>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {providers.filter(p => p.id !== 'fmp').map(provider => (
                  <label key={provider.id} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: '0.88rem' }}>
                    <input
                      type="checkbox"
                      checked={provider.enabled}
                      onChange={(e) => handleToggleProvider(provider.id, e.target.checked)}
                      style={{ accentColor: 'var(--primary)' }}
                    />
                    {provider.id.toUpperCase()}
                  </label>
                ))}
              </div>
            </div>

            {/* RSS Feeds Checklist */}
            <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
              <span style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Individual RSS Feeds
              </span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.75rem', maxHeight: '200px', overflowY: 'auto', padding: '0.25rem' }}>
                {feeds.map(feed => {
                  const isTierActive = settings.active_tiers.includes(feed.tier);
                  return (
                    <label
                      key={feed.id}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: isTierActive ? 'pointer' : 'not-allowed', fontSize: '0.85rem', opacity: isTierActive ? 1 : 0.45 }}
                    >
                      <input
                        type="checkbox"
                        checked={feed.enabled}
                        disabled={!isTierActive}
                        onChange={(e) => handleToggleFeed(feed.id, e.target.checked)}
                        style={{ accentColor: 'var(--primary)' }}
                      />
                      <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                        {feed.source} ({feed.category}, T{feed.tier})
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Ingester & Polling Status */}
          <div className="glass-card" style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
              <div>
                <h4 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  🔄 Ingester &amp; Polling Status
                </h4>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                  Monitors the background RSS polling cycles and lets you trigger an ingestion run manually.
                </p>
              </div>
              <button type="button" className="btn-primary" onClick={triggerPoll} disabled={pollingBtnText === 'Polling...'}>
                {pollingBtnText === 'Polling...' ? 'Polling...' : 'Poll now'}
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
              {/* Next Poll */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                  NEXT AUTOMATIC POLL
                </span>
                {pollStatus && pollStatus.next_poll_at ? (
                  <div>
                    <strong style={{ fontSize: '1.15rem', color: 'var(--primary)' }}>
                      {formatClockTime(pollStatus.next_poll_at)}
                    </strong>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                      ({remainingSeconds > 0 ? `in ${remainingSeconds}s` : 'due now'})
                    </span>
                  </div>
                ) : (
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>— (Continuous ingester running?)</span>
                )}
              </div>

              {/* Last Poll Stats */}
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <span style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                  LAST POLL STATS
                </span>
                {pollStatus && pollStatus.last_poll_finished_at ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', fontSize: '0.85rem' }}>
                    <div style={{ color: 'var(--text-dim)' }}>
                      Finished at: <strong style={{ color: 'var(--text-main)' }}>{formatClockTime(pollStatus.last_poll_finished_at)}</strong>
                    </div>
                    <div>
                      Total articles fetched: <strong style={{ color: 'var(--info)' }}>{pollStatus.last_raw_count ?? 0}</strong>
                    </div>
                    <div>
                      Saved (added to DB): <strong style={{ color: 'var(--success)' }}>{pollStatus.last_inserted ?? 0}</strong>
                    </div>
                  </div>
                ) : (
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No poll history recorded yet.</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PANEL: SEARCH & NEWS */}
      {activeTab === 'search' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="glass-card">
            {/* Search Input bar */}
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <input
                type="text"
                placeholder="Search article headlines..."
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                style={{ flex: 1 }}
              />
              <button type="button" className="btn-primary" onClick={handleSearch}>
                Search
              </button>
            </div>

            {/* Watchlist Chips */}
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Filter by watchlist symbol:
              </label>
              <div className="chips">
                {watchlistChips.length === 0 ? (
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No watchlist tickers.</span>
                ) : (
                  watchlistChips.map(chip => (
                    <button
                      key={chip}
                      type="button"
                      className={`chip ${selectedChip === chip ? 'active' : ''}`}
                      onClick={() => {
                        if (selectedChip === chip) {
                          setSelectedChip(null);
                          fetchFilteredNews();
                        } else {
                          setSelectedChip(chip);
                          fetchTickerNews(chip);
                        }
                      }}
                    >
                      {chip}
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Toggle view & Filters */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-color)', paddingTop: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div className="view-toggle">
                <button
                  type="button"
                  className={`btn-secondary ${activeView === 'watchlist' ? 'active' : ''}`}
                  onClick={() => {
                    setActiveView('watchlist');
                    setSelectedChip(null);
                  }}
                >
                  All watchlist
                </button>
                <button
                  type="button"
                  className={`btn-secondary ${activeView === 'latest' ? 'active' : ''}`}
                  onClick={() => {
                    setActiveView('latest');
                    setSelectedChip(null);
                  }}
                >
                  Latest News
                </button>
              </div>

              {/* Advanced filters */}
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                {/* Date */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <label htmlFor="news-date-filter" style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>Date:</label>
                  <input
                    type="date"
                    id="news-date-filter"
                    value={filterDate}
                    onChange={(e) => setFilterDate(e.target.value)}
                    style={{
                      fontSize: '0.8rem',
                      padding: '0.25rem 0.5rem',
                      background: 'rgba(255, 255, 255, 0.05)',
                      color: 'var(--text-main)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      colorScheme: 'dark',
                      outline: 'none'
                    }}
                  />
                </div>
                {/* Tier check list */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>Tiers:</span>
                  {[1, 2, 3, 4].map(tier => (
                    <label key={tier} style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.2rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={filterTiers.includes(tier)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setFilterTiers(prev => [...prev, tier]);
                          } else {
                            setFilterTiers(prev => prev.filter(t => t !== tier));
                          }
                        }}
                      />
                      T{tier}
                    </label>
                  ))}
                </div>
                {/* Provider Select */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <label htmlFor="news-provider-filter" style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>Provider:</label>
                  <select
                    id="news-provider-filter"
                    value={filterProvider}
                    onChange={(e) => setFilterProvider(e.target.value)}
                    style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', background: '#111827' }}
                  >
                    <option value="all">All Providers</option>
                    {availableProviders.map(src => (
                      <option key={src} value={src.toLowerCase()}>{src}</option>
                    ))}
                  </select>
                </div>
                
                {/* Clear filters */}
                <button
                  type="button"
                  onClick={() => {
                    setFilterDate('');
                    setFilterProvider('all');
                    setFilterTiers([1, 2, 3, 4]);
                    setSearchQ('');
                  }}
                  style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', padding: '0.25rem 0.5rem', borderRadius: '6px', fontSize: '0.78rem', cursor: 'pointer', color: 'var(--text-muted)' }}
                >
                  Reset
                </button>
              </div>
            </div>
          </div>

          {/* Results list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {loadingArticles ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 0', color: 'var(--text-dim)' }}>
                <svg className="animate-spin" viewBox="0 0 50 50" style={{ width: '32px', height: '32px', stroke: 'var(--primary)', fill: 'none', strokeWidth: 4, strokeLinecap: 'round', marginBottom: '1rem' }}>
                  <circle cx="25" cy="25" r="20"></circle>
                </svg>
                Loading articles...
              </div>
            ) : pagedArticles.length === 0 ? (
              <div className="glass-card" style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '2rem' }}>No articles found.</div>
            ) : (
              pagedArticles.map(art => (
                <article key={art.id} className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
                    <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.4 }}>
                      {art.headline}
                    </h3>
                    {art.thread_id && (
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', background: 'var(--info-bg)', color: 'var(--info)', borderColor: 'rgba(59,130,246,0.2)' }}
                        onClick={() => toggleThread(art.thread_id)}
                      >
                        🧵 {expandedThreads[art.thread_id] ? 'Hide Thread' : 'View Thread'}
                      </button>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1rem', fontSize: '0.78rem', color: 'var(--text-dim)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                    <span>{art.source}</span>
                    <span>•</span>
                    <span>{art.region}</span>
                    <span>•</span>
                    <span>{relTime(art.sort_ts)}</span>
                    {art.impact && (
                      <>
                        <span>•</span>
                        <span style={{ fontWeight: 700, color: art.impact === 'HIGH' ? 'var(--danger)' : art.impact === 'MEDIUM' ? 'var(--warning)' : 'var(--text-dim)' }}>
                          Impact: {art.impact}
                        </span>
                      </>
                    )}
                    {art.tickers && (
                      <>
                        <span>•</span>
                        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--primary)', fontWeight: 600 }}>{JSON.parse(art.tickers).join(', ')}</span>
                      </>
                    )}
                  </div>

                  {/* Grouped story threads display */}
                  {art.thread_id && expandedThreads[art.thread_id] && (
                    <div className="animate-fade-in" style={{ background: 'rgba(59,130,246,0.02)', border: '1px solid rgba(59,130,246,0.2)', padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '0.5rem' }}>
                      <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.82rem', color: 'var(--info)' }}>
                        Story Thread: {expandedThreads[art.thread_id].lead_headline}
                      </h4>
                      <ul style={{ paddingLeft: '1.2rem', margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        {expandedThreads[art.thread_id].articles && expandedThreads[art.thread_id].articles.map(child => (
                          <li key={child.id}>
                            <a href={child.link} target="_blank" rel="noopener" style={{ color: 'var(--text-main)', textDecoration: 'none' }}>
                              {child.headline}
                            </a>
                            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem', marginLeft: '0.5rem' }}>({child.source} · {relTime(child.sort_ts)})</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    {/* Raw & Rule analysis */}
                    <div style={{ flex: 1, minWidth: '300px', background: 'rgba(255,255,255,0.01)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                      <div>
                        <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.82rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          ⚙️ Raw &amp; Rule Analysis
                        </h4>
                        {art.summary ? (
                          <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.85rem', color: '#cbd5e1', lineHeight: 1.4 }}>{art.summary}</p>
                        ) : (
                          <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.85rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No raw summary provided.</p>
                        )}
                      </div>
                      
                      <div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(135px, 1fr))', gap: '0.5rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          <div>Priority: <strong style={{ color: '#fff' }}>{art.priority || 'ROUTINE'}</strong></div>
                          <div>Sentiment: <strong style={{ color: art.sentiment === 'BULLISH' ? 'var(--success)' : art.sentiment === 'BEARISH' ? 'var(--danger)' : '#fff' }}>{art.sentiment || 'NEUTRAL'}</strong></div>
                          <div>Impact Level: <strong style={{ color: '#fff' }}>{art.impact || 'LOW'}</strong></div>
                          <div>Category: <strong style={{ color: '#fff' }}>{art.category || 'MARKETS'}</strong></div>
                          <div>Threat Level: <strong style={{ color: '#fff' }}>{art.threat_level || 'INFO'}</strong></div>
                          <div>Threat Cat: <strong style={{ color: '#fff' }}>{art.threat_cat || 'general'}</strong></div>
                        </div>
                        {art.entities_json && art.entities_json !== '{}' && (
                          <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px dashed var(--border-color)', fontSize: '0.75rem', color: 'var(--text-dim)', lineHeight: 1.4 }}>
                            {JSON.parse(art.entities_json).people?.length ? (
                              <div>People: <strong style={{ color: 'var(--text-muted)' }}>{JSON.parse(art.entities_json).people.join(', ')}</strong></div>
                            ) : null}
                            {JSON.parse(art.entities_json).countries?.length ? (
                              <div>Countries: <strong style={{ color: 'var(--text-muted)' }}>{JSON.parse(art.entities_json).countries.join(', ')}</strong></div>
                            ) : null}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* LLM analysis column */}
                    <div style={{ flex: 1, minWidth: '300px', display: 'flex', flexDirection: 'column' }}>
                      {renderLlmColumn(art)}
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '0.8rem', marginTop: '0.25rem' }}>
                    <a href={art.link} target="_blank" rel="noopener" style={{ color: 'var(--primary)', textDecoration: 'none', fontWeight: 600 }}>Open Source Article →</a>
                  </div>
                </article>
              ))
            )}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', margin: '1rem 0' }}>
              <button
                type="button"
                className="btn-secondary"
                disabled={activePage <= 1}
                onClick={() => {
                  setCurrentPage(activePage - 1);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
              >
                Back
              </button>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Page
                <input
                  type="number"
                  min="1"
                  max={totalPages}
                  value={activePage}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val)) setCurrentPage(val);
                  }}
                  style={{ width: '60px', textAlign: 'center', background: '#111827', border: '1px solid var(--border-color)' }}
                />
                of {totalPages}
              </span>
              <button
                type="button"
                className="btn-secondary"
                disabled={activePage >= totalPages}
                onClick={() => {
                  setCurrentPage(activePage + 1);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {/* PANEL: BACKFILL */}
      {activeTab === 'backfill' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Global settings + actions */}
          <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 0.25rem 0' }}>📥 Alpaca Historical Backfill</h3>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                Backfill period: <strong>{settings.backfill_start_date || '2023-01-01'}</strong> onward &middot; Pause on error: <strong>{settings.backfill_pause_on_error !== false ? 'ON' : 'OFF'}</strong>
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn-primary" onClick={() => { triggerBackfillAll(); }}>
                Backfill All Now
              </button>
              <button type="button" className="btn-secondary" onClick={loadBackfillStatus}>
                🔄 Refresh
              </button>
            </div>
          </div>

          {/* Status table */}
          <div className="glass-card" style={{ overflowX: 'auto', padding: 0 }}>
            {backfillStatus.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-dim)' }}>
                No backfill entries yet. Add tickers to the watchlist to start.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', minWidth: '650px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.78rem' }}>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'center', width: '40px' }}>On</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'left' }}>Ticker</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'center' }}>Status</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Articles</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Up To</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Oldest</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'center', width: '100px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {backfillStatus.map(bs => {
                    const isBusy = backfillingTickers[bs.ticker];
                    const statusStyles = {
                      pending: { bg: 'rgba(255,255,255,0.03)', color: 'var(--text-dim)' },
                      in_progress: { bg: 'rgba(59,130,246,0.1)', color: '#60a5fa' },
                      completed: { bg: 'rgba(16,185,129,0.1)', color: '#34d399' },
                      paused: { bg: 'rgba(234,179,8,0.1)', color: '#facc15' },
                      error: { bg: 'rgba(239,68,68,0.1)', color: '#f87171' },
                    }[bs.status] || { bg: 'rgba(255,255,255,0.02)', color: 'var(--text-dim)' };
                    return (
                      <tr key={bs.ticker} style={{ borderBottom: '1px solid var(--border-color)', cursor: 'pointer', transition: 'background 0.15s', background: selectedBkTicker === bs.ticker ? 'rgba(59,130,246,0.05)' : 'transparent' }}
                        onClick={() => selectBkTicker(bs.ticker)}
                      >
                        <td style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                          <input type="checkbox" checked={bs.enabled} onChange={e => toggleBackfillTicker(bs.ticker, e.target.checked)} style={{ accentColor: 'var(--primary)', cursor: 'pointer' }} />
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', fontWeight: 700, color: 'var(--primary)' }}>{bs.ticker}</td>
                        <td style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }}>
                          <span style={{ display: 'inline-block', padding: '0.15rem 0.6rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, background: statusStyles.bg, color: statusStyles.color }}>
                            {bs.status === 'in_progress' ? '⏳' : bs.status === 'completed' ? '✅' : bs.status === 'error' ? '❌' : bs.status === 'paused' ? '⏸' : '🟡'} {bs.status}
                          </span>
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{bs.article_count?.toLocaleString() || 0}</td>
                        <td style={{ padding: '0.6rem 0.5rem', textAlign: 'right', color: 'var(--text-dim)', fontSize: '0.78rem' }}>
                          {bs.backfilled_up_to_ts ? new Date(bs.backfilled_up_to_ts * 1000).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', textAlign: 'right', color: 'var(--text-dim)', fontSize: '0.78rem' }}>
                          {bs.oldest_ts ? new Date(bs.oldest_ts * 1000).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                          <button type="button" className="btn-secondary" style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
                            disabled={isBusy}
                            onClick={() => triggerBackfillSingle(bs.ticker)}
                          >
                            {isBusy ? '⏳' : '▶'} Backfill
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Ticker news viewer (shown when ticker selected) */}
          {selectedBkTicker && (
            <div className="glass-card animate-fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
                  📰 {selectedBkTicker} News
                  <span style={{ fontSize: '0.85rem', fontWeight: 400, color: 'var(--text-dim)', marginLeft: '0.5rem' }}>
                    ({bkTickerNews.length} articles)
                  </span>
                </h3>
                <button type="button" className="btn-secondary" style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
                  onClick={() => { setSelectedBkTicker(null); setBkTickerNews([]); }}
                >
                  ✕ Close
                </button>
              </div>

              {/* Filter bar */}
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1rem', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)' }}>From:</label>
                <input type="date" value={bkNewsDateFrom} onChange={e => setBkNewsDateFrom(e.target.value)}
                  style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', background: '#111827', color: 'var(--text-main)', border: '1px solid var(--border-color)', borderRadius: '4px', colorScheme: 'dark' }} />
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)' }}>To:</label>
                <input type="date" value={bkNewsDateTo} onChange={e => setBkNewsDateTo(e.target.value)}
                  style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', background: '#111827', color: 'var(--text-main)', border: '1px solid var(--border-color)', borderRadius: '4px', colorScheme: 'dark' }} />
                <input type="text" placeholder="Search in headline/summary..." value={bkNewsSearch}
                  onChange={e => setBkNewsSearch(e.target.value)}
                  style={{ flex: 1, minWidth: '150px', fontSize: '0.8rem', padding: '0.25rem 0.5rem' }} />
                <button type="button" className="btn-primary" style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }}
                  onClick={() => fetchBkTickerNews(selectedBkTicker, bkNewsDateFrom, bkNewsDateTo)}
                >
                  Apply
                </button>
                <button type="button" className="btn-secondary" style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }}
                  onClick={() => { setBkNewsDateFrom(''); setBkNewsDateTo(''); setBkNewsSearch(''); fetchBkTickerNews(selectedBkTicker, '', ''); }}
                >
                  Reset
                </button>
              </div>

              {/* News results */}
              {loadingBkNews ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-dim)' }}>Loading...</div>
              ) : bkTickerNews.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-dim)' }}>No articles found for this ticker.</div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', minWidth: '500px' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.75rem' }}>
                        <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>#</th>
                        <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Headline</th>
                        <th style={{ padding: '0.5rem 0.4rem', textAlign: 'left' }}>Source</th>
                        <th style={{ padding: '0.5rem 0.4rem', textAlign: 'center' }}>Date</th>
                        <th style={{ padding: '0.5rem 0.4rem', textAlign: 'center' }}>Sentiment</th>
                        <th style={{ padding: '0.5rem 0.4rem', textAlign: 'center' }}>Link</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bkTickerNews.slice(0, 200).map((art, idx) => (
                        <tr key={art.id || idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <td style={{ padding: '0.4rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{idx + 1}</td>
                          <td style={{ padding: '0.4rem', fontWeight: 500, maxWidth: '350px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <span title={art.headline}>{art.headline}</span>
                          </td>
                          <td style={{ padding: '0.4rem', color: 'var(--text-dim)', fontSize: '0.75rem' }}>{art.source}</td>
                          <td style={{ padding: '0.4rem', textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                            {art.sort_ts ? new Date(art.sort_ts * 1000).toLocaleDateString() : '—'}
                          </td>
                          <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                            <span style={{ color: art.sentiment === 'BULLISH' ? '#34d399' : art.sentiment === 'BEARISH' ? '#f87171' : 'var(--text-dim)', fontWeight: 600 }}>
                              {art.sentiment === 'BULLISH' ? '🟢' : art.sentiment === 'BEARISH' ? '🔴' : '⚪'} {art.sentiment || '—'}
                            </span>
                          </td>
                          <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                            {art.link ? (
                              <a href={art.link} target="_blank" rel="noopener" style={{ color: 'var(--primary)', fontSize: '0.75rem', textDecoration: 'none' }}>Open</a>
                            ) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {bkTickerNews.length > 200 && (
                    <div style={{ padding: '0.5rem', textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                      Showing first 200 of {bkTickerNews.length} articles. Use date filters to narrow.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* PANEL: INFORMATION */}
      {activeTab === 'info' && (
        <div className="animate-fade-in info-layout">
          {/* Left Sidebar Menu */}
          <div className="info-menu">
            <button
              type="button"
              className={infoTab === 'db' ? 'active' : ''}
              onClick={() => setInfoTab('db')}
            >
              🗄️ Database Tables
            </button>
            <button
              type="button"
              className={infoTab === 'flow' ? 'active' : ''}
              onClick={() => setInfoTab('flow')}
            >
              🔄 Full Dataflow
            </button>
            <button
              type="button"
              className={infoTab === 'feeds' ? 'active' : ''}
              onClick={() => setInfoTab('feeds')}
            >
              🔌 News Providers
            </button>
          </div>

          {/* Right Content Area */}
          <div className="info-content">
            {/* DB Info Subtab */}
            {infoTab === 'db' && (
              <div className="glass-card animate-fade-in">
                <h2 style={{ fontSize: '1.25rem', marginTop: 0, marginBottom: '0.75rem', fontWeight: 800 }}>Database Tables Information</h2>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
                  The system runs on a SQLite database containing <strong>11 logical tables</strong> (plus FTS5 search index tables). Here is a breakdown of what each table is used for:
                </p>

                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginTop: '1.5rem', marginBottom: '0.5rem', color: 'var(--primary)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.25rem' }}>1. Ingestion &amp; Content</h3>
                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.88rem', lineSpacing: '1.6', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  <li><strong>articles</strong>: Stores processed news leads (headline, summary, source, sentiment, impact, and other extraction metadata).</li>
                  <li><strong>watchlist_tickers</strong>: Contains active stock symbols being monitored (e.g. AAPL, NVDA).</li>
                  <li><strong>vinu_settings</strong>: Stores runtime configuration (e.g. collection mode, poll interval).</li>
                  <li><strong>feed_health</strong>: Monitors feed latency, success rates, failure streaks, and recent HTTP/parse errors for the 22 RSS channels.</li>
                  <li><strong>ticker_reference</strong>: Fast database-level lookup of company names and aliases from the Adanos database.</li>
                </ul>

                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginTop: '1.5rem', marginBottom: '0.5rem', color: 'var(--primary)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.25rem' }}>2. Grouping &amp; Analytics</h3>
                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.88rem', lineSpacing: '1.6', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  <li><strong>story_threads</strong>: Groups semantically similar articles together over time into unified story lines.</li>
                  <li><strong>article_ticker_mentions</strong>: A junction table mapping articles to tickers with dominance weights and primary indicators.</li>
                  <li><strong>thread_daily_snapshots</strong>: Stores daily aggregated statistics (sentiment distributions) per story thread.</li>
                  <li><strong>ticker_daily_stats</strong>: Aggregates daily metrics per ticker (total articles, bullish/bearish count).</li>
                </ul>

                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginTop: '1.5rem', marginBottom: '0.5rem', color: 'var(--primary)', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.25rem' }}>3. Enrichment &amp; Integrations</h3>
                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.88rem', lineSpacing: '1.6', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.35rem', margin: 0 }}>
                  <li><strong>news_analysis</strong>: Caches the on-demand, deep LLM analysis (sentiment, confidence score, risk flags, and summary).</li>
                  <li><strong>article_price_reaction</strong>: Tracks price differences before and after an article is published for primary tickers (integrates with stock service).</li>
                </ul>
              </div>
            )}

            {/* Flow Info Subtab */}
            {infoTab === 'flow' && (
              <div className="info-pane active">
                {/* Ingest Flow */}
                <div className="glass-card animate-fade-in" style={{ marginBottom: '1.25rem' }}>
                  <h2 style={{ fontSize: '1.25rem', marginTop: 0, marginBottom: '0.5rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    ⚙️ Ingestion &amp; Analysis Pipeline (Without LLM)
                  </h2>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem', fontStyle: 'italic' }}>
                    Deterministic rule-based ingestion. Every poll cycle runs this pipeline to process feed content quickly.
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                    <div style={{ background: 'rgba(255,255,255,0.01)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                      <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>1. Ingestion Source</strong>
                      Loads RSS feeds configured in <code>feeds.yaml</code> and queries Yahoo News via <code>run_ticker_news_ingest</code>.
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.01)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                      <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>2. Pre-Enrichment &amp; 9-Stage Rules</strong>
                      Filters batch duplicate URLs, strips HTML, and classifies:
                      <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.2rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        <li><strong>Priority</strong>: FLASH / URGENT / BREAKING / ROUTINE</li>
                        <li><strong>Sentiment</strong>: BULLISH / BEARISH / NEUTRAL</li>
                        <li><strong>Impact</strong>: HIGH / MEDIUM / LOW based on rules</li>
                        <li><strong>Category</strong>: EARNINGS, CRYPTO, DEFENSE, TECH, etc.</li>
                        <li><strong>Ticker Extraction</strong>: Database-level company name &amp; alias mapping with stop lists</li>
                        <li><strong>Threat &amp; Source Credibility</strong>: Evaluates site and content risk indicators</li>
                      </ul>
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.01)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                      <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>3. Post-Enrichment Deduplication &amp; Lead Pick</strong>
                      Performs Country &amp; Person NER. Normalizes synonyms, vectorizes headlines (TF-IDF), clusters duplicates with cosine similarity &ge; 0.25, and picks the best "Lead" article to save.
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.01)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                      <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>4. Persistence &amp; Thread Matching</strong>
                      Locks and commits raw news leads to the SQLite database (updating <code>articles</code>, FTS index, daily snapshots, and matches to existing <code>story_threads</code>).
                    </div>
                  </div>

                  <pre className="mermaid" style={{ marginTop: '1.25rem', background: '#0e131f', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
{`flowchart TD
  subgraph Ingest [Ingestion]
    Feeds[feeds.yaml RSS]
    TickerNews[Yahoo ticker news]
    Feeds --> Poll[poll_all_feeds]
    TickerNews --> TickerIngest[run_ticker_news_ingest]
    Poll --> Raw[raw articles]
    TickerIngest --> Raw
  end

  subgraph Analysis [Rule analysis - no LLM]
    Raw --> Pre[validate + url dedup]
    Pre --> Enrich[9-stage enrichment]
    Enrich --> Post[NER + cosine dedup + lead pick]
    Post --> Filter[collection filter]
    Filter --> Persist[persist_leads + threads]
  end

  subgraph Storage [SQLite]
    Persist --> Articles[(articles)]
    Persist --> Threads[(story_threads)]
    Persist --> FTS[(articles_fts)]
    Poll --> FH[(feed_health)]
  end

  subgraph API [HTTP API]
    Articles --> Routes[GET /latest /ticker /search /threads]
  end`}
                  </pre>
                </div>

                {/* LLM Flow */}
                <div className="glass-card animate-fade-in">
                  <h2 style={{ fontSize: '1.25rem', marginTop: 0, marginBottom: '0.5rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    🧠 Deep Article Analysis Pipeline (With LLM)
                  </h2>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem', fontStyle: 'italic' }}>
                    On-demand intelligence trigger. Only runs when a client asks to analyze an article's context.
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                    <div style={{ background: 'rgba(255,255,255,0.01)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                      <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>1. API Request Trigger</strong>
                      Client sends a <code>POST /news/analyze</code> containing the article ID or link. The system looks up the article in the raw <code>articles</code> table.
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.01)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                      <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>2. Cache Table Lookup</strong>
                      The system queries the <code>news_analysis</code> cache table. If a match is found and its age is within the configured TTL (e.g. 24 hours), the cached JSON result is returned immediately.
                    </div>
                    <div style={{ background: 'rgba(255,255,255,0.01)', padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                      <strong style={{ color: 'var(--text-main)', display: 'block', marginBottom: '0.25rem' }}>3. LLM API Query &amp; Cache Store</strong>
                      On a cache miss, the system formats the user prompt (injecting article details), queries the OpenAI-compatible or local Ollama service, parses and standardizes the JSON response, stores it in <code>news_analysis</code>, and returns it.
                    </div>
                  </div>

                  <pre className="mermaid" style={{ marginTop: '1.25rem', background: '#0e131f', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
{`flowchart TD
  subgraph base [Always running - section 1]
    Ingest[RSS + rule pipeline]
    Ingest --> DB[(articles)]
  end

  subgraph llm [LLM path - on demand]
    User[POST /news/analyze] --> Analyze[analyze_article]
    Analyze --> Lookup[Load article from DB]
    Lookup --> CacheHit{news_analysis cache?}
    CacheHit -->|TTL hit| Return[Return JSON]
    CacheHit -->|miss| LLM[LlmClient]
    LLM --> Ollama[Ollama / OpenAI-compatible API]
    Ollama --> Save[save_analysis]
    Save --> Return
  end

  DB --> Lookup`}
                  </pre>
                </div>
              </div>
            )}

            {/* Feeds Info Subtab */}
            {infoTab === 'feeds' && (
              <div className="glass-card animate-fade-in">
                <h2 style={{ fontSize: '1.25rem', marginTop: 0, marginBottom: '0.75rem', fontWeight: 800 }}>News Providers</h2>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
                  The following RSS news feeds are loaded from the configuration file <code>feeds.yaml</code> and polled during each ingestion cycle:
                </p>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem', textAlign: 'left', minWidth: '500px' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-muted)', fontWeight: 600 }}>
                        <th style={{ padding: '0.6rem 0.4rem' }}>ID</th>
                        <th style={{ padding: '0.6rem 0.4rem' }}>Source</th>
                        <th style={{ padding: '0.6rem 0.4rem' }}>Category</th>
                        <th style={{ padding: '0.6rem 0.4rem' }}>Region</th>
                        <th style={{ padding: '0.6rem 0.4rem' }}>Tier</th>
                        <th style={{ padding: '0.6rem 0.4rem' }}>URL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {infoFeeds.map(f => (
                        <tr key={f.id} style={{ borderBottom: '1px solid var(--border-color)', transition: 'background 0.2s ease' }}>
                          <td style={{ padding: '0.6rem 0.4rem', fontFamily: 'var(--font-mono)', fontWeight: 'bold', color: 'var(--text-muted)' }}>{f.id}</td>
                          <td style={{ padding: '0.6rem 0.4rem', color: 'var(--text-main)' }}>{f.source}</td>
                          <td style={{ padding: '0.6rem 0.4rem' }}>
                            <span style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)', padding: '0.15rem 0.4rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                              {f.category}
                            </span>
                          </td>
                          <td style={{ padding: '0.6rem 0.4rem', color: 'var(--text-dim)' }}>{f.region}</td>
                          <td style={{ padding: '0.6rem 0.4rem', color: 'var(--text-dim)' }}>Tier {f.tier}</td>
                          <td style={{ padding: '0.6rem 0.4rem', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <a href={f.url} target="_blank" rel="noopener" style={{ color: 'var(--primary)', textDecoration: 'none' }}>{f.url}</a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
