import Hero from '@/components/landing/Hero';
import Features from '@/components/landing/Features';
import Testimonial from '@/components/landing/Testimonial';
import FinalCTA from '@/components/landing/FinalCTA';
import Footer from '@/components/landing/Footer';

export default function Home() {
  return (
    <div className="bg-background text-foreground">
      <Hero />
      <Features />
      <Testimonial />
      <FinalCTA />
      <Footer />
    </div>
  );
}
