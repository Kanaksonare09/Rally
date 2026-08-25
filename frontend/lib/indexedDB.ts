import { openDB, DBSchema, IDBPDatabase } from 'idb';

interface RallyDBSchema extends DBSchema {
  pending_locations: {
    key: string;
    value: {
      id: string;
      user_id: string;
      trip_id: string;
      group_id: string;
      latitude: number;
      longitude: number;
      speed?: number;
      heading?: number;
      battery_level?: number;
      connectivity_state: string;
      device_timestamp: string;
    };
    indexes: { 'by-timestamp': string };
  };
}

let dbPromise: Promise<IDBPDatabase<RallyDBSchema>> | null = null;

function getDB() {
  if (typeof window === 'undefined') return null;
  if (!dbPromise) {
    dbPromise = openDB<RallyDBSchema>('rally-offline-db', 1, {
      upgrade(db) {
        const store = db.createObjectStore('pending_locations', { keyPath: 'id' });
        store.createIndex('by-timestamp', 'device_timestamp');
      },
    });
  }
  return dbPromise;
}

export async function queueOfflineLocation(locationPayload: any) {
  const db = await getDB();
  if (!db) return;
  await db.put('pending_locations', locationPayload);
  console.log('[RALLY Offline Queue] Saved location update to IndexedDB:', locationPayload.id);
}

export async function getQueuedLocations() {
  const db = await getDB();
  if (!db) return [];
  return await db.getAll('pending_locations');
}

export async function clearQueuedLocations(ids: string[]) {
  const db = await getDB();
  if (!db) return;
  const tx = db.transaction('pending_locations', 'readwrite');
  await Promise.all(ids.map((id) => tx.store.delete(id)));
  await tx.done;
  console.log('[RALLY Offline Queue] Synchronized & cleared', ids.length, 'queued locations.');
}
