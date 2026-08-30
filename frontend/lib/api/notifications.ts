import { api } from './client';
import type { ApiNotification, NotificationListResponse, UnreadCountResponse } from './types';

export function listNotifications(query: { unread_only?: boolean; limit?: number; offset?: number } = {}): Promise<NotificationListResponse> {
  return api.get<NotificationListResponse>('/notifications', query);
}

export function getUnreadCount(): Promise<UnreadCountResponse> {
  return api.get<UnreadCountResponse>('/notifications/unread-count');
}

export function markNotificationRead(notificationId: string): Promise<ApiNotification> {
  return api.patch<ApiNotification>(`/notifications/${notificationId}/read`);
}

export function markAllNotificationsRead(): Promise<{ marked_count: number }> {
  return api.patch<{ marked_count: number }>('/notifications/read-all');
}
