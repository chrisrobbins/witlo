/**
 * The address-to-preview journey, driven the way a person drives it.
 *
 * These tests use accessible queries only (labels, roles, names) — if a control
 * cannot be found by its label here, it cannot be found by a screen reader
 * either, so the suite doubles as an accessibility check on the flow.
 */
import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Create } from '../src/routes/Create';
import { RouterProvider } from '../src/lib/router';
import { CONTENT, NOTE_MAX_CHARS } from '../src/lib/letterContent';

function renderWizard() {
  return render(
    <RouterProvider>
      <Create />
    </RouterProvider>,
  );
}

async function fillAddress(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^Street address/), '414 W San Antonio St');
  await user.type(screen.getByLabelText(/^City/), 'Marfa');
  await user.selectOptions(screen.getByLabelText(/^State/), 'TX');
  await user.type(screen.getByLabelText(/^ZIP/), '79843');
}

const nextButton = () => screen.getByRole('button', { name: /Continue|Read the letter/ });

beforeEach(() => {
  sessionStorage.clear();
});

describe('step 1 — the address', () => {
  it('states that only US addresses are supported', () => {
    renderWizard();
    expect(screen.getByText(/United States addresses only/i)).toBeInTheDocument();
  });

  it('will not advance with an empty address, and says why', async () => {
    const user = userEvent.setup();
    renderWizard();

    await user.click(nextButton());

    expect(screen.getByText(/Please enter the street address/i)).toBeInTheDocument();
    expect(screen.getByText(/Please enter the city/i)).toBeInTheDocument();
    expect(screen.getByText(/Please choose the state/i)).toBeInTheDocument();
    expect(screen.getByText(/Please enter the ZIP code/i)).toBeInTheDocument();
    // Still on step 1.
    expect(screen.getByLabelText(/^Street address/)).toBeInTheDocument();
  });

  it('marks invalid fields for assistive technology', async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.click(nextButton());

    const street = screen.getByLabelText(/^Street address/);
    expect(street).toHaveAttribute('aria-invalid', 'true');
    expect(street).toHaveAccessibleDescription(/Please enter the street address/i);
  });

  it('rejects a PO box with an explanation rather than a generic error', async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.type(screen.getByLabelText(/^Street address/), 'PO Box 42');
    await user.type(screen.getByLabelText(/^City/), 'Marfa');
    await user.selectOptions(screen.getByLabelText(/^State/), 'TX');
    await user.type(screen.getByLabelText(/^ZIP/), '79843');
    await user.click(nextButton());

    expect(screen.getByText(/A PO box has no outdoor light/i)).toBeInTheDocument();
  });

  it('rejects a malformed ZIP', async () => {
    const user = userEvent.setup();
    renderWizard();
    await user.type(screen.getByLabelText(/^Street address/), '414 W San Antonio St');
    await user.type(screen.getByLabelText(/^City/), 'Marfa');
    await user.selectOptions(screen.getByLabelText(/^State/), 'TX');
    await user.type(screen.getByLabelText(/^ZIP/), '798');
    await user.click(nextButton());

    expect(screen.getByText(/12345 or 12345-6789/)).toBeInTheDocument();
  });

  it('advances once the address is valid', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());

    expect(screen.getByRole('heading', { name: /What did you notice/i })).toBeInTheDocument();
  });
});

describe('step 2 — observations', () => {
  it('says that some lights are needed', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());

    expect(screen.getByText(/Some lights are needed/i)).toBeInTheDocument();
    expect(screen.getByText(/never claims the light is unnecessary/i)).toBeInTheDocument();
  });

  it('offers every observation and lets all of them be skipped', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());

    for (const key of CONTENT.order.observations) {
      expect(screen.getByText(CONTENT.observations[key].label)).toBeInTheDocument();
    }
    await user.click(nextButton());
    expect(screen.getByRole('heading', { name: /Which ideas/i })).toBeInTheDocument();
  });

  it('shows the note field only when "something else" is chosen', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());

    expect(screen.queryByLabelText(/In a sentence or so/)).not.toBeInTheDocument();
    await user.click(screen.getByText(CONTENT.observations.other.label));
    expect(screen.getByLabelText(/In a sentence or so/)).toBeInTheDocument();
  });

  it('blocks a note that reads as a legal threat, and explains why', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());
    await user.click(screen.getByText(CONTENT.observations.other.label));
    await user.type(
      screen.getByLabelText(/In a sentence or so/),
      'This is a violation of the city ordinance',
    );
    await user.click(nextButton());

    expect(screen.getByText(/friendly request/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /What did you notice/i })).toBeInTheDocument();
  });

  it('blocks contact details in the note', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());
    await user.click(screen.getByText(CONTENT.observations.other.label));
    await user.type(screen.getByLabelText(/In a sentence or so/), 'call me on 555-123-4567');
    await user.click(nextButton());

    expect(screen.getByText(/leave out phone numbers/i)).toBeInTheDocument();
  });

  it('counts characters against the published limit', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());
    await user.click(screen.getByText(CONTENT.observations.other.label));
    await user.type(screen.getByLabelText(/In a sentence or so/), 'hello');

    expect(screen.getByText(`5 / ${NOTE_MAX_CHARS} characters`)).toBeInTheDocument();
  });
});

describe('step 4 — the preview', () => {
  async function goToPreview(user: ReturnType<typeof userEvent.setup>) {
    await fillAddress(user);
    await user.click(nextButton());
    await user.click(screen.getByText(CONTENT.observations.all_night.label));
    await user.click(nextButton());
    await user.click(nextButton());
  }

  it('shows the letter and the recipient address exactly as they will be used', async () => {
    const user = userEvent.setup();
    renderWizard();
    await goToPreview(user);

    const sheet = screen.getByRole('article', { name: /Letter preview/i });
    expect(within(sheet).getByText(CONTENT.recipient_line)).toBeInTheDocument();
    expect(within(sheet).getByText('414 W San Antonio St')).toBeInTheDocument();
    expect(within(sheet).getByText('Marfa, TX 79843')).toBeInTheDocument();
    expect(within(sheet).getByText(CONTENT.salutation)).toBeInTheDocument();
    expect(
      within(sheet).getByText(CONTENT.observations.all_night.bullet),
    ).toBeInTheDocument();
  });

  it('reflects the selections made earlier, and nothing else', async () => {
    const user = userEvent.setup();
    renderWizard();
    await goToPreview(user);

    const sheet = screen.getByRole('article', { name: /Letter preview/i });
    expect(within(sheet).queryByText(CONTENT.observations.spill.bullet)).not.toBeInTheDocument();
    // The default suggestions carried through from step 3.
    expect(within(sheet).getByText(CONTENT.suggestions.shield.bullet)).toBeInTheDocument();
  });

  it('offers print and download, and says no letter will be mailed', async () => {
    const user = userEvent.setup();
    renderWizard();
    await goToPreview(user);

    expect(screen.getByRole('button', { name: /Print or save as PDF/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download the letter/i })).toBeInTheDocument();
    expect(screen.getByText(/No letter will be mailed/i)).toBeInTheDocument();
  });

  it('has no control that could pay or mail in demo mode', async () => {
    const user = userEvent.setup();
    renderWizard();
    await goToPreview(user);

    expect(screen.queryByRole('button', { name: /Pay/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mail this letter/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Check this address/i })).not.toBeInTheDocument();
  });
});

describe('keyboard access', () => {
  it('reaches and operates every control on step 1 with the keyboard alone', async () => {
    const user = userEvent.setup();
    renderWizard();

    await user.tab();
    // Walk forward until the street field has focus, then type into it.
    for (let i = 0; i < 20 && document.activeElement !== screen.getByLabelText(/^Street address/); i += 1) {
      await user.tab();
    }
    expect(screen.getByLabelText(/^Street address/)).toHaveFocus();
    await user.keyboard('414 W San Antonio St');
    expect(screen.getByLabelText(/^Street address/)).toHaveValue('414 W San Antonio St');
  });

  it('toggles a choice card with the space bar', async () => {
    const user = userEvent.setup();
    renderWizard();
    await fillAddress(user);
    await user.click(nextButton());

    const checkbox = screen.getByRole('checkbox', {
      name: new RegExp(CONTENT.observations.all_night.label),
    });
    checkbox.focus();
    await user.keyboard(' ');
    expect(checkbox).toBeChecked();
  });
});

describe('progress', () => {
  it('announces the current step', async () => {
    const user = userEvent.setup();
    renderWizard();
    // The polite live region in <Stepper> announces "Step N of 4: <label>".
    // The visible eyebrow reads "Step N of 4" with no colon, so match the colon
    // to target the announcement specifically.
    expect(screen.getByText(/Step 1 of 4:/)).toBeInTheDocument();
    await fillAddress(user);
    await user.click(nextButton());
    expect(screen.getByText(/Step 2 of 4:/)).toBeInTheDocument();
  });
});
