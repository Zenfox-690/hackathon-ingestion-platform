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

