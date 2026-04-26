// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TemplateContractDiagnostics } from './TemplateContractDiagnostics';

describe('TemplateContractDiagnostics', () => {
  it('shows a ready state when the contract has full editor coverage', () => {
    render(<TemplateContractDiagnostics unsupportedNodes={[]} dropinResolutionReport={[]} />);

    expect(screen.getByText('Template contract ready')).toBeTruthy();
    expect(screen.getByText('Unsupported nodes: 0')).toBeTruthy();
    expect(screen.getByText('Unresolved drop-ins: 0')).toBeTruthy();
  });

  it('explains DPP impact without incorrectly blocking draft save', () => {
    render(
      <TemplateContractDiagnostics
        unsupportedNodes={[
          {
            path: 'Nameplate/BinaryPayload',
            idShort: 'BinaryPayload',
            modelType: 'Blob',
            reasons: ['unsupported_model_type:Blob'],
          },
        ]}
        dropinResolutionReport={[
          {
            status: 'missing',
            reason: 'source_template_not_cached',
            path: 'Nameplate/Address',
          },
        ]}
      />,
    );

    expect(screen.getByText('Template contract needs review')).toBeTruthy();
    expect(screen.getByText('Unsupported nodes: 1')).toBeTruthy();
    expect(screen.getByText('Unresolved drop-ins: 1')).toBeTruthy();
    expect(
      screen.getByText(
        'Draft save remains available. Publishing can be blocked until the listed paths are supported.',
      ),
    ).toBeTruthy();
    expect(screen.getByText(/Nameplate\/BinaryPayload: Unsupported model type: Blob/i)).toBeTruthy();
    expect(screen.getByText(/Nameplate\/Address: source template not cached/i)).toBeTruthy();
  });

  it('uses sandbox-specific impact text for public template previews', () => {
    render(
      <TemplateContractDiagnostics
        mode="sandbox"
        unsupportedNodes={[
          {
            path: 'Nameplate/Operation',
            idShort: 'Operation',
            modelType: 'Operation',
            reasons: ['unsupported_model_type:Operation'],
          },
        ]}
      />,
    );

    expect(
      screen.getByText('Preview and export may fail or require JSON edits for the listed paths.'),
    ).toBeTruthy();
  });
});
