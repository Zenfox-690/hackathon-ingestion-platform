export function computeLiveStatus(
  item: {
    status?: string
    deadline?: string | null
    reg_starts_at?: string | null
    reg_ends_at?: string | null
    starts_at?: string | null
    ends_at?: string | null
    source_status?: string | null
  },
  now: Date = new Date()
): 'open' | 'upcoming' | 'ended' | 'unknown' {
  if (item.source_status && ['ended', 'past', 'closed'].includes(item.source_status.toLowerCase())) {
    return 'ended'
  }

  const effectiveDeadline = item.reg_ends_at || item.deadline
  if (effectiveDeadline && effectiveDeadline.toLowerCase() !== 'unknown') {
    let dlDate: Date
    // If date-only deadline (e.g. YYYY-MM-DD or doesn't have explicit time), treat as end of day
    if (!effectiveDeadline.includes('T') && !effectiveDeadline.includes(':')) {
      dlDate = new Date(`${effectiveDeadline}T23:59:59.999Z`)
    } else {
      dlDate = new Date(effectiveDeadline)
    }

    if (!isNaN(dlDate.getTime())) {
      if (dlDate.getTime() < now.getTime()) {
        return 'ended'
      }

      if (item.reg_starts_at) {
        const start = new Date(item.reg_starts_at)
        if (!isNaN(start.getTime()) && start.getTime() > now.getTime()) {
          return 'upcoming'
        }
      }

      if (item.source_status && item.source_status.toLowerCase() === 'upcoming') {
        return 'upcoming'
      }

      return 'open'
    }
  }

  if (item.ends_at) {
    const end = new Date(item.ends_at)
    if (!isNaN(end.getTime()) && end.getTime() < now.getTime()) {
      return 'ended'
    }
  }

  if (item.starts_at) {
    const start = new Date(item.starts_at)
    if (!isNaN(start.getTime())) {
      if (start.getTime() > now.getTime()) {
        return 'upcoming'
      }
      return 'unknown'
    }
  }

  return (item.status as any) || 'unknown'
}
