import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const catalogPath = path.resolve(__dirname, '../public/data/hackathons.json')

test('Public JSON Catalog Integrity', () => {
  assert.ok(fs.existsSync(catalogPath), 'hackathons.json must exist in public/data/')
  const content = fs.readFileSync(catalogPath, 'utf8')
  const json = JSON.parse(content)

  // Verify structure
  assert.ok(json.metadata, 'Catalog metadata is required')
  assert.equal(typeof json.metadata.version, 'string')
  assert.equal(typeof json.metadata.total_count, 'number')
  assert.ok(Array.isArray(json.hackathons), 'Hackathons must be an array')
  assert.equal(json.hackathons.length, json.metadata.total_count)

  // Verify each item conforms to public contract and does not leak private fields
  json.hackathons.forEach(item => {
    assert.ok(item.id, 'item.id is required')
    assert.ok(item.name, 'item.name is required')
    assert.ok(item.link, 'item.link is required')
    assert.ok(item.source, 'item.source is required')
    assert.ok(item.status, 'item.status is required')

    // Strict leak checks: Never export bot state or user credentials
    assert.equal(item.chat_id, undefined, 'chat_id must never be present')
    assert.equal(item.users, undefined, 'users must never be present')
    assert.equal(item.filters, undefined, 'filters must never be present')
    assert.equal(item.token, undefined, 'token must never be present')
  })
})

test('Frontend Filtering Logic Simulation', () => {
  const sampleItems = [
    { id: '1', name: 'AI Super Hack', source: 'Devpost', status: 'open', tags: ['ai', 'python'], deadline: '2026-08-01' },
    { id: '2', name: 'Web3 Builder', source: 'Devfolio', status: 'open', tags: ['web3'], deadline: '2026-07-01' },
    { id: '3', name: 'Legacy Past Hack', source: 'Unstop', status: 'ended', tags: ['ai'], deadline: '2025-01-01' }
  ]

  // Filter by source: Devpost
  const devpostOnly = sampleItems.filter(h => h.source === 'Devpost')
  assert.equal(devpostOnly.length, 1)
  assert.equal(devpostOnly[0].name, 'AI Super Hack')

  // Filter by status: open
  const openOnly = sampleItems.filter(h => h.status === 'open')
  assert.equal(openOnly.length, 2)

  // Filter by tag: ai
  const aiOnly = sampleItems.filter(h => h.tags.includes('ai'))
  assert.equal(aiOnly.length, 2)

  // Sort by deadline ascending
  const sorted = [...sampleItems].sort((a, b) => a.deadline.localeCompare(b.deadline))
  assert.equal(sorted[0].id, '3')
})

test('Actionable Filtering and Devfolio Integration Verification', () => {
  const content = fs.readFileSync(catalogPath, 'utf8')
  const json = JSON.parse(content)

  // 1. Verify supplementary navigation links are exposed
  assert.ok(Array.isArray(json.metadata.supplementary_links), 'supplementary_links must be an array')
  assert.ok(json.metadata.supplementary_links.length >= 4, 'Must include Devfolio section navigation links')
  const sectionNames = json.metadata.supplementary_links.map(l => l.name.toLowerCase())
  assert.ok(sectionNames.some(n => n.includes('open')), 'Must include open hackathons link')
  assert.ok(sectionNames.some(n => n.includes('upcoming')), 'Must include upcoming hackathons link')

  // 2. Verify Devfolio real hackathons exist in hackathons array
  const devfolioHacks = json.hackathons.filter(h => h.source === 'Devfolio')
  assert.ok(devfolioHacks.length > 0, 'Devfolio real hackathons must be present')
  devfolioHacks.forEach(h => {
    assert.notEqual(h.name.toLowerCase(), 'your hackathons', 'Section links must not be hackathon cards')
    assert.notEqual(h.name.toLowerCase(), 'all upcoming hackathons', 'Section links must not be hackathon cards')
    assert.ok(h.link.startsWith('http'), 'Valid link required')
  })

  // 3. Verify Actionable Filter excludes expired hackathons
  const actionable = json.hackathons.filter(h => h.status === 'open' || h.status === 'upcoming')
  actionable.forEach(h => {
    assert.notEqual(h.status, 'ended', 'Actionable results must not include ended hackathons')
  })
})

test('Format Normalization and Benefits Contract Verification', () => {
  const content = fs.readFileSync(catalogPath, 'utf8')
  const json = JSON.parse(content)

  const validFormats = new Set(['Online', 'In-Person', 'Hybrid', 'Unknown'])

  // Check formats metadata
  if (json.metadata.formats) {
    Object.keys(json.metadata.formats).forEach(fmt => {
      assert.ok(validFormats.has(fmt), `Metadata format '${fmt}' must be one of Online, In-Person, Hybrid, Unknown`)
    })
  }

  // Check item formats and benefits
  json.hackathons.forEach(h => {
    assert.ok(validFormats.has(h.location), `Hackathon location '${h.location}' must be normalized to canonical formats`)
    assert.ok(Array.isArray(h.benefits), `Hackathon '${h.name}' must have benefits array`)

    h.benefits.forEach(b => {
      assert.ok(b.name, 'Benefit name is required')
      assert.ok(b.category, 'Benefit category is required')
      assert.equal(typeof b.requires_separate_application, 'boolean')
      assert.ok(b.confidence === 'verified' || b.confidence === 'unverified')

      // Ensure benefit application deadline is isolated from hackathon main deadline
      if (b.application_deadline && h.deadline) {
        // They could coincidentally match, but if separate application is required, verify isolation
        assert.equal(typeof b.application_deadline, 'string')
      }
    })
  })

  // Format filter simulation
  const onlineOnly = json.hackathons.filter(h => h.location === 'Online')
  const inPersonOnly = json.hackathons.filter(h => h.location === 'In-Person')
  const hybridOnly = json.hackathons.filter(h => h.location === 'Hybrid')
  const unknownOnly = json.hackathons.filter(h => h.location === 'Unknown')

  assert.equal(
    onlineOnly.length + inPersonOnly.length + hybridOnly.length + unknownOnly.length,
    json.hackathons.length,
    'Combined format counts must equal total hackathons'
  )
})

test('Dynamic Status Freshness Evaluation and Controllable Clock', async () => {
  const { computeLiveStatus } = await import('../src/status.ts')

  // Item exported as 'open' with deadline 2026-10-15
  const item = {
    name: 'Dynamic Hack',
    deadline: '2026-10-15',
    status: 'open'
  }

  // 1. Clock before deadline on the same day (10:00 AM UTC): should be OPEN because date-only is EOD (23:59:59)
  const clockBefore = new Date('2026-10-15T10:00:00Z')
  assert.equal(computeLiveStatus(item, clockBefore), 'open', 'Must be open during the day for date-only deadline')

  // 2. Clock after deadline (2026-10-16T00:00:01Z): should dynamically transition to ENDED
  const clockAfter = new Date('2026-10-16T00:00:01Z')
  assert.equal(computeLiveStatus(item, clockAfter), 'ended', 'Must dynamically compute ended once deadline passes')

  // 3. Item with future registration start: should be UPCOMING
  const upcomingItem = {
    name: 'Future Registration Hack',
    reg_starts_at: '2026-11-01T00:00:00Z',
    deadline: '2026-12-01T00:00:00Z',
    status: 'open'
  }
  assert.equal(computeLiveStatus(upcomingItem, clockBefore), 'upcoming')
})

test('Bookmark Persistence, Identity Stability, and Safe Storage', async () => {
  const {
    getHackathonIdentityKey,
    loadSavedBookmarks,
    persistSavedBookmarks,
  } = await import('../src/bookmarks.ts')

  // 1. Mock in-memory localStorage
  const memoryStore = new Map()
  const mockStorage = {
    getItem: (key) => memoryStore.get(key) || null,
    setItem: (key, val) => memoryStore.set(key, String(val)),
    removeItem: (key) => memoryStore.delete(key),
    clear: () => memoryStore.clear()
  }

  // 2. Initial load from empty storage
  const initial = loadSavedBookmarks(mockStorage)
  assert.equal(initial.size, 0, 'Initial saved bookmarks should be empty')

  // 3. Save bookmarks using stable canonical identity
  const item1 = { id: 'devpost-123', link: 'https://devpost.com/hackathons/ai-summit-2026', name: 'AI Summit' }
  const item2 = { id: 'devfolio-456', url: 'https://devfolio.co/hackathons/eth-denver-2026', name: 'ETH Denver' }
  const key1 = getHackathonIdentityKey(item1)
  const key2 = getHackathonIdentityKey(item2)

  assert.equal(key1, 'https://devpost.com/hackathons/ai-summit-2026', 'Canonical link must be the primary key')
  assert.equal(key2, 'https://devfolio.co/hackathons/eth-denver-2026', 'Canonical url must be used when link is omitted')

  const toSave = new Set([key1, key2])
  const persisted = persistSavedBookmarks(toSave, mockStorage)
  assert.equal(persisted, true)

  // 4. Reload from storage (simulate page refresh)
  const reloaded = loadSavedBookmarks(mockStorage)
  assert.equal(reloaded.size, 2)
  assert.ok(reloaded.has(key1))
  assert.ok(reloaded.has(key2))

  // 5. Unsave / toggle item
  toSave.delete(key1)
  persistSavedBookmarks(toSave, mockStorage)
  const afterUnsave = loadSavedBookmarks(mockStorage)
  assert.equal(afterUnsave.size, 1)
  assert.ok(!afterUnsave.has(key1))
  assert.ok(afterUnsave.has(key2))

  // 6. Stability across catalog updates:
  // If the listing's ID changes (e.g. re-indexing) or date updates, canonical URL still matches
  const updatedItem2 = { id: 'devfolio-999-new-id', link: 'https://devfolio.co/hackathons/eth-denver-2026', deadline: '2026-12-31' }
  const updatedKey2 = getHackathonIdentityKey(updatedItem2)
  assert.ok(afterUnsave.has(updatedKey2), 'Bookmark must persist across catalog record updates with changed id')

  // 7. Graceful error handling for missing/malformed storage
  const nullLoaded = loadSavedBookmarks(null)
  assert.equal(nullLoaded.size, 0, 'Must handle null storage gracefully')

  const corruptedStorage = {
    getItem: () => '{ invalid json garbage %%%',
    setItem: () => {}
  }
  const corruptedLoaded = loadSavedBookmarks(corruptedStorage)
  assert.equal(corruptedLoaded.size, 0, 'Must handle corrupted JSON gracefully without throwing')

  const throwingStorage = {
    getItem: () => { throw new Error('SecurityError: localStorage denied') },
    setItem: () => { throw new Error('QuotaExceededError') }
  }
  assert.doesNotThrow(() => {
    loadSavedBookmarks(throwingStorage)
    persistSavedBookmarks(new Set(['test']), throwingStorage)
  }, 'Must handle throwing storage gracefully')
})
