import React from 'react';

/** Shared shell for every /auth/* screen — a minimal centered white card,
 * consistent with a Google Sign-in-style layout: generous whitespace, a
 * single clear primary action, subtle branding instead of the app's usual
 * glassy/dark surface treatment. */
export const AuthShell: React.FC<{ title: string; subtitle?: React.ReactNode; children: React.ReactNode }> = ({
  title, subtitle, children,
}) => (
  <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
    <div className="w-full max-w-[400px]">
      <div className="flex flex-col items-center mb-8">
        <OraMark />
        <span className="mt-3 text-lg font-semibold text-slate-900 tracking-tight">Ora</span>
      </div>

      <div className="w-full bg-white border border-slate-200 rounded-2xl shadow-sm p-8">
        <div className="text-center mb-7">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
          {subtitle && <p className="text-slate-500 text-sm mt-1.5">{subtitle}</p>}
        </div>
        {children}
      </div>
    </div>
  </div>
);

export const OraMark: React.FC<{ size?: number }> = ({ size = 40 }) => (
  <div
    className="rounded-xl bg-brand-600 flex items-center justify-center shadow-sm"
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
  "block w-full pl-10 pr-3 py-2.5 bg-white border border-slate-300 rounded-lg text-slate-900 placeholder:text-slate-400 " +
  "focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-shadow text-sm";

export const authPrimaryButtonClass =
  "w-full py-2.5 px-4 rounded-lg text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 " +
  "transition-colors flex justify-center disabled:opacity-50 disabled:pointer-events-none";

export const authOAuthButtonClass =
  "w-full py-2.5 px-4 rounded-lg text-sm font-medium text-slate-700 bg-white border border-slate-300 " +
  "hover:bg-slate-50 transition-colors flex items-center justify-center gap-2.5";
