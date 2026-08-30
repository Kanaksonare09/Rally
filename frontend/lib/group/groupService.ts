/**
 * The real (backend-backed) GroupService — see
 * lib/realtime/RallyGroupService.ts for the implementation. This module
 * is the one import path every component uses (`@/lib/group/groupService`),
 * so swapping the concrete implementation later never means touching
 * consumer files again.
 *
 * `buildPreviewGroup` is re-exported from the mock module unchanged — it
 * only ever builds a non-persisted, in-memory preview for the
 * create-group page's live map preview panel before a real group exists
 * (never real member/location data), which is exactly the kind of
 * "intentionally isolated frontend placeholder" Phase 13 says is fine to
 * keep.
 */
export { rallyGroupService as groupService } from '@/lib/realtime/RallyGroupService';
export { buildPreviewGroup } from '@/lib/mock/groupService';
export type { GroupService } from '@/lib/mock/groupService';
