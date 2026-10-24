import type { ReactNode } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import type { Tone } from "../lib/types";

export function Badge({
  children,
  tone = "slate",
  dot = false,
}: {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
}) {
  return (
    <span className={`badge badge--${tone}`}>
      {dot && <span className="badge__dot" />}
      {children}
    </span>
  );
}

export function Panel({
  children,
  className = "",
  padding = "md",
}: {
  children: ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
}) {
  return <section className={`panel panel--${padding} ${className}`}>{children}</section>;
}

export function SectionTitle({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="section-title__actions">{actions}</div>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  unit,
  hint,
  tone = "cyan",
  icon,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: string;
  tone?: Tone;
  icon?: ReactNode;
}) {
  return (
    <div className={`stat-card stat-card--${tone}`}>
      <div className="stat-card__top">
        <span>{label}</span>
        {icon && <span className="stat-card__icon">{icon}</span>}
      </div>
      <div className="stat-card__value">
        {value}
        {unit && <small>{unit}</small>}
      </div>
      {hint && <div className="stat-card__hint">{hint}</div>}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-loading">
      <Loader2 size={16} className="spin" />
      {label && <span>{label}</span>}
    </span>
  );
}

export function LoadingBlock({ label = "Cargando…" }: { label?: string }) {
  return (
    <div className="loading-block">
      <Loader2 size={26} className="spin" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ title = "No se pudo cargar", message }: { title?: string; message: string }) {
  return (
    <div className="error-state">
      <AlertTriangle size={22} />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`field ${className}`}>
      <span className="field__label">{label}</span>
      {children}
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  color,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description?: string;
  color?: string;
}) {
  return (
    <button type="button" className={`toggle ${checked ? "is-on" : ""}`} onClick={() => onChange(!checked)}>
      <span className="toggle__switch" style={color ? { background: checked ? color : undefined } : undefined}>
        <span className="toggle__thumb" />
      </span>
      <span className="toggle__copy">
        <span>{label}</span>
        {description && <small>{description}</small>}
      </span>
    </button>
  );
}

export function ProgressBar({ value, tone = "cyan" }: { value: number; tone?: Tone }) {
  return (
    <div className={`progress progress--${tone}`}>
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-state__mark">◇</div>
      <h3>{title}</h3>
      <p>{message}</p>
      {action}
    </div>
  );
}
