// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import TwinLayerShell from './TwinLayerShell';

describe('TwinLayerShell', () => {
  it('toggles on space and ignores input typing targets', () => {
    const onToggle = vi.fn();

    render(
      <TwinLayerShell
        layer="joyful"
        onToggleLayer={onToggle}
        joyfulView={<div>Joyful</div>}
        technicalView={<div>Technical</div>}
      />,
    );

    fireEvent.keyDown(window, { code: 'Space' });
    expect(onToggle).toHaveBeenCalledTimes(1);

    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();

    fireEvent.keyDown(input, { code: 'Space' });
    expect(onToggle).toHaveBeenCalledTimes(1);

    document.body.removeChild(input);

    expect(screen.getByTestId('cirpass-layer-joyful')).toBeTruthy();
  });
});
