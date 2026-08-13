import React from 'react';

export const AuthShell: React.FC<{ title: string; subtitle?: React.ReactNode; children: React.ReactNode }> = ({
  title, subtitle, children,
}) => (
  <div className="min-h-screen bg-ora-canvas text-ora-primary">
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      <section className="ora-auth-brand-panel hidden border-r border-white/10 bg-ora-nav px-10 py-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3">
          <OraMark />
          <div>
            <p className="text-lg font-semibold tracking-tight">Ora</p>
            <p className="text-xs text-white/55">Adaptive workspaces</p>
          </div>
        </div>

        <div className="max-w-xl">
          <p className="text-sm font-medium uppercase tracking-[0.22em] text-ora-accent">Plan. Schedule. Adapt.</p>
          <h1 className="mt-5 text-5xl font-semibold leading-[1.02] tracking-tight">
            A calm operating layer for personal work and shared teams.
          </h1>
          <p className="mt-5 max-w-md text-sm leading-6 text-white/65">
            Ora keeps goals, projects, schedules, evidence, and team context in one workspace without turning work into an issue tracker.
          </p>
        </div>

        <div className="grid max-w-xl grid-cols-3 gap-3 text-xs">
          {['Personal focus', 'Team context', 'Verified actions'].map(item => (
            <div key={item} className="ora-nav-surface rounded-lg border border-white/10 bg-ora-nav-surface px-3 py-3 text-white/75">
              {item}
            </div>
          ))}
        </div>
      </section>

      <main className="ora-auth-form-plane flex min-h-screen items-center justify-center px-4 py-10">
        <div className="w-full max-w-[420px]">
          <div className="mb-8 flex flex-col items-center lg:hidden">
            <OraMark />
            <span className="mt-3 text-lg font-semibold tracking-tight">Ora</span>
          </div>

          <div className="rounded-lg border border-ora-border bg-ora-surface p-7 shadow-sm sm:p-8">
            <div className="mb-7">
              <h1 className="text-2xl font-semibold tracking-tight text-ora-primary">{title}</h1>
              {subtitle && <p className="mt-2 text-sm leading-6 text-ora-secondary">{subtitle}</p>}
            </div>
            {children}
          </div>
        </div>
      </main>
    </div>
  </div>
);

export const OraMark: React.FC<{ size?: number }> = ({ size = 40 }) => (
  <div
    className="rounded-lg bg-ora-accent flex items-center justify-center shadow-sm"
    style={{ width: size, height: size }}
  >
    <span className="text-white font-bold" style={{ fontSize: size * 0.5 }}>O</span>
  </div>
);

export const GoogleIcon: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
    <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.87 2.7-6.62z" />
    <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.81.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18z" />
    <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33z" />
    <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58z" />
  </svg>
);

export const MicrosoftIcon: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
    <rect x="0" y="0" width="8.5" height="8.5" fill="#F25022" />
    <rect x="9.5" y="0" width="8.5" height="8.5" fill="#7FBA00" />
    <rect x="0" y="9.5" width="8.5" height="8.5" fill="#00A4EF" />
    <rect x="9.5" y="9.5" width="8.5" height="8.5" fill="#FFB900" />
  </svg>
);

export const authInputClass =
  "block w-full pl-10 pr-3 py-2.5 bg-ora-surface border border-ora-border rounded-lg text-ora-primary placeholder:text-ora-tertiary " +
  "focus:border-ora-accent focus:ring-2 focus:ring-ora-accent/20 outline-none transition-shadow text-sm";

export const authPrimaryButtonClass =
  "w-full py-2.5 px-4 rounded-lg text-sm font-medium text-white bg-ora-accent hover:bg-ora-accent-hover " +
  "transition-colors flex justify-center disabled:opacity-50 disabled:pointer-events-none";

export const authOAuthButtonClass =
  "w-full py-2.5 px-4 rounded-lg text-sm font-medium text-ora-secondary bg-ora-surface border border-ora-border " +
  "hover:bg-ora-subtle transition-colors flex items-center justify-center gap-2.5";
