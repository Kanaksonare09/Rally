import Hero from '@/components/landing/Hero';
import ProductStory from '@/components/landing/ProductStory';
import LiveVisualization from '@/components/landing/LiveVisualization';
import Features from '@/components/landing/Features';
import SeparationTimeline from '@/components/landing/SeparationTimeline';
import OneGroupOneView from '@/components/landing/OneGroupOneView';
import SmartAlertsDemo from '@/components/landing/SmartAlertsDemo';
import TripReplayDemo from '@/components/landing/TripReplayDemo';
import SafetyEditorial from '@/components/landing/SafetyEditorial';
import ProductProof from '@/components/landing/ProductProof';
import Testimonial from '@/components/landing/Testimonial';
import FinalProductStatement from '@/components/landing/FinalProductStatement';
import FinalCTA from '@/components/landing/FinalCTA';
import Footer from '@/components/landing/Footer';

export default function Home() {
  return (
    <div className="bg-background text-foreground">
      <Hero />
      <ProductStory />
      <LiveVisualization />
      <Features />
      <SeparationTimeline />
      <OneGroupOneView />
      <SmartAlertsDemo />
      <TripReplayDemo />
      <SafetyEditorial />
      <ProductProof />
      <Testimonial />
      <FinalProductStatement />
      <FinalCTA />
      <Footer />
    </div>
  );
}
