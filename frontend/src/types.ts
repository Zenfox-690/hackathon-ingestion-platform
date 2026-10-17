export interface Hackathon {
  id: string
  fingerprint: string
  name: string
  title: string
  link: string
  url: string
  source: 'Devpost' | 'Devfolio' | 'Unstop' | string
  deadline: string
  reg_starts_at?: string
  reg_ends_at?: string
  starts_at?: string
  ends_at?: string
  description?: string
  tags: string[]
  prize?: string
  location?: string
  status: 'open' | 'upcoming' | 'ended' | 'unknown'
  is_section_link?: boolean
  created_at?: string
  updated_at?: string
}

export interface SupplementaryLink {
  name: string
  url: string
  source: string
}

export interface CatalogMetadata {
  version: string
  generated_at: string
  total_count: number
  active_count: number
  open_count?: number
  upcoming_count?: number
  ended_count?: number
  unknown_count?: number
  sources: Record<string, number>
  supplementary_links?: SupplementaryLink[]
}

export interface CatalogResponse {
  metadata: CatalogMetadata
  hackathons: Hackathon[]
}
