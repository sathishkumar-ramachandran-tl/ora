import { describe, expect, it } from 'vitest';
import tailwindConfig from '../../tailwind.config';
import { brand, navigation, semanticTokens, status, surface } from './tokens';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

describe('Ora design tokens v2', () => {
  it('uses a neutral-first surface system with cobalt accent', () => {
    expect(surface.canvas).toBe('#F2F4F1');
    expect(surface.ink).toBe('#18201D');
    expect(navigation.base).toBe('#17201E');
    expect(brand[500]).toBe('#2367E8');
  });

  it('keeps semantic status colors separate from the Ora accent', () => {
    expect(status.success).toBe('#0F704D');
    expect(status.successSoft).toBe('#E7F7EF');
    expect(status.warning).toBe('#8A560F');
    expect(status.warningSoft).toBe('#FFF3D6');
    expect(status.danger).toBe('#B6352D');
    expect(status.dangerSoft).toBe('#FCE8E6');
    expect(status.info).toBe('#315F8F');
    expect(status.infoSoft).toBe('#EAF3FF');
    expect(status.success).not.toBe(brand[500]);
  });

  it('exposes the semantic token contract used by core shell components', () => {
    expect(Object.keys(semanticTokens).sort()).toEqual([
      'accent',
      'accentHover',
      'accentSoft',
      'accentStrong',
      'borderStrong',
      'borderSubtle',
      'canvas',
      'danger',
      'dangerSoft',
      'info',
      'infoSoft',
      'nav',
      'navMuted',
      'navSurface',
      'success',
      'successSoft',
      'surface',
      'surfaceSubtle',
      'textPrimary',
      'textSecondary',
      'textTertiary',
      'warning',
      'warningSoft',
    ].sort());
  });

  it('defines Tailwind aliases for every high-frequency semantic utility', () => {
    const colors = tailwindConfig.theme.extend.colors as Record<string, any>;
    expect(colors.ora).toMatchObject({
      canvas: expect.stringContaining('--ora-canvas'),
      surface: expect.stringContaining('--ora-surface'),
      'surface-subtle': expect.stringContaining('--ora-surface-subtle'),
      primary: expect.stringContaining('--ora-text-primary'),
      secondary: expect.stringContaining('--ora-text-secondary'),
      tertiary: expect.stringContaining('--ora-text-tertiary'),
      border: expect.stringContaining('--ora-border'),
      nav: expect.stringContaining('--ora-nav'),
      accent: expect.stringContaining('--ora-accent'),
      'accent-strong': expect.stringContaining('--ora-accent-strong'),
      'accent-soft': expect.stringContaining('--ora-accent-soft'),
      'warning-soft': expect.stringContaining('--ora-warning-soft'),
    });
    expect(colors).toMatchObject({
      canvas: expect.stringContaining('--ora-canvas'),
      surface: expect.stringContaining('--ora-surface'),
      foreground: expect.stringContaining('--ora-text-primary'),
      muted: expect.stringContaining('--ora-text-secondary'),
      'border-subtle': expect.stringContaining('--ora-border'),
      accent: expect.stringContaining('--ora-accent'),
    });
  });

  it('keeps the document shell on Ora semantic body classes and CSS variables', () => {
    const indexHtml = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
    const indexCss = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

    expect(indexHtml).toContain('body class="bg-ora-canvas text-ora-primary h-screen overflow-hidden"');
    expect(indexHtml).not.toContain('body class="bg-slate-50 text-slate-900');
    expect(indexCss).toContain('--ora-canvas: 242 244 241');
    expect(indexCss).toContain('--ora-nav: 23 32 30');
    expect(indexCss).toContain('--ora-text-primary: 24 32 29');
    expect(indexCss).toContain('rgb(var(--ora-text-primary, 24 32 29))');
  });
});
