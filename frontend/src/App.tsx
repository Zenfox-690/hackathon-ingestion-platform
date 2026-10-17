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
  Compass,
  Gift,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  ShieldCheck,
  Sparkles
} from 'lucide-react'
import type { CatalogResponse, SpecialBenefit } from './types'

export const App: React.FC = () => {
  const [data, setData] = useState<CatalogResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedSource, setSelectedSource] = useState<string>('all')
  const [selectedStatus, setSelectedStatus] = useState<string>('actionable')
  const [selectedFormat, setSelectedFormat] = useState<string>('all')
  const [selectedTag, setSelectedTag] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('deadline-asc')

  // Expanded benefits state per hackathon card
  const [expandedBenefits, setExpandedBenefits] = useState<Record<string, boolean>>({})

  const toggleBenefits = (id: string) => {
    setExpandedBenefits(prev => ({
      ...prev,
      [id]: !prev[id]
    }))
  }

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
          const benefitMatch = item.benefits?.some(b =>
            b.name.toLowerCase().includes(q) ||
            (b.description || '').toLowerCase().includes(q)
          )
          if (!nameMatch && !descMatch && !tagMatch && !benefitMatch) return false
        }

        // Source filter
        if (selectedSource !== 'all' && item.source.toLowerCase() !== selectedSource.toLowerCase()) {
          return false
        }

        // Participation format filter
        if (selectedFormat !== 'all') {
          const itemFmt = (item.location || 'Unknown').toLowerCase()
          if (itemFmt !== selectedFormat.toLowerCase()) {
            return false
          }
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
  }, [data, searchQuery, selectedSource, selectedFormat, selectedStatus, selectedTag, sortBy])

  const resetFilters = () => {
    setSearchQuery('')
    setSelectedSource('all')
    setSelectedFormat('all')
    setSelectedStatus('actionable')
    setSelectedTag('all')
    setSortBy('deadline-asc')
  }

  // Format date helper
  const formatDeadline = (dl?: string | null) => {
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

  // Derive reference time deterministically from catalog metadata timestamp
  const referenceTime = data?.metadata?.generated_at
    ? new Date(data.metadata.generated_at).getTime()
    : 0

  // Separate evaluation for benefit application deadlines
  const evaluateBenefitDeadline = (deadlineStr?: string | null) => {
    if (!deadlineStr || deadlineStr.toLowerCase() === 'unknown') {
      return { status: 'unknown', label: 'Benefit Deadline: Not explicitly specified' }
    }
    try {
      const targetTime = new Date(deadlineStr).getTime()
      if (isNaN(targetTime)) {
        return { status: 'unknown', label: `Benefit Deadline: ${deadlineStr}` }
      }
      const diffMs = targetTime - referenceTime
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
      const formatted = new Date(deadlineStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      })

      if (diffDays < 0) {
        return { status: 'passed', label: `Benefit Application Closed (${formatted})` }
      } else if (diffDays <= 7) {
        return {
          status: 'approaching',
          label: `⚠️ Benefit Deadline Approaching: ${formatted} (${diffDays}d left)`
        }
      } else {
        return { status: 'active', label: `Benefit Deadline: ${formatted} (${diffDays}d left)` }
      }
    } catch {
      return { status: 'unknown', label: `Benefit Deadline: ${deadlineStr}` }
    }
  }

  const formatCategory = (cat: string) => {
    const map: Record<string, string> = {
      cloud_credits: 'Cloud Credits',
      api_credits: 'API Credits',
      dev_tools: 'Dev Tools',
      startup_perks: 'Startup Perks',
      general: 'Special Benefit'
    }
    return map[cat] || cat
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
          Real-time aggregated discovery across Devpost, Devfolio, and Unstop with verified contracts, participation mode filters, and sponsor benefit discovery.
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
            <div className="stat-card">
              <span className="stat-label">Special Benefits</span>
              <span className="stat-value" style={{ color: '#a78bfa' }}>
                {data.metadata.benefits_count ?? data.hackathons.reduce((acc, h) => acc + (h.benefits?.length || 0), 0)} Verified
              </span>
            </div>
          </div>
        )}
      </header>

      {/* Supplementary Navigation Portals */}
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
              placeholder="Search hackathons by title, host, credits, or topics..."
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

        {/* Participation Format Filter Group */}
        <div className="filter-group-row">
          <div className="pill-group">
            <span className="pill-label">Format:</span>
            <button
              className={`filter-pill ${selectedFormat === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedFormat('all')}
            >
              All formats
            </button>
            {(['Online', 'In-Person', 'Hybrid', 'Unknown'] as const).map(fmt => (
              <button
                key={fmt}
                className={`filter-pill ${selectedFormat === fmt ? 'active' : ''}`}
                onClick={() => setSelectedFormat(fmt)}
              >
                {fmt === 'Online' && '🌐 Online'}
                {fmt === 'In-Person' && '📍 In-person'}
                {fmt === 'Hybrid' && '⚡ Hybrid'}
                {fmt === 'Unknown' && '❓ Unknown'}
                {data?.metadata?.formats?.[fmt] !== undefined && (
                  <span className="count-chip">{data.metadata.formats[fmt]}</span>
                )}
              </button>
            ))}
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
                : 'Try adjusting your search query, platform, format, or status filter.'}
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
              {filteredHackathons.map(item => {
                const formatLabel = item.location || 'Unknown'
                const hasBenefits = Boolean(item.benefits && item.benefits.length > 0)
                const isExpanded = Boolean(expandedBenefits[item.id])

                return (
                  <article key={item.id} className="hackathon-card">
                    <div>
                      {/* Header Row: Source Badge, Format Badge & Status */}
                      <div className="card-header-row">
                        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                          <span className={`source-badge ${item.source || 'Other'}`}>{item.source}</span>
                          <span className={`format-badge format-${formatLabel.toLowerCase().replace(/[^a-z]/g, '')}`}>
                            {formatLabel}
                          </span>
                        </div>
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
                          Format: <strong>{formatLabel}</strong>
                        </span>
                      </div>
                    </div>

                    {/* Special Benefits & Credits Section */}
                    <div className="benefits-section">
                      <button
                        type="button"
                        className={`benefits-toggle-btn ${hasBenefits ? 'has-benefits' : ''}`}
                        onClick={() => toggleBenefits(item.id)}
                        aria-expanded={isExpanded}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                          <Gift size={14} />
                          <span style={{ fontWeight: 600 }}>
                            {hasBenefits
                              ? `Special Benefits & Credits (${item.benefits!.length})`
                              : 'Special Benefits & Credits'}
                          </span>
                          {hasBenefits && (
                            <span className="benefit-sparkle-pill">
                              <Sparkles size={11} /> Perks
                            </span>
                          )}
                        </div>
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>

                      {isExpanded && (
                        <div className="benefits-drawer">
                          {hasBenefits ? (
                            item.benefits!.map((b: SpecialBenefit, idx: number) => {
                              const dlInfo = evaluateBenefitDeadline(b.application_deadline)

                              return (
                                <div key={idx} className="benefit-card">
                                  <div className="benefit-header">
                                    <span className="benefit-name">{b.name}</span>
                                    <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                                      <span className="benefit-category-pill">{formatCategory(b.category)}</span>
                                      <span className={`confidence-pill ${b.confidence}`}>
                                        <ShieldCheck size={11} />
                                        {b.confidence}
                                      </span>
                                    </div>
                                  </div>

                                  {b.description && <p className="benefit-desc">{b.description}</p>}

                                  {/* Benefit Application Deadline Warning/Status */}
                                  <div className={`benefit-deadline-pill ${dlInfo.status}`}>
                                    {dlInfo.status === 'approaching' && <AlertTriangle size={12} />}
                                    {dlInfo.status === 'passed' && <Clock size={12} />}
                                    <span>{dlInfo.label}</span>
                                  </div>

                                  {b.eligibility && (
                                    <div className="benefit-eligibility">
                                      <strong>Eligibility:</strong> {b.eligibility}
                                    </div>
                                  )}

                                  <div className="benefit-actions-row">
                                    {b.requires_separate_application ? (
                                      <span className="benefit-req-badge">
                                        Separate Application Required
                                      </span>
                                    ) : (
                                      <span className="benefit-auto-badge">
                                        Included with Hackathon
                                      </span>
                                    )}

                                    <div style={{ display: 'flex', gap: '0.5rem', marginLeft: 'auto' }}>
                                      {b.application_url && (
                                        <a
                                          href={b.application_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="benefit-link-btn primary"
                                        >
                                          Apply for Perk <ExternalLink size={11} />
                                        </a>
                                      )}
                                      {b.source_url && (
                                        <a
                                          href={b.source_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="benefit-link-btn"
                                        >
                                          Source <ExternalLink size={11} />
                                        </a>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )
                            })
                          ) : (
                            <div className="no-benefits-notice">
                              <HelpCircle size={15} />
                              <span>No verified benefit information found</span>
                            </div>
                          )}
                        </div>
                      )}
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
                )
              })}
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <div>
          <strong>Hackathon Ingestion Platform</strong> • Multi-source automated discovery engine with format filters & credit discovery.
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
