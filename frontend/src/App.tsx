import React, { useState, useEffect, useMemo } from 'react'
import {
  Search,
  Calendar,
  Trophy,
  MapPin,
  ExternalLink,
  RefreshCw,
  Clock,
  Filter,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Compass
} from 'lucide-react'
import type { CatalogResponse } from './types'

export const App: React.FC = () => {
  const [data, setData] = useState<CatalogResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Filters & Search: Default to actionable (open and upcoming) so students see real opportunities immediately
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedSource, setSelectedSource] = useState<string>('all')
  const [selectedStatus, setSelectedStatus] = useState<string>('actionable')
  const [selectedTag, setSelectedTag] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('deadline-asc')

  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      setLoading(true)
      setError(null)
      const base = import.meta.env.BASE_URL || './'
      const candidates = [
        `${base}data/hackathons.json`,
        `${base}hackathons.json`,
        './data/hackathons.json',
        './hackathons.json'
      ]

      let loaded = false
      for (const url of candidates) {
        try {
          const res = await fetch(url)
          if (res.ok) {
            const json: CatalogResponse = await res.json()
            if (!cancelled) {
              setData(json)
              loaded = true
            }
            break
          }
        } catch {
          // try next candidate
        }
      }

      if (!cancelled) {
        if (!loaded) {
          setError('Unable to load hackathons catalog. Please verify that the data file is present.')
        }
        setLoading(false)
      }
    }

    loadData()
    return () => {
      cancelled = true
    }
  }, [])

  // Collect unique tags
  const allTags = useMemo(() => {
    if (!data) return []
    const tagSet = new Set<string>()
    data.hackathons.forEach(h => {
      h.tags?.forEach(t => tagSet.add(t))
    })
    return Array.from(tagSet).sort()
  }, [data])

  // Filtered & sorted hackathons
  const filteredHackathons = useMemo(() => {
    if (!data) return []

    return data.hackathons
      .filter(item => {
        // Exclude section links from hackathon card grid
        if (item.is_section_link) return false

        // Text search
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase()
          const nameMatch = item.name.toLowerCase().includes(q)
          const descMatch = (item.description || '').toLowerCase().includes(q)
          const tagMatch = item.tags?.some(t => t.toLowerCase().includes(q))
          if (!nameMatch && !descMatch && !tagMatch) return false
        }

        // Source filter
        if (selectedSource !== 'all' && item.source.toLowerCase() !== selectedSource.toLowerCase()) {
          return false
        }

        // Status filter: Strict segregation of active opportunities vs expired/unknown
        if (selectedStatus === 'actionable') {
          if (item.status !== 'open' && item.status !== 'upcoming') return false
        } else if (selectedStatus === 'open') {
          if (item.status !== 'open') return false
        } else if (selectedStatus === 'upcoming') {
          if (item.status !== 'upcoming') return false
        } else if (selectedStatus === 'ended') {
          if (item.status !== 'ended') return false
        } else if (selectedStatus === 'unknown') {
          if (item.status !== 'unknown') return false
        }

        // Tag filter
        if (selectedTag !== 'all') {
          if (!item.tags?.includes(selectedTag)) return false
        }

        return true
      })
      .sort((a, b) => {
        if (sortBy === 'deadline-asc') {
          const da = a.deadline && a.deadline !== 'Unknown' ? a.deadline : '9999'
          const db = b.deadline && b.deadline !== 'Unknown' ? b.deadline : '9999'
          return da.localeCompare(db)
        } else if (sortBy === 'name-asc') {
          return a.name.localeCompare(b.name)
        } else if (sortBy === 'created-desc') {
          const ca = a.created_at || ''
          const cb = b.created_at || ''
          return cb.localeCompare(ca)
        }
        return 0
      })
  }, [data, searchQuery, selectedSource, selectedStatus, selectedTag, sortBy])

  const resetFilters = () => {
    setSearchQuery('')
    setSelectedSource('all')
    setSelectedStatus('actionable')
    setSelectedTag('all')
    setSortBy('deadline-asc')
  }

  // Format date helper
  const formatDeadline = (dl?: string) => {
    if (!dl || dl.toLowerCase() === 'unknown') return 'Unverified / Rolling'
    if (dl.includes('T')) {
      try {
        const d = new Date(dl)
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      } catch {
        return dl
      }
    }
    return dl
  }

  return (
    <div className="container">
      {/* Hero Header */}
      <header className="hero-header">
        <div className="hero-top-row">
          <div className="brand-badge">
            <span className="pulse-dot"></span>
            <span>Live Hackathon Ingestion Hub</span>
          </div>

          {data && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: '#94a3b8' }}>
              <Clock size={14} />
              <span>
                Updated {new Date(data.metadata.generated_at).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </span>
            </div>
          )}
        </div>

        <h1 className="hero-title">Discover Global Hackathons</h1>
        <p className="hero-subtitle">
          Real-time aggregated discovery across Devpost, Devfolio, and Unstop with verified contracts, canonical deduplication, and zero-maintenance static sync.
        </p>

        {/* Stats Summary Bar */}
        {data && (
          <div className="stats-bar">
            <div className="stat-card">
              <span className="stat-label">Active Opportunities</span>
              <span className="stat-value" style={{ color: '#34d399' }}>
                {data.metadata.active_count ?? data.hackathons.filter(h => h.status === 'open' || h.status === 'upcoming').length}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Open for Registration</span>
              <span className="stat-value" style={{ color: '#60a5fa' }}>
                {data.metadata.open_count ?? data.hackathons.filter(h => h.status === 'open').length}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Catalogued</span>
              <span className="stat-value">{data.metadata.total_count}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Platforms Monitored</span>
              <span className="stat-value">{Object.keys(data.metadata.sources || {}).length} Sources</span>
            </div>
          </div>
        )}
      </header>

      {/* Supplementary Navigation Portals (e.g. Devfolio section portals) */}
      {data?.metadata?.supplementary_links && data.metadata.supplementary_links.length > 0 && (
        <section className="supplementary-bar" aria-label="Supplementary Platform Links">
          <div className="supplementary-inner">
            <span className="supplementary-title">
              <Compass size={14} /> Official Platform Portals:
            </span>
            <div className="supplementary-links">
              {data.metadata.supplementary_links.map(link => (
                <a
                  key={link.url}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="supplementary-link"
                >
                  <span>{link.name}</span>
                  <ExternalLink size={12} />
                </a>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Control Panel: Search & Filters */}
      <section className="controls-panel" aria-label="Catalog Filters">
        <div className="search-row">
          <div className="search-input-wrapper">
            <Search size={18} />
            <input
              type="text"
              className="search-input"
              placeholder="Search hackathons by title, host, or topics..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              aria-label="Search hackathons"
            />
          </div>

          <select
            className="sort-select"
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            aria-label="Sort hackathons by"
          >
            <option value="deadline-asc">Deadline (Soonest first)</option>
            <option value="name-asc">Title (A-Z)</option>
            <option value="created-desc">Recently Discovered</option>
          </select>
        </div>

        {/* Source and Status Filter Group */}
        <div className="filter-group-row">
          <div className="pill-group">
            <span className="pill-label">Platform:</span>
            <button
              className={`filter-pill ${selectedSource === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedSource('all')}
            >
              All Sources
              {data && <span className="count-chip">{data.metadata.total_count}</span>}
            </button>
            {data &&
              Object.entries(data.metadata.sources || {}).map(([sourceName, count]) => (
                <button
                  key={sourceName}
                  className={`filter-pill ${selectedSource.toLowerCase() === sourceName.toLowerCase() ? 'active' : ''}`}
                  onClick={() => setSelectedSource(sourceName)}
                >
                  {sourceName}
                  <span className="count-chip">{count}</span>
                </button>
              ))}
          </div>

          {/* Actionable vs Historical Status Tabs */}
          <div className="pill-group">
            <span className="pill-label">Status:</span>
            <button
              className={`filter-pill ${selectedStatus === 'actionable' ? 'active' : ''}`}
              onClick={() => setSelectedStatus('actionable')}
              title="Show hackathons with active or upcoming registrations"
            >
              ⭐ Active Opportunities
            </button>
            <button
              className={`filter-pill ${selectedStatus === 'open' ? 'active' : ''}`}
              onClick={() => setSelectedStatus('open')}
            >
              Open Now
            </button>
            <button
              className={`filter-pill ${selectedStatus === 'upcoming' ? 'active' : ''}`}
              onClick={() => setSelectedStatus('upcoming')}
            >
              Opens Soon
            </button>
            <button
              className={`filter-pill ${selectedStatus === 'ended' ? 'active' : ''}`}
              onClick={() => setSelectedStatus('ended')}
            >
              Past / Closed
            </button>
            <button
              className={`filter-pill ${selectedStatus === 'unknown' ? 'active' : ''}`}
              onClick={() => setSelectedStatus('unknown')}
            >
              Unverified
            </button>
            <button
              className={`filter-pill ${selectedStatus === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedStatus('all')}
            >
              All
            </button>
          </div>
        </div>

        {/* Tag Filter Pills */}
        {allTags.length > 0 && (
          <div className="pill-group" style={{ marginTop: '0.25rem' }}>
            <span className="pill-label">Topics:</span>
            <button
              className={`filter-pill ${selectedTag === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedTag('all')}
            >
              All Topics
            </button>
            {allTags.slice(0, 10).map(tag => (
              <button
                key={tag}
                className={`filter-pill ${selectedTag === tag ? 'active' : ''}`}
                onClick={() => setSelectedTag(tag === selectedTag ? 'all' : tag)}
              >
                #{tag}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Main Hackathon Grid */}
      <main>
        {loading && (
          <div className="cards-grid" aria-busy="true">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="skeleton-card" />
            ))}
          </div>
        )}

        {error && (
          <div className="empty-state">
            <AlertCircle size={48} color="#f43f5e" />
            <h3>Catalog Sync Notice</h3>
            <p>{error}</p>
            <button className="reset-btn" onClick={() => window.location.reload()}>
              <RefreshCw size={14} style={{ display: 'inline', marginRight: '6px' }} />
              Retry Connection
            </button>
          </div>
        )}

        {!loading && !error && filteredHackathons.length === 0 && (
          <div className="empty-state">
            <Filter size={48} color="#6366f1" />
            <h3>No hackathons matched your criteria</h3>
            <p>
              {selectedStatus === 'actionable'
                ? 'No open or upcoming hackathons found for this filter. Check "Past / Closed" or "All" to view historical records.'
                : 'Try adjusting your search query, platform, or status filter.'}
            </p>
            <button className="reset-btn" onClick={resetFilters}>
              Reset Filters
            </button>
          </div>
        )}

        {!loading && !error && filteredHackathons.length > 0 && (
          <>
            <div style={{ marginBottom: '1.25rem', fontSize: '0.9rem', color: '#94a3b8' }}>
              Showing {filteredHackathons.length} hackathons{' '}
              {selectedStatus === 'actionable' && '(Active & Open Opportunities)'}
            </div>
            <div className="cards-grid">
              {filteredHackathons.map(item => (
                <article key={item.id} className="hackathon-card">
                  <div>
                    {/* Header Row: Source Badge & Dynamic Status */}
                    <div className="card-header-row">
                      <span className={`source-badge ${item.source || 'Other'}`}>{item.source}</span>
                      <span className={`status-pill ${item.status}`}>
                        {item.status === 'open' && (
                          <>
                            <CheckCircle2 size={12} /> Open for Registration
                          </>
                        )}
                        {item.status === 'upcoming' && (
                          <>
                            <Clock size={12} /> Opens Soon
                          </>
                        )}
                        {item.status === 'ended' && (
                          <>
                            <span>●</span> Registration Closed
                          </>
                        )}
                        {item.status === 'unknown' && (
                          <>
                            <HelpCircle size={12} /> Unverified Deadline
                          </>
                        )}
                      </span>
                    </div>

                    {/* Title */}
                    <h2 className="card-title">{item.name}</h2>

                    {/* Description / Host */}
                    {item.description && <p className="card-description">{item.description}</p>}
                  </div>

                  {/* Metadata Row */}
                  <div className="metadata-grid">
                    <div className="meta-item">
                      <Calendar size={15} />
                      <span>
                        Deadline: <strong>{formatDeadline(item.reg_ends_at || item.deadline)}</strong>
                      </span>
                    </div>

                    {item.starts_at && (
                      <div className="meta-item">
                        <Clock size={15} />
                        <span>
                          Event: <strong>{formatDeadline(item.starts_at)}</strong>
                        </span>
                      </div>
                    )}

                    {item.prize && item.prize !== 'Unknown' && (
                      <div className="meta-item">
                        <Trophy size={15} />
                        <span>
                          Prize: <strong style={{ color: '#fbbf24' }}>{item.prize}</strong>
                        </span>
                      </div>
                    )}

                    <div className="meta-item">
                      <MapPin size={15} />
                      <span>
                        Format: <strong>{item.location || 'Online'}</strong>
                      </span>
                    </div>
                  </div>

                  {/* Tags */}
                  {item.tags && item.tags.length > 0 && (
                    <div className="tags-container">
                      {item.tags.map(t => (
                        <span key={t} className="tag-badge">
                          #{t}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Action Link */}
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="card-action-btn"
                    aria-label={`View ${item.name} on ${item.source}`}
                  >
                    <span>
                      {item.status === 'open'
                        ? `Register on ${item.source}`
                        : item.status === 'upcoming'
                        ? `View on ${item.source}`
                        : `View Archive on ${item.source}`}
                    </span>
                    <ExternalLink size={15} />
                  </a>
                </article>
              ))}
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <div>
          <strong>Hackathon Ingestion Platform</strong> • Multi-source automated discovery engine.
        </div>
        <div>
          <span>Public Static Feed: </span>
          <a
            href="./data/hackathons.json"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#818cf8', textDecoration: 'none' }}
          >
            data/hackathons.json
          </a>
        </div>
      </footer>
    </div>
  )
}

export default App
