'use client';

import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export default function AuthInput({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  required,
  helperText,
  className = '',
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  helperText?: string;
  className?: string;
}) {
  const [visible, setVisible] = useState(false);
  const isPassword = type === 'password';
  const resolvedType = isPassword ? (visible ? 'text' : 'password') : type;

  return (
    <div className={`space-y-1.5 ${className}`}>
      <label className="text-sm font-medium text-foreground block">{label}</label>
      <div className="relative">
        <input
          type={resolvedType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          placeholder={placeholder}
          className="w-full bg-card border-none rounded-xl h-11 px-4 pr-11 text-sm text-foreground placeholder:text-white/20 focus:outline-none focus:ring-2 focus:ring-white/20 transition-shadow"
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Hide password' : 'Show password'}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          >
            {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
      {helperText && <p className="text-xs text-muted-foreground">{helperText}</p>}
    </div>
  );
}
