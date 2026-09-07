/**
 * Form primitives.
 *
 * Accessibility notes that are easy to lose in a refactor:
 *  - every control has a real <label for>, not an aria-label
 *  - hints and errors are wired through aria-describedby
 *  - errors set aria-invalid and are announced politely, not as an alert
 *  - choice cards are real checkboxes inside a <fieldset><legend>, so screen
 *    readers announce the group name and the checked state
 */
import { useId, type ReactNode } from 'react';
import { AlertIcon, CheckIcon } from './Icons';

interface BaseFieldProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  autoComplete?: string;
  id?: string;
}

interface TextFieldProps extends BaseFieldProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  inputMode?: 'text' | 'numeric' | 'email';
  maxLength?: number;
  type?: 'text' | 'email';
  onBlur?: () => void;
}

function describedBy(ids: Array<string | false | undefined>): string | undefined {
  const list = ids.filter(Boolean) as string[];
  return list.length ? list.join(' ') : undefined;
}

export function TextField({
  label,
  hint,
  error,
  required,
  value,
  onChange,
  placeholder,
  inputMode = 'text',
  maxLength,
  type = 'text',
  autoComplete,
  onBlur,
  id,
}: TextFieldProps) {
  const auto = useId();
  const fieldId = id ?? auto;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;

  return (
    <div className={`field${error ? ' field--invalid' : ''}`}>
      <label className="field__label" htmlFor={fieldId}>
        {label}
        {!required && <span className="field__hint">Optional</span>}
        {hint && (
          <span className="field__hint" id={hintId}>
            {hint}
          </span>
        )}
      </label>
      <input
        id={fieldId}
        className="field__control"
        type={type}
        value={value}
        placeholder={placeholder}
        inputMode={inputMode}
        maxLength={maxLength}
        autoComplete={autoComplete}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy([hint && hintId, error && errorId])}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
      />
      {error && (
        <p className="field__error" id={errorId}>
          <AlertIcon size={15} />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}

interface SelectFieldProps extends BaseFieldProps {
  value: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<{ value: string; label: string }>;
  placeholder?: string;
}

export function SelectField({
  label,
  hint,
  error,
  required,
  value,
  onChange,
  options,
  placeholder,
  autoComplete,
  id,
}: SelectFieldProps) {
  const auto = useId();
  const fieldId = id ?? auto;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;

  return (
    <div className={`field${error ? ' field--invalid' : ''}`}>
      <label className="field__label" htmlFor={fieldId}>
        {label}
        {hint && (
          <span className="field__hint" id={hintId}>
            {hint}
          </span>
        )}
      </label>
      <select
        id={fieldId}
        className="field__control"
        value={value}
        autoComplete={autoComplete}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy([hint && hintId, error && errorId])}
        onChange={(e) => onChange(e.target.value)}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="field__error" id={errorId}>
          <AlertIcon size={15} />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}

interface TextAreaFieldProps extends BaseFieldProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength: number;
}

export function TextAreaField({
  label,
  hint,
  error,
  value,
  onChange,
  placeholder,
  maxLength,
  id,
}: TextAreaFieldProps) {
  const auto = useId();
  const fieldId = id ?? auto;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;
  const countId = `${fieldId}-count`;
  const over = value.length > maxLength;

  return (
    <div className={`field${error ? ' field--invalid' : ''}`}>
      <label className="field__label" htmlFor={fieldId}>
        {label}
        {hint && (
          <span className="field__hint" id={hintId}>
            {hint}
          </span>
        )}
      </label>
      <textarea
        id={fieldId}
        className="field__control"
        value={value}
        placeholder={placeholder}
        aria-invalid={error || over ? true : undefined}
        aria-describedby={describedBy([hint && hintId, countId, error && errorId])}
        onChange={(e) => onChange(e.target.value)}
      />
      <span className={`char-count${over ? ' char-count--over' : ''}`} id={countId}>
        {value.length} / {maxLength} characters
      </span>
      {error && (
        <p className="field__error" id={errorId}>
          <AlertIcon size={15} />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}

interface ChoiceProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: string;
  description?: string;
  name?: string;
}

export function Choice({ checked, onChange, title, description, name }: ChoiceProps) {
  return (
    <label className="choice">
      <input
        type="checkbox"
        name={name}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="choice__box" aria-hidden="true">
        <CheckIcon size={13} />
      </span>
      <span className="choice__body">
        <strong>{title}</strong>
        {description && <span>{description}</span>}
      </span>
    </label>
  );
}

export function ChoiceGroup({
  legend,
  intro,
  children,
}: {
  legend: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  return (
    <fieldset className="choices">
      <legend>{legend}</legend>
      {intro && <div className="choices__intro">{intro}</div>}
      {children}
    </fieldset>
  );
}
