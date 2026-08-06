/**
 * Lightweight markdown renderer for AI chat responses.
 * Handles: headings, bullets, numbered lists, bold/italic/code inline,
 * pipe tables, blockquotes, horizontal rules, fenced code blocks.
 * Supports dark (default) and light variants.
 */
import React from 'react';

type Variant = 'dark' | 'light';

const THEME = {
  dark: {
    heading1: 'font-bold text-white text-lg mt-3 mb-1',
    heading2: 'font-bold text-white text-base mt-3 mb-0.5',
    heading3: 'font-semibold text-slate-100 text-sm mt-2 mb-0.5',
    heading4: 'font-semibold text-slate-200 text-sm mt-1.5',
    bullet: 'text-indigo-400',
    subBullet: 'text-slate-500',
    subText: 'text-slate-300',
    blockquote: 'border-l-2 border-indigo-500/60 pl-3 my-1 text-sm text-slate-300 italic',
    hr: 'border-slate-700 my-2',
    tableWrapper: 'overflow-x-auto my-2 rounded-lg border border-slate-600/50',
    tableHead: 'bg-slate-700/60',
    tableHeadCell: 'px-3 py-1.5 text-left font-semibold text-slate-200 border-b border-slate-600',
    tableRow: 'border-b border-slate-700/40 hover:bg-slate-700/20 transition-colors',
    tableCell: 'px-3 py-1.5 text-slate-300',
    pre: 'bg-slate-800/80 rounded-lg px-3 py-2 text-xs font-mono text-emerald-300 my-1.5 overflow-x-auto whitespace-pre-wrap',
    strong: 'font-semibold text-white',
    em: 'italic text-slate-300',
    code: 'bg-slate-800 px-1 rounded text-xs font-mono text-emerald-300',
    check: 'text-emerald-400 font-medium',
    cross: 'text-red-400 font-medium',
  },
  light: {
    heading1: 'font-bold text-slate-900 text-lg mt-3 mb-1',
    heading2: 'font-bold text-slate-900 text-base mt-3 mb-0.5',
    heading3: 'font-semibold text-slate-800 text-sm mt-2 mb-0.5',
    heading4: 'font-semibold text-slate-700 text-sm mt-1.5',
    bullet: 'text-indigo-500',
    subBullet: 'text-slate-400',
    subText: 'text-slate-600',
    blockquote: 'border-l-2 border-indigo-400/60 pl-3 my-1 text-sm text-slate-600 italic',
    hr: 'border-slate-200 my-2',
    tableWrapper: 'overflow-x-auto my-2 rounded-lg border border-slate-200',
    tableHead: 'bg-slate-100',
    tableHeadCell: 'px-3 py-1.5 text-left font-semibold text-slate-700 border-b border-slate-200',
    tableRow: 'border-b border-slate-100 hover:bg-slate-50 transition-colors',
    tableCell: 'px-3 py-1.5 text-slate-600',
    pre: 'bg-slate-100 rounded-lg px-3 py-2 text-xs font-mono text-emerald-700 my-1.5 overflow-x-auto whitespace-pre-wrap',
    strong: 'font-semibold text-slate-900',
    em: 'italic text-slate-600',
    code: 'bg-slate-100 px-1 rounded text-xs font-mono text-emerald-700',
    check: 'text-emerald-600 font-medium',
    cross: 'text-red-600 font-medium',
  },
};

function formatInline(text: string, t: typeof THEME.dark): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i} className={t.strong}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2)
      return <em key={i} className={t.em}>{part.slice(1, -1)}</em>;
    if (part.startsWith('`') && part.endsWith('`'))
      return <code key={i} className={t.code}>{part.slice(1, -1)}</code>;
    if (part.includes('✓'))
      return <span key={i} className={t.check}>{part}</span>;
    if (part.includes('✗'))
      return <span key={i} className={t.cross}>{part}</span>;
    return part;
  });
}

function renderTable(tableLines: string[], key: number, t: typeof THEME.dark) {
  const parseRow = (line: string) => line.split('|').slice(1, -1).map(c => c.trim());
  const isSep = (line: string) => /^\|[\s\-|:]+\|$/.test(line.trim());
  const nonSep = tableLines.filter(l => !isSep(l));
  if (nonSep.length === 0) return null;
  const [header, ...body] = nonSep;
  const headerCells = parseRow(header);
  return (
    <div key={key} className={t.tableWrapper}>
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className={t.tableHead}>
            {headerCells.map((cell, i) => (
              <th key={i} className={t.tableHeadCell}>{formatInline(cell, t)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri} className={t.tableRow}>
              {parseRow(row).map((cell, ci) => (
                <td key={ci} className={t.tableCell}>{formatInline(cell, t)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface RichTextProps {
  content: string;
  variant?: Variant;
  className?: string;
}

export const RichText: React.FC<RichTextProps> = ({ content, variant = 'dark', className = '' }) => {
  const t = THEME[variant];
  const lines = content.split('\n');
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let inCode = false;
  let codeLines: string[] = [];

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.startsWith('```')) {
      if (inCode) {
        nodes.push(<pre key={i} className={t.pre}>{codeLines.join('\n')}</pre>);
        codeLines = []; inCode = false;
      } else { inCode = true; }
      i++; continue;
    }
    if (inCode) { codeLines.push(line); i++; continue; }

    // Pipe table
    if (line.trim().startsWith('|')) {
      const tl: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { tl.push(lines[i]); i++; }
      nodes.push(renderTable(tl, nodes.length, t));
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      nodes.push(
        <blockquote key={i} className={t.blockquote}>{formatInline(line.slice(2), t)}</blockquote>
      );
      i++; continue;
    }

    // HR
    if (/^-{3,}$/.test(line.trim())) {
      nodes.push(<hr key={i} className={t.hr} />);
      i++; continue;
    }

    // Headings
    if (line.startsWith('# '))   { nodes.push(<h1 key={i} className={t.heading1}>{formatInline(line.slice(2), t)}</h1>); i++; continue; }
    if (line.startsWith('## '))  { nodes.push(<h2 key={i} className={t.heading2}>{formatInline(line.slice(3), t)}</h2>); i++; continue; }
    if (line.startsWith('### ')) { nodes.push(<h3 key={i} className={t.heading3}>{formatInline(line.slice(4), t)}</h3>); i++; continue; }
    if (/^#{4,}\s/.test(line))   { nodes.push(<p key={i} className={t.heading4}>{formatInline(line.replace(/^#{4,}\s/, ''), t)}</p>); i++; continue; }

    // Bullet
    if (/^[*\-•]\s/.test(line)) {
      nodes.push(
        <div key={i} className="flex gap-2 text-sm leading-relaxed">
          <span className={`${t.bullet} mt-0.5 flex-shrink-0`}>•</span>
          <span>{formatInline(line.slice(2), t)}</span>
        </div>
      );
      i++; continue;
    }

    // Numbered list
    if (/^\d+\.\s/.test(line)) {
      const num = line.match(/^(\d+)\./)?.[1] ?? '1';
      nodes.push(
        <div key={i} className="flex gap-2 text-sm leading-relaxed">
          <span className={`${t.bullet} font-mono text-xs mt-0.5 flex-shrink-0 w-4`}>{num}.</span>
          <span>{formatInline(line.replace(/^\d+\.\s/, ''), t)}</span>
        </div>
      );
      i++; continue;
    }

    // Indented sub-bullet
    if (/^\s{2,}[*\-]\s/.test(line)) {
      nodes.push(
        <div key={i} className="flex gap-2 text-sm leading-relaxed ml-5">
          <span className={`${t.subBullet} mt-0.5 flex-shrink-0`}>◦</span>
          <span className={t.subText}>{formatInline(line.replace(/^\s+[*\-]\s/, ''), t)}</span>
        </div>
      );
      i++; continue;
    }

    if (line.trim() === '') { nodes.push(<div key={i} className="h-1" />); i++; continue; }

    nodes.push(<p key={i} className="text-sm leading-relaxed">{formatInline(line, t)}</p>);
    i++;
  }

  return <div className={`space-y-0.5 ${className}`}>{nodes}</div>;
};
