export interface RouteOption {
  id: string;
  coordinates: { lat: number; lng: number }[];
  distance: number; // in meters
  duration: number; // in seconds
  summary: string;
  isRecommended: boolean;
}

export async function calculateRoute(
  start: { lat: number; lng: number },
  destination: { lat: number; lng: number }
): Promise<RouteOption[]> {
  // Validate coordinates
  if (
    start.lat < -90 || start.lat > 90 || start.lng < -180 || start.lng > 180 ||
    destination.lat < -90 || destination.lat > 90 || destination.lng < -180 || destination.lng > 180
  ) {
    throw new Error('Invalid coordinates provided');
  }

  // OSRM coordinates format: longitude,latitude
  const url = `https://router.project-osrm.org/route/v1/driving/${start.lng},${start.lat};${destination.lng},${destination.lat}?overview=full&geometries=geojson&alternatives=true`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error('Routing service unavailable');
    }

    const data = await res.json();
    if (data.code !== 'Ok' || !data.routes || data.routes.length === 0) {
      throw new Error('No route available');
    }

    const options = data.routes.map((route: any, index: number) => {
      const coordinates = route.geometry.coordinates.map((coord: number[]) => ({
        lat: coord[1],
        lng: coord[0],
      }));
      return {
        id: `route-${index}`,
        coordinates,
        distance: route.distance,
        duration: route.duration,
        summary: route.legs && route.legs[0] && route.legs[0].summary ? route.legs[0].summary : `Route ${index + 1}`,
        isRecommended: false,
      };
    });

    // Determine recommended route by shortest duration
    let recommendedIndex = 0;
    let minDuration = Infinity;
    options.forEach((opt: any, index: number) => {
      if (opt.duration < minDuration) {
        minDuration = opt.duration;
        recommendedIndex = index;
      }
    });
    
    options[recommendedIndex].isRecommended = true;

    return options;
  } catch (error: any) {
    console.error('Routing error:', error);
    throw new Error(error.message || 'Unable to calculate route');
  }
}
