/**
 * Utilities for managing and persisting bookmarked / saved hackathons
 * in browser localStorage with graceful error handling and stable identity keys.
 */

export const BOOKMARKS_STORAGE_KEY = 'hackathon_saved_bookmarks_v1'

export interface BookmarkableItem {
  id?: string
  link?: string
  url?: string
  fingerprint?: string
  name?: string
}

/**
 * Returns a stable, canonical identity key for a hackathon.
 * Prefers the canonical link/url to survive catalog updates or re-indexing,
 * falling back to id or fingerprint.
 */
export function getHackathonIdentityKey(item: BookmarkableItem | null | undefined): string {
  if (!item) return ''
  const primary = item.link || item.url || item.id || item.fingerprint || ''
  return primary.trim()
}

/**
 * Safely loads saved bookmark identity keys from browser localStorage.
 * Gracefully handles missing, corrupted, or access-restricted localStorage.
 */
export function loadSavedBookmarks(
  storage: Storage | null = typeof window !== 'undefined' ? window.localStorage : null
): Set<string> {
  if (!storage) return new Set()
  try {
    const raw = storage.getItem(BOOKMARKS_STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      return new Set(
        parsed.filter((k): k is string => typeof k === 'string' && k.trim().length > 0)
      )
    }
  } catch (err) {
    // Graceful fallback on quota error, syntax error, or SecurityError
    console.warn('[Bookmarks] Could not load saved bookmarks:', err)
  }
  return new Set()
}

/**
 * Safely writes saved bookmark identity keys to browser localStorage.
 * Returns true if persisted successfully, false on error/unavailability.
 */
export function persistSavedBookmarks(
  keys: Set<string>,
  storage: Storage | null = typeof window !== 'undefined' ? window.localStorage : null
): boolean {
  if (!storage) return false
  try {
    const array = Array.from(keys)
    storage.setItem(BOOKMARKS_STORAGE_KEY, JSON.stringify(array))
    return true
  } catch (err) {
    console.warn('[Bookmarks] Could not persist saved bookmarks:', err)
    return false
  }
}
