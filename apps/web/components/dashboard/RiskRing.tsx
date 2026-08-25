'use client';

import type { RiskAssessment } from '@/lib/mock/types';

const LEVEL_COLOR: Record<RiskAssessment['level'], string> = {
  'LOW RISK': '#34D399',
  'MODERATE RISK': '#FBBF24',
  'HIGH RISK': '#F87171',
};

export default function RiskRing({ risk, size = 96 }: { risk: RiskAssessment; size?: number }) {
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - risk.score / 100);
  const color = LEVEL_COLOR[risk.level];

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-bold text-foreground leading-none">{risk.score}</span>
        <span className="text-[10px] text-muted-foreground leading-none mt-0.5">/ 100</span>
      </div>
    </div>
  );
}
