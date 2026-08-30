export type LocationQuality = 'Excellent' | 'Good' | 'Fair' | 'Poor';

export interface LocationData {
  id?: string;
  latitude: number;
  longitude: number;
  accuracy: number;
  speed: number | null;
  heading: number | null;
  timestamp: number;
}
