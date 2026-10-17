export interface SpecialBenefit {
  name: string
  category: string
  description?: string
  requires_separate_application: boolean
  application_deadline?: string | null
  application_url?: string | null
  source_url?: string | null
  eligibility?: string | null
  confidence: 'verified' | 'unverified'
}

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
  location?: 'Online' | 'In-Person' | 'Hybrid' | 'Unknown' | string
  status: 'open' | 'upcoming' | 'ended' | 'unknown'
  benefits?: SpecialBenefit[]
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
  formats?: Record<string, number>
  benefits_count?: number
  supplementary_links?: SupplementaryLink[]
}

export interface CatalogResponse {
  metadata: CatalogMetadata
  hackathons: Hackathon[]
}
