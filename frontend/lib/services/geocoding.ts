export interface Destination {
  name: string;
  latitude: number;
  longitude: number;
}

export async function searchDestination(query: string): Promise<Destination[]> {
  if (!query.trim()) return [];
  
  const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`;
  
  try {
    const res = await fetch(url, {
      headers: {
        'Accept-Language': 'en',
        // Provide a custom user-agent as per Nominatim's usage policy if possible,
        // though standard browser fetch is usually accepted for low volume.
      }
    });
    
    if (!res.ok) {
      throw new Error('Geocoding service unavailable');
    }
    
    const data = await res.json();
    return data.map((item: any) => ({
      name: item.display_name,
      latitude: parseFloat(item.lat),
      longitude: parseFloat(item.lon),
    }));
  } catch (error) {
    console.error('Geocoding error:', error);
    throw new Error('Failed to search destination');
  }
}
