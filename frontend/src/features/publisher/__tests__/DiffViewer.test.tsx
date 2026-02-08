// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DiffViewer } from '../components/DiffViewer';

describe('DiffViewer', () => {
  it('renders empty state when no differences', () => {
    render(
      <DiffViewer
        diff={{ from_rev: 1, to_rev: 2, added: [], removed: [], changed: [] }}
      />,
    );
    expect(screen.getByText(/No differences/)).toBeTruthy();
  });

  it('renders added entries with count badge', () => {
    render(
      <DiffViewer
        diff={{
          from_rev: 1,
          to_rev: 2,
          added: [
            { path: 'submodels.name', operation: 'added', old_value: null, new_value: 'Test' },
          ],
          removed: [],
          changed: [],
        }}
      />,
    );
    expect(screen.getByText('+1')).toBeTruthy();
    expect(screen.getByText('-0')).toBeTruthy();
    expect(screen.getByText('~0')).toBeTruthy();
    expect(screen.getByText('name')).toBeTruthy();
    expect(screen.getByText('Test')).toBeTruthy();
  });

  it('renders removed entries', () => {
    render(
      <DiffViewer
        diff={{
          from_rev: 1,
          to_rev: 2,
          added: [],
          removed: [
            { path: 'metadata.version', operation: 'removed', old_value: '1.0', new_value: null },
          ],
          changed: [],
        }}
      />,
    );
    expect(screen.getByText('-1')).toBeTruthy();
    expect(screen.getByText('version')).toBeTruthy();
    expect(screen.getByText('1.0')).toBeTruthy();
  });

  it('renders changed entries with old and new values', () => {
    render(
      <DiffViewer
        diff={{
          from_rev: 1,
          to_rev: 3,
          added: [],
          removed: [],
          changed: [
            {
              path: 'assetAdministrationShells.idShort',
              operation: 'changed',
              old_value: 'OldName',
              new_value: 'NewName',
            },
          ],
        }}
      />,
    );
    expect(screen.getByText('~1')).toBeTruthy();
    expect(screen.getByText('Old')).toBeTruthy();
    expect(screen.getByText('New')).toBeTruthy();
    expect(screen.getByText('OldName')).toBeTruthy();
    expect(screen.getByText('NewName')).toBeTruthy();
  });

  it('groups entries by top-level path segment', () => {
    render(
      <DiffViewer
        diff={{
          from_rev: 1,
          to_rev: 2,
          added: [
            { path: 'submodels.a', operation: 'added', old_value: null, new_value: 1 },
            { path: 'submodels.b', operation: 'added', old_value: null, new_value: 2 },
            { path: 'assets.x', operation: 'added', old_value: null, new_value: 3 },
          ],
          removed: [],
          changed: [],
        }}
      />,
    );
    expect(screen.getAllByText('assets').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('submodels').length).toBeGreaterThanOrEqual(1);
  });

  it('collapses and expands groups', () => {
    render(
      <DiffViewer
        diff={{
          from_rev: 1,
          to_rev: 2,
          added: [
            { path: 'group1.field', operation: 'added', old_value: null, new_value: 'val' },
          ],
          removed: [],
          changed: [],
        }}
      />,
    );

    // Entry is visible initially (groups start expanded)
    expect(screen.getByText('field')).toBeTruthy();

    // Click group header to collapse
    fireEvent.click(screen.getByText('group1'));
    expect(screen.queryByText('field')).toBeNull();

    // Click again to expand
    fireEvent.click(screen.getByText('group1'));
    expect(screen.getByText('field')).toBeTruthy();
  });

  it('shows revision numbers in header', () => {
    render(
      <DiffViewer
        diff={{
          from_rev: 3,
          to_rev: 7,
          added: [{ path: 'x', operation: 'added', old_value: null, new_value: 1 }],
          removed: [],
          changed: [],
        }}
      />,
    );
    expect(screen.getByText(/Diff:.*#3.*→.*#7/)).toBeTruthy();
  });
});
