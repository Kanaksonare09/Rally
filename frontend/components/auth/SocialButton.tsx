'use client';

export default function SocialButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center justify-center gap-2 h-11 bg-background border border-border rounded-xl text-sm font-medium text-foreground hover:bg-white/5 transition-colors"
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}
