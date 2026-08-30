import { api } from './client';
import type { ApiGroup, ApiGroupListItem, ApiGroupMember } from './types';

export function listMyGroups(): Promise<ApiGroupListItem[]> {
  return api.get<ApiGroupListItem[]>('/groups');
}

export function createGroup(input: { name: string; destination_name?: string; latitude?: number; longitude?: number }): Promise<ApiGroup> {
  return api.post<ApiGroup>('/groups', input);
}

export function joinGroup(joinCode: string): Promise<ApiGroup> {
  return api.post<ApiGroup>('/groups/join', { join_code: joinCode });
}

export function getGroup(groupId: string): Promise<ApiGroup> {
  return api.get<ApiGroup>(`/groups/${groupId}`);
}

export function getGroupMembers(groupId: string): Promise<ApiGroupMember[]> {
  return api.get<ApiGroupMember[]>(`/groups/${groupId}/members`);
}

export function leaveGroup(groupId: string): Promise<void> {
  return api.post<void>(`/groups/${groupId}/leave`);
}

export function removeMember(groupId: string, targetUserId: string): Promise<void> {
  return api.delete<void>(`/groups/${groupId}/members/${targetUserId}`);
}

export function transferLeadership(groupId: string, newLeaderId: string): Promise<void> {
  return api.post<void>(`/groups/${groupId}/transfer-leadership`, { new_leader_id: newLeaderId });
}
