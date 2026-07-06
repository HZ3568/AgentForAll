import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MessageContent } from './MessageBubble';

describe('MessageContent', () => {
  it('renders markdown paragraphs, lists, tables, and code blocks', () => {
    render(
      <MessageContent
        text={[
          '**Result**',
          '',
          '- item one',
          '',
          '| A | B |',
          '| - | - |',
          '| 1 | 2 |',
          '',
          '```ts',
          'const value = 1;',
          '```',
        ].join('\n')}
      />,
    );

    expect(screen.getByText('Result').tagName.toLowerCase()).toBe('strong');
    expect(screen.getByText('item one').closest('li')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('const value = 1;')).toBeInTheDocument();
  });
});
