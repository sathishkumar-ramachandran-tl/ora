import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RichText } from './RichText';

describe('RichText', () => {
  it('renders plain text content', () => {
    render(<RichText content="Hello world" />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('renders a heading with the dark variant styling', () => {
    render(<RichText content="## Section Title" variant="dark" />);
    const heading = screen.getByText('Section Title');
    expect(heading).toBeInTheDocument();
    expect(heading.className).toContain('text-white');
  });

  it('renders bold text inside a paragraph', () => {
    render(<RichText content="This is **bold** text" />);
    expect(screen.getByText('bold').tagName).toBe('STRONG');
  });
});
