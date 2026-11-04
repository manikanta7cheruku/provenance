import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { describeBand } from "../../lib/states";
import type { Band } from "../../lib/states";
import {
  fetchPreview,
  fetchShortlist,
  hourLabel,
  ownTimeZone,
  saveShortlist,
  sendShortlistNow,
  timeZones,
  WEEKDAYS,
} from "../../lib/shortlist-api";
import type { Frequency, Shortlist, ShortlistPreview } from "../../lib/shortlist-api";
import { useAsync } from "../../lib/useAsync";
import { ActionButton, Button, Checkbox, DataTable, Notice, Section, Select, Skeleton, Status } from "../../ui";
import "./settings.css";

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);
const COUNTS = Array.from({ length: 10 }, (_, i) => i + 1);

function Form({ data, onSaved }: { data: Shortlist; onSaved: () => void }) {
  const own = useMemo(ownTimeZone, []);
  const s = data.settings;
  const [enabled, setEnabled] = useState(s.enabled);
  const [frequency, setFrequency] = useState<Frequency>(s.frequency);
  const [weekday, setWeekday] = useState(s.weekday);
  const [hour, setHour] = useState(s.hour);
  // A person who has never set it up gets their own time zone, not UTC.
  const [timezone, setTimezone] = useState(s.enabled || s.next_run_at ? s.timezone : own);
  const [maxItems, setMaxItems] = useState(s.max_items);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ tone: "info" | "warn" | "danger"; text: string } | null>(null);
  const zones = useMemo(() => timeZones(own), [own]);

  async function save() {
    setBusy(true);
    setErrors({});
    setMessage(null);
    try {
      await saveShortlist({ enabled, frequency, weekday, hour, timezone, max_items: maxItems });
      setMessage({ tone: "info", text: enabled ? "Saved. The shortlist email is on." : "Saved. The shortlist email is off." });
      onSaved();
    } catch (caught) {
      if (caught instanceof ApiError && Object.keys(caught.fields).length > 0) setErrors(caught.fields);
      else setMessage({ tone: "warn", text: caught instanceof ApiError ? caught.message : "Your settings could not be saved. Nothing was changed." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="settings__form"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      {message ? (
        <Notice tone={message.tone}>
          <p>{message.text}</p>
        </Notice>
      ) : null}
      <Checkbox
        label="Send me a shortlist email"
        hint="A few jobs on your list that are worth your time, each with its reason. Off until you turn it on."
        checked={enabled}
        disabled={!data.email_verified && !s.enabled}
        onChange={(event) => setEnabled(event.target.checked)}
      />
      <Select label="How often" value={frequency} error={errors.frequency} onChange={(event) => setFrequency(event.target.value as Frequency)}>
        <option value="weekly">Once a week</option>
        <option value="daily">Every day</option>
      </Select>
      {frequency === "weekly" ? (
        <Select label="Day" value={String(weekday)} error={errors.weekday} onChange={(event) => setWeekday(Number(event.target.value))}>
          {WEEKDAYS.map((name, index) => (
            <option key={name} value={index}>
              {name}
            </option>
          ))}
        </Select>
      ) : null}
      <Select label="Time" value={String(hour)} error={errors.hour} onChange={(event) => setHour(Number(event.target.value))}>
        {HOURS.map((h) => (
          <option key={h} value={h}>
            {hourLabel(h)}
          </option>
        ))}
      </Select>
      <Select label="Your time zone" hint="The time above is on your own clock, including when clocks change." value={timezone} error={errors.timezone} onChange={(event) => setTimezone(event.target.value)}>
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone}
          </option>
        ))}
      </Select>
      <Select label="How many jobs at most" value={String(maxItems)} error={errors.max_items} onChange={(event) => setMaxItems(Number(event.target.value))}>
        {COUNTS.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </Select>
      <p>
        <Button type="submit" variant="primary" busy={busy}>
          Save shortlist settings
        </Button>
      </p>
    </form>
  );
}

function Preview() {
  const [preview, setPreview] = useState<ShortlistPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function load() {
    setBusy(true);
    setFailed(false);
    try {
      setPreview(await fetchPreview());
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings__preview">
      <p>
        <ActionButton disabled={busy} onClick={() => void load()}>
          Preview what would be sent now
        </ActionButton>
      </p>
      {failed ? (
        <Notice tone="warn">
          <p>The preview could not be loaded. Nothing was changed.</p>
        </Notice>
      ) : null}
      {preview ? (
        <>
          <p role="status">{preview.note}</p>
          {preview.items.length > 0 ? (
            <ol className="settings__items">
              {preview.items.map((item) => {
                const band = item.band ? describeBand(item.band as Band) : null;
                return (
                  <li key={item.id}>
                    <Link to={`/opportunities/${item.id}`}>{item.title ?? "Untitled posting"}</Link>
                    <span className="row-sub">{[item.company, item.location].filter(Boolean).join(" | ")}</span>
                    {band ? <Status tone={band.tone} label={band.label} /> : null}
                    <span className="row-sub">{item.reason}</span>
                  </li>
                );
              })}
            </ol>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export function ShortlistSection() {
  const shortlist = useAsync((signal) => fetchShortlist(signal), []);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const data = shortlist.data;

  async function sendNow() {
    setSending(true);
    setProblem(null);
    setSent(null);
    try {
      const result = await sendShortlistNow();
      setSent(result.message);
      window.setTimeout(shortlist.reload, 4000);
    } catch (caught) {
      setProblem(caught instanceof ApiError ? caught.message : "It could not be queued. Nothing was changed.");
    } finally {
      setSending(false);
    }
  }

  return (
    <Section title="Shortlist email">
      {shortlist.error ? (
        <Notice tone="danger" title="Your shortlist settings could not be loaded">
          <p>{shortlist.error.message} Nothing was changed.</p>
          <p>
            <ActionButton onClick={shortlist.reload}>Try again</ActionButton>
          </p>
        </Notice>
      ) : !data ? (
        <Skeleton label="Loading shortlist settings" lines={4} />
      ) : (
        <>
          <p className="settings__lead">
            A short email with the jobs most worth your time: a Strong or Good fit against your own evidence, nothing in the way, and not sent before. It
            never applies for you, and it is never sent when there is nothing worth a look.
          </p>
          {data.blocker ? (
            <Notice tone="warn" title="Verify your email address first">
              <p>{data.blocker}</p>
            </Notice>
          ) : null}
          <p role="status" className="settings__next">
            {data.settings.enabled && data.settings.next_run_at
              ? `On. Next email: ${formatDateTime(data.settings.next_run_at)} (${data.settings.schedule_text}).`
              : "Off. Nothing is sent."}
          </p>
          <p className="job__note">{data.delivery_note}</p>
          <Form data={data} onSaved={shortlist.reload} />

          <Preview />
          <p>
            <ActionButton disabled={sending || !data.email_verified} onClick={() => void sendNow()}>
              Send me one now
            </ActionButton>
          </p>
          {sent ? (
            <Notice tone="info">
              <p>{sent}</p>
            </Notice>
          ) : null}
          {problem ? (
            <Notice tone="warn">
              <p>{problem}</p>
            </Notice>
          ) : null}

          {data.runs.length > 0 ? (
            <DataTable caption={`Recent shortlist emails, ${data.runs.length} shown`}>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">What happened</th>
                  <th scope="col" className="num">
                    Jobs
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.runs.map((run, index) => (
                  <tr key={index}>
                    <td>{formatDateTime(run.at)}</td>
                    <td>
                      {run.outcome_text}
                      {run.manual ? <span className="row-sub">You asked for this one</span> : null}
                    </td>
                    <td className="num">{run.item_count}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          ) : null}
        </>
      )}
    </Section>
  );
}
