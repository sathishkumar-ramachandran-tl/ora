import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthShell } from './AuthShell';

describe('AuthShell', () => {
  it('renders a branded SaaS auth surface without hiding the form', () => {
    render(
      <AuthShell title="Welcome back" subtitle="Sign in to continue.">
        <button>Continue</button>
      </AuthShell>
    );

    expect(screen.getByText('Adaptive workspaces')).toBeInTheDocument();
    expect(screen.getByText('A calm operating layer for personal work and shared teams.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
  });
});
