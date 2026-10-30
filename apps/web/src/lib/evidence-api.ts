import { request } from "./api";

export interface EvidenceStatus {
  indexed: number;
  embedded: number;
  pending: number;
  /** True when an AI key and an embedding model are set. Keyword search never needs them. */
  meaning_search_configured: boolean;
}

export interface EvidenceHit {
  chunk_id: string;
  /** The profile entry this text came from, or null for other sources. */
  entry_id: string | null;
  source_type: string;
  entry_type: string | null;
  text: string;
  score: number;
  matched_by: string[];
  keyword_rank: number | null;
  meaning_rank: number | null;
  similarity: number | null;
}

export interface EvidenceSearch {
  query: string;
  meaning_search_used: boolean;
  /** A plain sentence when meaning search was not used. */
  note: string | null;
  hits: EvidenceHit[];
}

const BASE = "/api/v1/evidence";

export function fetchEvidenceStatus(signal?: AbortSignal): Promise<EvidenceStatus> {
  return request<EvidenceStatus>("GET", `${BASE}/status`, { signal });
}

export function searchEvidence(query: string, limit = 10): Promise<EvidenceSearch> {
  return request<EvidenceSearch>("POST", `${BASE}/search`, { body: { query, limit } });
}
