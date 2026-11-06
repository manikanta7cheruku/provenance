import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { fetchPreferences, savePreferences } from "../../lib/profile-api";
import type { Preferences } from "../../lib/profile-api";
import { useAsync } from "../../lib/useAsync";
import { useFormSubmit } from "../../lib/useFormSubmit";
import {
  ActionButton,
  Button,
  ChipPicker,
  Notice,
  Section,
  Select,
  Skeleton,
  TextField,
} from "../../ui";

const EMPLOYMENT_TYPES = [
  { value: "full_time", label: "Full time" },
  { value: "part_time", label: "Part time" },
  { value: "internship", label: "Internship" },
  { value: "contract", label: "Contract" },
  { value: "freelance", label: "Freelance" },
] as const;

const pick = (...names: string[]) =>
  names.map((name) => ({ value: name, label: name }));

const ROLE_OPTIONS = pick(
  "Software engineer",
  "Frontend developer",
  "Backend developer",
  "Full stack developer",
  "Mobile developer",
  "Data analyst",
  "Data scientist",
  "ML engineer",
  "DevOps engineer",
  "Cloud engineer",
  "QA engineer",
  "Business analyst",
  "Product manager",
  "UI/UX designer",
);
const COUNTRY_OPTIONS = pick(
  "India",
  "United States",
  "Canada",
  "United Kingdom",
  "Germany",
  "United Arab Emirates",
  "Singapore",
  "Australia",
);
const PLACE_OPTIONS = pick(
  "Bengaluru",
  "Hyderabad",
  "Pune",
  "Mumbai",
  "Delhi",
  "Chennai",
  "Kolkata",
  "Remote",
);
const AVOID_OPTIONS = pick("Gambling", "Crypto", "Tobacco", "Adult content");
const YES_NO = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
];
const WORK_FROM = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
  { value: "any", label: "Any" },
];

const CURRENCIES = [
  "INR",
  "USD",
  "CAD",
  "GBP",
  "EUR",
  "AED",
  "SGD",
  "AUD",
] as const;

interface FormValues {
  target_roles: string[];
  authorized_countries: string[];
  needs_sponsorship: string;
  locations: string[];
  open_to_relocate: string;
  remote_preference: string;
  employment_types: string[];
  min_salary_amount: string;
  min_salary_currency: string;
  exclusions: string[];
}

const triState = (value: boolean | null): string =>
  value === null ? "" : value ? "yes" : "no";
const fromTriState = (value: string): boolean | null =>
  value === "" ? null : value === "yes";

function toValues(preferences: Preferences): FormValues {
  return {
    target_roles: preferences.target_roles,
    authorized_countries: preferences.authorized_countries,
    needs_sponsorship: triState(preferences.needs_sponsorship),
    locations: preferences.locations,
    open_to_relocate: triState(preferences.open_to_relocate),
    remote_preference: preferences.remote_preference ?? "",
    employment_types: preferences.employment_types,
    min_salary_amount: preferences.min_salary_amount?.toString() ?? "",
    min_salary_currency: preferences.min_salary_currency ?? "",
    exclusions: preferences.exclusions,
  };
}

function toPreferences(values: FormValues): Preferences {
  return {
    target_roles: values.target_roles,
    authorized_countries: values.authorized_countries,
    needs_sponsorship: fromTriState(values.needs_sponsorship),
    locations: values.locations,
    open_to_relocate: fromTriState(values.open_to_relocate),
    remote_preference: (values.remote_preference ||
      null) as Preferences["remote_preference"],
    employment_types: values.employment_types,
    min_salary_amount: values.min_salary_amount
      ? Number(values.min_salary_amount)
      : null,
    min_salary_currency: values.min_salary_currency || null,
    exclusions: values.exclusions,
  };
}

export function PreferencesSection() {
  const { data, error, loading, reload } = useAsync(
    (signal) => fetchPreferences(signal),
    [],
  );
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
    setValues((previous) =>
      previous ? { ...previous, [key]: value } : previous,
    );
  };

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!values) return;
    const errors: Record<string, string> = {};
    if (
      values.min_salary_amount &&
      !/^\d{1,10}$/.test(values.min_salary_amount)
    ) {
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
        Jobs that clearly do not fit are set aside before any scoring. Skip
        anything you are unsure about.
      </p>
      <form ref={form.formRef} className="prefs" onSubmit={onSubmit} noValidate>
        {form.notice ? (
          <Notice tone={form.notice.tone}>{form.notice.text}</Notice>
        ) : null}
        {form.fieldErrors.request ? (
          <Notice tone="danger">{form.fieldErrors.request}</Notice>
        ) : null}
        <ChipPicker
          legend="Roles you want"
          options={ROLE_OPTIONS}
          values={values.target_roles}
          onChange={(next) => set("target_roles", next)}
          custom={{ placeholder: "Another role" }}
          error={form.fieldErrors.target_roles}
        />
        <ChipPicker
          legend="Where you can work without a visa"
          options={COUNTRY_OPTIONS}
          values={values.authorized_countries}
          onChange={(next) => set("authorized_countries", next)}
          custom={{ placeholder: "Another country" }}
          error={form.fieldErrors.authorized_countries}
        />
        <div className="prefs__row">
          <ChipPicker
            legend="Need visa sponsorship?"
            single
            options={YES_NO}
            values={values.needs_sponsorship ? [values.needs_sponsorship] : []}
            onChange={(next) => set("needs_sponsorship", next[0] ?? "")}
          />
          <ChipPicker
            legend="Would you relocate?"
            single
            options={YES_NO}
            values={values.open_to_relocate ? [values.open_to_relocate] : []}
            onChange={(next) => set("open_to_relocate", next[0] ?? "")}
          />
        </div>
        <ChipPicker
          legend="Places you would work"
          options={PLACE_OPTIONS}
          values={values.locations}
          onChange={(next) => set("locations", next)}
          custom={{ placeholder: "Another city or country" }}
          error={form.fieldErrors.locations}
        />
        <ChipPicker
          legend="Work from"
          single
          options={WORK_FROM}
          values={values.remote_preference ? [values.remote_preference] : []}
          onChange={(next) => set("remote_preference", next[0] ?? "")}
        />
        <ChipPicker
          legend="Kinds of work you will consider"
          options={EMPLOYMENT_TYPES}
          values={values.employment_types}
          onChange={(next) => set("employment_types", next)}
        />
        <div className="prefs__salary">
          <TextField
            label="Lowest yearly pay (optional)"
            inputMode="numeric"
            placeholder="600000"
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
        <ChipPicker
          legend="Avoid"
          hint="Companies, industries or words. Matching jobs are marked not for you."
          options={AVOID_OPTIONS}
          values={values.exclusions}
          onChange={(next) => set("exclusions", next)}
          custom={{ placeholder: "A company or word" }}
          error={form.fieldErrors.exclusions}
        />
        <div className="prefs__actions">
          <Button
            type="submit"
            variant="primary"
            busy={form.busy}
            disabled={form.blocked}
          >
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
