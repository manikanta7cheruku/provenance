import { useEffect, useState } from "react";
import { saveMessage, startOutput, tick } from "../../lib/preparation-api";
import type {
  PrepAction,
  PrepClaim,
  PrepItem,
} from "../../lib/preparation-api";
import {
  ActionButton,
  Checkbox,
  ConfirmDialog,
  Notice,
  Section,
  Status,
  TextArea,
} from "../../ui";
import type { PrepProps } from "./PrepOverview";

function Claims({ claims }: { claims: PrepClaim[] }) {
  const unsupported = claims.filter((c) => !c.supported);
  if (unsupported.length === 0) return null;
  return (
    <Notice tone="warn" title="Not in your evidence">
      <p>
        These are not in your profile or the job. Fix the wording, add them to
        your profile if true, or leave them out:
      </p>
      <ul>
        {unsupported.map((claim) => (
          <li key={claim.text}>{claim.text}</li>
        ))}
      </ul>
    </Notice>
  );
}

function Item({
  item,
  jobId,
  onUpdate,
  onProblem,
}: { item: PrepItem } & Omit<PrepProps, "data">) {
  return (
    <li className="prep__item">
      <details>
        <summary>
          <span className="prep__q">{item.text}</span>
          <span className="prep__meta">
            {[item.category, item.difficulty].filter(Boolean).join(", ")}
          </span>
        </summary>
        {item.guidance ? (
          <p className="prep__guidance">{item.guidance}</p>
        ) : null}
        {item.insufficient_evidence ? (
          <p className="prep__insufficient">{item.note}</p>
        ) : (
          <p className="field__hint">
            Built from {item.evidence_count}{" "}
            {item.evidence_count === 1 ? "piece" : "pieces"} of your evidence.
          </p>
        )}
        <Claims claims={item.claims} />
      </details>
      <Checkbox
        label={`Done: ${item.text}`}
        checked={item.done}
        onChange={(event) => {
          tick(jobId, item.key, event.target.checked)
            .then(onUpdate)
            .catch((caught: unknown) =>
              onProblem(caught, "That could not be saved. Try again."),
            );
        }}
      />
    </li>
  );
}

function ListAction({
  action,
  jobId,
  onUpdate,
  onProblem,
  likely,
}: { action: PrepAction; likely: string } & Omit<PrepProps, "data">) {
  const [busy, setBusy] = useState(false);
  async function write() {
    setBusy(true);
    try {
      onUpdate(await startOutput(jobId, action.key));
    } catch (caught) {
      onProblem(caught, "That could not be started. Try again.");
    } finally {
      setBusy(false);
    }
  }
  const working = action.status === "queued" || action.status === "working";
  return (
    <section className="prep__action" aria-label={action.label}>
      <h3 className="group__title">{action.label}</h3>
      <p className="field__hint">{action.description}</p>
      <p>
        <ActionButton
          variant={action.status === "ready" ? "quiet" : "primary"}
          onClick={() => void write()}
          disabled={busy || working}
        >
          {working
            ? "Writing"
            : action.status === "ready"
              ? "Write again"
              : "Write this"}
        </ActionButton>{" "}
        {working ? (
          <Status tone="neutral" label="Writing, this takes a moment" />
        ) : null}
      </p>
      {action.status === "failed" && action.error ? (
        <Notice tone="warn">
          <p>{action.error}</p>
        </Notice>
      ) : null}
      {action.status === "ready" ? (
        <>
          <p className="field__hint">{likely}</p>
          <ul className="prep__items">
            {action.items.map((item) => (
              <Item
                key={item.key}
                item={item}
                jobId={jobId}
                onUpdate={onUpdate}
                onProblem={onProblem}
              />
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

function MessageAction({
  action,
  jobId,
  onUpdate,
  onProblem,
  label,
}: { action: PrepAction; label: string } & Omit<PrepProps, "data">) {
  const [value, setValue] = useState(action.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [confirm, setConfirm] = useState(false);
  const [copied, setCopied] = useState("");
  useEffect(() => setValue(action.body), [action.body]);
  const working = action.status === "queued" || action.status === "working";
  const changed = value.trim() !== action.body.trim();

  async function write(replace: boolean) {
    setBusy(true);
    try {
      onUpdate(await startOutput(jobId, action.key, replace));
      setConfirm(false);
    } catch (caught) {
      const code = (caught as { code?: string }).code;
      if (code === "EDITED_TEXT") setConfirm(true);
      else onProblem(caught, "That could not be started. Try again.");
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    setBusy(true);
    setError(undefined);
    try {
      onUpdate(await saveMessage(jobId, action.key, value));
    } catch (caught) {
      const fields = (caught as { fields?: Record<string, string> }).fields;
      setError(fields?.text ?? "That could not be saved.");
    } finally {
      setBusy(false);
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied("Copied. Paste it where you are sending it.");
    } catch {
      setCopied("Select the text and copy it yourself.");
    }
  }

  return (
    <section className="prep__action" aria-label={action.label}>
      <h3 className="group__title">{action.label}</h3>
      <p className="field__hint">{action.description}</p>
      <p>
        <ActionButton
          variant={action.status === "ready" ? "quiet" : "primary"}
          onClick={() => void write(false)}
          disabled={busy || working}
        >
          {working
            ? "Writing"
            : action.status === "ready"
              ? "Write again"
              : "Write this"}
        </ActionButton>{" "}
        {working ? (
          <Status tone="neutral" label="Writing, this takes a moment" />
        ) : null}
      </p>
      {action.status === "failed" && action.error ? (
        <Notice tone="warn">
          <p>{action.error}</p>
        </Notice>
      ) : null}
      {action.status === "ready" ? (
        <>
          <p className="field__hint">{label}</p>
          <TextArea
            label={`${action.label}, in your words`}
            hint={`${action.word_count} words. Change anything. Nothing is sent from here: copy it and send it yourself.`}
            value={value}
            error={error}
            onChange={(event) => setValue(event.target.value)}
          />
          <div className="prep__row">
            <ActionButton
              variant="primary"
              onClick={() => void save()}
              disabled={busy || !changed}
            >
              Check my changes
            </ActionButton>
            <ActionButton onClick={() => void copy()}>
              Copy the text
            </ActionButton>
          </div>
          <p className="visually-hidden" role="status">
            {copied}
          </p>
          {copied ? <p className="field__hint">{copied}</p> : null}
          <Claims claims={action.claims} />
          {action.evidence.length > 0 ? (
            <details className="prep__evidence">
              <summary>The evidence this was built from</summary>
              <ul>
                {action.evidence.map((e) => (
                  <li key={e.text}>
                    {e.text}{" "}
                    <span className="field__hint">
                      {e.cited ? "Used" : "Shown, not used"}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}
      <ConfirmDialog
        open={confirm}
        title="Write this again?"
        confirmLabel="Write it again"
        busy={busy}
        onCancel={() => setConfirm(false)}
        onConfirm={() => void write(true)}
      >
        <p>You edited this text. Writing it again replaces your edits.</p>
      </ConfirmDialog>
    </section>
  );
}

export function PrepPractice({ jobId, data, onUpdate, onProblem }: PrepProps) {
  const lists = data.actions.filter((a) => a.shape === "list");
  const messages = data.actions.filter((a) => a.shape === "text");
  return (
    <>
      <Section title="Practice material">
        <p className="field__hint">{data.generated_label}</p>
        {!data.can_prepare ? (
          <Notice tone="warn">
            <p>{data.blocker}</p>
          </Notice>
        ) : null}
        {lists.map((action) => (
          <ListAction
            key={action.key}
            action={action}
            jobId={jobId}
            onUpdate={onUpdate}
            onProblem={onProblem}
            likely={data.likely_label}
          />
        ))}
      </Section>
      <Section title="Messages you can send">
        <p className="field__hint">
          These are drafts for you. Provenance never sends anything for you.
        </p>
        {messages.map((action) => (
          <MessageAction
            key={action.key}
            action={action}
            jobId={jobId}
            onUpdate={onUpdate}
            onProblem={onProblem}
            label={data.generated_label}
          />
        ))}
      </Section>
    </>
  );
}
