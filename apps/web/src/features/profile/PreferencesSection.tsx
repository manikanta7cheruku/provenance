import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { fetchPreferences, savePreferences } from "../../lib/profile-api";
import type { Preferences } from "../../lib/profile-api";
import { useAsync } from "../../lib/useAsync";
import { useFormSubmit } from "../../lib/useFormSubmit";
import { ActionButton, Button, Checkbox, Notice, Section, Select, Skeleton, TextArea, TextField } from "../../ui";

const EMPLOYMENT_TYPES = [
  { value: "full_time", label: "Full time" },
  { value: "part_time", label: "Part time" },
  { value: "internship", label: "Internship" },
  { value: "contract", label: "Contract" },
  { value: "freelance", label: "Freelance" },
] as const;

const CURRENCIES = ["INR", "USD", "CAD", "GBP", "EUR", "AED", "SGD", "AUD"] as const;

interface FormValues {
  target_roles: string;
  authorized_countries: string;
  needs_sponsorship: string;
  locations: string;
  open_to_relocate: string;
  remote_preference: string;
  employment_types: string[];
  min_salary_amount: string;
  min_salary_currency: string;
  exclusions: string;
}

const lines = (value: string): string[] => value.split("\n").map((line) => line.trim()).filter(Boolean);
const triState = (value: boolean | null): string => (value === null ? "" : value ? "yes" : "no");
const fromTriState = (value: string): boolean | null => (value === "" ? null : value === "yes");

function toValues(preferences: Preferences): FormValues {
  return {
    target_roles: preferences.target_roles.join("\n"),
    authorized_countries: preferences.authorized_countries.join("\n"),
    needs_sponsorship: triState(preferences.needs_sponsorship),
    locations: preferences.locations.join("\n"),
    open_to_relocate: triState(preferences.open_to_relocate),
    remote_preference: preferences.remote_preference ?? "",
    employment_types: preferences.employment_types,
    min_salary_amount: preferences.min_salary_amount?.toString() ?? "",
    min_salary_currency: preferences.min_salary_currency ?? "",
    exclusions: preferences.exclusions.join("\n"),
  };
}

function toPreferences(values: FormValues): Preferences {
  return {
    target_roles: lines(values.target_roles),
    authorized_countries: lines(values.authorized_countries),
    needs_sponsorship: fromTriState(values.needs_sponsorship),
    locations: lines(values.locations),
    open_to_relocate: fromTriState(values.open_to_relocate),
    remote_preference: (values.remote_preference || null) as Preferences["remote_preference"],
    employment_types: values.employment_types,
    min_salary_amount: values.min_salary_amount ? Number(values.min_salary_amount) : null,
    min_salary_currency: values.min_salary_currency || null,
    exclusions: lines(values.exclusions),
  };
}

export function PreferencesSection() {
  const { data, error, loading, reload } = useAsync((signal) => fetchPreferences(signal), []);
  const form = useFormSubmit();
  const [values, setValues] = useState<FormValues | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setValues(toValues(data));
  }, [data]);

  if (error) {
    return (
      <Section title="What you are looking for">
        <Notice tone="danger" title="Your preferences could not be loaded">
          <p>{error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={reload}>Try again</ActionButton>
          </p>
        </Notice>
      </Section>
    );
  }
  if (loading || !values) {
    return (
      <Section title="What you are looking for">
        <Skeleton label="Loading your preferences" lines={4} />
      </Section>
    );
  }

  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    setSaved(false);
    setValues((previous) => (previous ? { ...previous, [key]: value } : previous));
  };

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!values) return;
    const errors: Record<string, string> = {};
    if (values.min_salary_amount && !/^\d{1,10}$/.test(values.min_salary_amount)) {
      errors.min_salary_amount = "Enter a whole number, without commas.";
    }
    if (values.min_salary_amount && !values.min_salary_currency) {
      errors.min_salary_currency = "Choose a currency.";
    }
    if (!values.min_salary_amount && values.min_salary_currency) {
      errors.min_salary_amount = "Enter an amount, or clear the currency.";
    }
    await form.submit(errors, async () => {
      setValues(toValues(await savePreferences(toPreferences(values))));
      setSaved(true);
    });
  }

  return (
    <Section title="What you are looking for">
      <p className="entries__lead">
        These answers decide which jobs are not for you before any scoring happens, such as the wrong
        country or a role type you rule out. Leave a question blank if you are not sure yet.
      </p>
      <form ref={form.formRef} className="prefs" onSubmit={onSubmit} noValidate>
        {form.notice ? <Notice tone={form.notice.tone}>{form.notice.text}</Notice> : null}
        {form.fieldErrors.request ? <Notice tone="danger">{form.fieldErrors.request}</Notice> : null}
        <TextArea
          label="Roles you want"
          hint="One per line. For example Data analyst."
          rows={3}
          value={values.target_roles}
          error={form.fieldErrors.target_roles}
          onChange={(e) => set("target_roles", e.target.value)}
        />
        <TextArea
          label="Countries where you can work without a visa"
          hint="One per line."
          rows={2}
          value={values.authorized_countries}
          error={form.fieldErrors.authorized_countries}
          onChange={(e) => set("authorized_countries", e.target.value)}
        />
        <Select
          label="Do you need a company to sponsor your visa?"
          value={values.needs_sponsorship}
          onChange={(e) => set("needs_sponsorship", e.target.value)}
        >
          <option value="">Not answered</option>
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </Select>
        <TextArea
          label="Places you would work"
          hint="Cities or countries, one per line."
          rows={3}
          value={values.locations}
          error={form.fieldErrors.locations}
          onChange={(e) => set("locations", e.target.value)}
        />
        <Select
          label="Would you relocate?"
          value={values.open_to_relocate}
          onChange={(e) => set("open_to_relocate", e.target.value)}
        >
          <option value="">Not answered</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </Select>
        <Select
          label="Where do you want to work from?"
          value={values.remote_preference}
          onChange={(e) => set("remote_preference", e.target.value)}
        >
          <option value="">No preference stated</option>
          <option value="remote">Remote</option>
          <option value="hybrid">Hybrid</option>
          <option value="onsite">On-site</option>
          <option value="any">Any of these</option>
        </Select>
        <fieldset className="prefs__group">
          <legend className="prefs__legend">Kinds of work you will consider</legend>
          {EMPLOYMENT_TYPES.map((type) => (
            <Checkbox
              key={type.value}
              label={type.label}
              checked={values.employment_types.includes(type.value)}
              onChange={(e) =>
                set(
                  "employment_types",
                  e.target.checked
                    ? [...values.employment_types, type.value]
                    : values.employment_types.filter((value) => value !== type.value),
                )
              }
            />
          ))}
        </fieldset>
        <div className="prefs__salary">
          <TextField
            label="Lowest yearly pay you would accept (optional)"
            inputMode="numeric"
            value={values.min_salary_amount}
            error={form.fieldErrors.min_salary_amount}
            onChange={(e) => set("min_salary_amount", e.target.value)}
          />
          <Select
            label="Currency"
            value={values.min_salary_currency}
            error={form.fieldErrors.min_salary_currency}
            onChange={(e) => set("min_salary_currency", e.target.value)}
          >
            <option value="">Choose</option>
            {CURRENCIES.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </Select>
        </div>
        <TextArea
          label="Companies, industries or words to avoid"
          hint="One per line. Jobs that match are marked as not for you."
          rows={3}
          value={values.exclusions}
          error={form.fieldErrors.exclusions}
          onChange={(e) => set("exclusions", e.target.value)}
        />
        <div className="prefs__actions">
          <Button type="submit" variant="primary" busy={form.busy} disabled={form.blocked}>
            Save preferences
          </Button>
          <span role="status" className="prefs__saved">
            {saved ? "Preferences saved." : ""}
          </span>
        </div>
      </form>
    </Section>
  );
}
