/**
 * Typed client for in-app notifications.
 *
 * Endpoints (per `.agent/adr/012-ai-brief.md` §12.2):
 *   GET  /notifications?unread_only=&limit=
 *   POST /notifications/{id}/read
 *   GET  /notifications/unread-count
 */

import { api } from '../api'
import type { Notification } from '@ai-news-scraper/shared'

export interface ListNotificationsOpts {
  unreadOnly?: boolean
  limit?: number
}

// The /notifications endpoint returns a wrapper `{ items, total }`
// matching the shared `NotificationListResponse` type. (Previously
// this typed the return as `Notification[]` and used to compile
// because NotificationListResponse was widened at runtime, but the
// real API always returns the wrapper -- so the type was a lie and
// `data.filter` on the wrapper object crashed at runtime.)
export interface NotificationListResponse {
  items: Notification[]
  total: number
}

export async function listNotifications(
  opts: ListNotificationsOpts = {}
): Promise<NotificationListResponse> {
  const params = new URLSearchParams()
  if (opts.unreadOnly) params.set('unread_only', 'true')
  if (opts.limit) params.set('limit', String(opts.limit))
  const qs = params.toString()
  return api.get<NotificationListResponse>(`/notifications${qs ? `?${qs}` : ''}`)
}

export async function markNotificationRead(id: string): Promise<void> {
  await api.post<{ ok: true }>(`/notifications/${encodeURIComponent(id)}/read`)
}

export async function getUnreadCount(): Promise<number> {
  const res = await api.get<{ count: number }>('/notifications/unread-count')
  return res.count
}
