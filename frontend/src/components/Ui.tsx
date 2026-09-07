import type { ReactNode } from 'react';
import { AlertIcon, CheckIcon, InfoIcon } from './Icons';

export function Callout({
  tone = 'neutral',
  title,
  children,
}: {
  tone?: 'neutral' | 'warm' | 'gold' | 'ok';
  title?: string;
  children: ReactNode;
}) {
  const Icon = tone === 'warm' ? AlertIcon : tone === 'ok' ? CheckIcon : InfoIcon;
  const cls = tone === 'neutral' ? 'callout' : `callout callout--${tone}`;
  return (
    <div className={cls} role={tone === 'warm' ? 'note' : undefined}>
      <span className="callout__icon">
        <Icon size={tone === 'ok' ? 16 : 19} />
      </span>
      <div>
        {title && <p><strong>{title}</strong></p>}
        {children}
      </div>
    </div>
  );
}

export interface StepDef {
  id: string;
  label: string;
}

export function Stepper({ steps, currentIndex }: { steps: StepDef[]; currentIndex: number }) {
  const pct = Math.round(((currentIndex + 1) / steps.length) * 100);
  return (
    <nav className="stepper" aria-label="Progress">
      <ol className="stepper__list">
        {steps.map((step, i) => {
          const state = i < currentIndex ? 'done' : i === currentIndex ? 'current' : 'todo';
          return (
            <li
              key={step.id}
              className={`stepper__item stepper__item--${state}`}
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <span className="stepper__dot" aria-hidden="true">
                {state === 'done' ? <CheckIcon size={11} /> : i + 1}
              </span>
              <span>
                <span className="visually-hidden">
                  {state === 'done' ? 'Completed step: ' : state === 'current' ? 'Current step: ' : 'Upcoming step: '}
                </span>
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="stepper__bar" role="presentation">
        <span style={{ width: `${pct}%` }} />
      </div>
      <p className="visually-hidden" aria-live="polite">
        Step {currentIndex + 1} of {steps.length}: {steps[currentIndex]?.label}
      </p>
    </nav>
  );
}

export function StatusBadge({
  tone,
  children,
}: {
  tone: 'ok' | 'pending' | 'stop' | 'neutral';
  children: ReactNode;
}) {
  const cls = tone === 'neutral' ? 'status-badge' : `status-badge status-badge--${tone}`;
  return (
    <span className={cls}>
      <span className="status-badge__dot" aria-hidden="true" />
      {children}
    </span>
  );
}

/**
 * `level` exists so a page whose main heading is a section head still has
 * exactly one <h1>. A page with no <h1> gives screen-reader users nothing to
 * orient by, and the wizard's step heading is genuinely the page's title.
 */
export function SectionHead({
  eyebrow,
  title,
  children,
  id,
  level = 2,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  id?: string;
  level?: 1 | 2 | 3;
}) {
  const Heading = `h${level}` as 'h1' | 'h2' | 'h3';
  return (
    <header className="section__head">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <Heading id={id}>{title}</Heading>
      {children}
    </header>
  );
}
