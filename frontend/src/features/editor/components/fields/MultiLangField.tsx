import { useState } from 'react';
import { Controller } from 'react-hook-form';
import type { FieldProps } from '../../types/formTypes';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

export function MultiLangField({ name, control, node }: FieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const requiredLangs = node.smt?.required_lang ?? [];
  const [newLang, setNewLang] = useState('');

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const current =
          field.value && typeof field.value === 'object' && !Array.isArray(field.value)
            ? (field.value as Record<string, string>)
            : {};

        // Dynamic language list: required + existing + user-added (no hardcoded list)
        const languages = Array.from(
          new Set([...requiredLangs, ...Object.keys(current)]),
        );

        const addLanguage = () => {
          const lang = newLang.trim().toLowerCase();
          if (lang && !languages.includes(lang)) {
            field.onChange({ ...current, [lang]: '' });
            setNewLang('');
          }
        };

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
          >
            {requiredLangs.length > 0 && (
              <p className="text-xs text-gray-400">
                Required languages: {requiredLangs.join(', ')}
              </p>
            )}
            <div className="space-y-2">
              {languages.map((lang) => (
                <div key={lang} className="flex items-center gap-2">
                  <span className="w-10 text-xs font-medium uppercase text-gray-500">
                    {lang}
                  </span>
                  <input
                    type="text"
                    className="flex-1 border rounded-md px-3 py-2 text-sm"
                    placeholder={node.smt?.example_value ?? undefined}
                    value={current[lang] ?? ''}
                    onChange={(e) => {
                      field.onChange({ ...current, [lang]: e.target.value });
                    }}
                  />
                  {!requiredLangs.includes(lang) && (
                    <button
                      type="button"
                      className="text-xs text-red-500 hover:text-red-600"
                      onClick={() => {
                        const next = { ...current };
                        delete next[lang];
                        field.onChange(next);
                      }}
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  className="w-20 border rounded-md px-2 py-1 text-xs"
                  placeholder="e.g. ja"
                  value={newLang}
                  onChange={(e) => setNewLang(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addLanguage();
                    }
                  }}
                />
                <button
                  type="button"
                  className="text-sm text-primary hover:text-primary/80"
                  onClick={addLanguage}
                >
                  Add language
                </button>
              </div>
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
