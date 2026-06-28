/**
 * Shared types between apps/api (Python) and apps/web (TypeScript).
 * Keep this file framework-agnostic. Manual mirror of Pydantic schemas in
 * apps/api/api/schemas/*.py — keep them in sync.
 */

export type ID = string;

export interface Article {
  id: ID;
  url: string;
  headline: string;
  body: string;
  summary: string;
  topics: string[];
  source_domain: string;
  publish_date: string | null;
  indexed_at: string;
  user_id: ID | null;
}

export interface ArticleListResponse {
  items: Article[];
  total: number;
  page: number;
  page_size: number;
}

export interface ScrapeRequest {
  url: string;
}

export interface BatchScrapeRequest {
  urls: string[];
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  filters?: SearchFilters;
}

export interface SearchFilters {
  source?: string;
  topics?: string[];
  date_from?: string;
  date_to?: string;
}

export interface SearchResult {
  article: Article;
  score: number;
  highlights?: string[];
}

export interface SearchResponse {
  results: SearchResult[];
  took_ms: number;
}

export interface Feed {
  id: ID;
  user_id: ID;
  feed_url: string;
  title: string;
  description: string | null;
  last_polled: string | null;
  active: boolean;
  item_count: number;
  created_at: string;
}

export interface FeedItem {
  id: ID;
  feed_id: ID;
  article_id: ID | null;
  guid: string;
  title: string;
  url: string;
  fetched_at: string;
}

export interface User {
  id: ID;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export interface ApiError {
  detail: string;
  code?: string;
}