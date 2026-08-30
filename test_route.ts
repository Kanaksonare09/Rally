import { calculateRoute } from './frontend/lib/services/routing';

async function test() {
  try {
    const start = { lat: 19.0760, lng: 72.8777 }; // Mumbai
    const dest = { lat: 18.5204, lng: 73.8567 }; // Pune
    console.log("Calculating...");
    const routes = await calculateRoute(start, dest);
    console.log("Routes count:", routes.length);
    console.log("First route distance:", routes[0]?.distance);
    console.log("First route coords length:", routes[0]?.coordinates?.length);
  } catch (err) {
    console.error("Error:", err);
  }
}
test();
