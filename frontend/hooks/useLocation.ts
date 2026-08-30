import { useState, useEffect, useCallback } from 'react';
import type { LocationData, LocationQuality } from '../types/location';

export function useLocation() {
  const [location, setLocation] = useState<LocationData | null>(null);
  const [isTracking, setIsTracking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [permissionState, setPermissionState] = useState<PermissionState | 'unsupported' | 'unknown'>('unknown');
  const [watchId, setWatchId] = useState<number | null>(null);

  // Check initial permissions if supported
  useEffect(() => {
    if (typeof window !== 'undefined' && 'navigator' in window && 'permissions' in navigator) {
      navigator.permissions.query({ name: 'geolocation' }).then((status) => {
        setPermissionState(status.state);
        status.onchange = () => setPermissionState(status.state);
      }).catch(() => {
        // Fallback for browsers that don't support permission query for geolocation
      });
    } else if (typeof window !== 'undefined' && !('geolocation' in navigator)) {
      setPermissionState('unsupported');
    }
  }, []);

  const startTracking = useCallback(() => {
    if (typeof window === 'undefined' || !('geolocation' in navigator)) {
      setError('Your browser does not support location services required by RALLY.');
      setPermissionState('unsupported');
      return;
    }

    if (isTracking) return;

    setError(null);
    setIsTracking(true);

    const id = navigator.geolocation.watchPosition(
      (position) => {
        const { latitude, longitude, accuracy, speed, heading } = position.coords;

        // Validation
        if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
          return; // Ignore invalid coordinates
        }

        setLocation({
          latitude,
          longitude,
          accuracy,
          speed,
          heading,
          timestamp: position.timestamp,
        });
        setPermissionState('granted');
      },
      (err) => {
        setIsTracking(false);
        if (watchId !== null) {
          navigator.geolocation.clearWatch(watchId);
          setWatchId(null);
        }

        switch (err.code) {
          case err.PERMISSION_DENIED:
            setError('Location permission is required for RALLY location features. Please enable it in your browser settings.');
            setPermissionState('denied');
            break;
          case err.POSITION_UNAVAILABLE:
            setError('GPS signal unavailable. Please check your device location settings.');
            break;
          case err.TIMEOUT:
            setError('Location request timed out. Trying again...');
            break;
          default:
            setError('An unknown error occurred while acquiring location.');
        }
      },
      {
        enableHighAccuracy: true,
        maximumAge: 0,
        timeout: 15000,
      }
    );

    setWatchId(id);
  }, [isTracking, watchId]);

  const stopTracking = useCallback(() => {
    if (watchId !== null && typeof window !== 'undefined' && 'geolocation' in navigator) {
      navigator.geolocation.clearWatch(watchId);
      setWatchId(null);
    }
    setIsTracking(false);
  }, [watchId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (watchId !== null && typeof window !== 'undefined' && 'geolocation' in navigator) {
        navigator.geolocation.clearWatch(watchId);
      }
    };
  }, [watchId]);

  return {
    location,
    isTracking,
    error,
    permissionState,
    startTracking,
    stopTracking,
  };
}

export function getLocationQuality(accuracy: number | undefined): LocationQuality {
  if (!accuracy) return 'Poor';
  if (accuracy <= 15) return 'Excellent';
  if (accuracy <= 50) return 'Good';
  if (accuracy <= 100) return 'Fair';
  return 'Poor';
}
