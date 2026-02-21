/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, type PropsWithChildren } from 'react';
import type { TemplateContractResponse } from '../types/definition';

export type DocHintsPayload = NonNullable<TemplateContractResponse['doc_hints']>;

const DocHintsContext = createContext<DocHintsPayload | undefined>(undefined);

type DocHintsProviderProps = PropsWithChildren<{
  docHints?: TemplateContractResponse['doc_hints'];
}>;

export function DocHintsProvider({ docHints, children }: DocHintsProviderProps) {
  return <DocHintsContext.Provider value={docHints ?? undefined}>{children}</DocHintsContext.Provider>;
}

export function useDocHints(): DocHintsPayload | undefined {
  return useContext(DocHintsContext);
}
