import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../lib/api";
import { decideMatch, fetchMatches } from "../../lib/jobs-api";
import type { JobMatches, PostingMatch, Sighting } from "../../lib/jobs-api";
import { ActionButton, Notice, Section, Skeleton, Status } from "../../ui";

const when = (iso: string) => new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });

const STATE: Record<PostingMatch["state"], { label: string; tone: "ok" | "neutral" | "warn" }> = {
  auto: { label: "Linked automatically", tone: "ok" },
  confirmed: { label: "You said: same job", tone: "ok" },
  suggested: { label: "Possible match", tone: "warn" },
  undone: { label: "You said: not the same job", tone: "neutral" },
};

function SightingLine({ s }: { s: Sighting }) {
  return (
    <li>
      <strong>{s.kind === "yours" ? "Your copy" : s.source_name}</strong>. {s.how}
      {s.board_id ? ` (${s.board_id})` : ""}. First seen {when(s.first_seen_at)}
      {s.kind === "public" ? `, last seen ${when(s.last_seen_at)}, seen ${s.seen_count} ${s.seen_count === 1 ? "time" : "times"}` : ""}.
      {s.closed ? " No longer listed." : ""}{" "}
      {s.url ? (
        <a href={s.url} target="_blank" rel="noopener noreferrer">
          Open this posting<span className="visually-hidden"> at {s.source_name}</span>
        </a>
      ) : null}
    </li>
  );
}

function Match({ m, busy, onDecide }: { m: PostingMatch; busy: boolean; onDecide: (verb: "confirm" | "undo" | "reset") => void }) {
  const info = STATE[m.state];
  const decided = m.state === "confirmed" || m.state === "undone";
  return (
    <li className="sightings__item">
      <p className="sightings__line">
        <strong>
          {m.title}
          {m.company_name ? `, ${m.company_name}` : ""}
        </strong>{" "}
        <Status tone={info.tone} label={info.label} />
      </p>
      <p className="sightings__meta">
        {[m.location, m.source_name].filter(Boolean).join(" | ")}. {m.reason}
      </p>
      <div className="sightings__actions" role="group" aria-label={`Is ${m.title} the same job?`}>
        {m.state !== "confirmed" && m.state !== "auto" ? (
          <ActionButton disabled={busy} aria-label={`Same job, ${m.title} at ${m.source_name}`} onClick={() => onDecide("confirm")}>
            Same job
          </ActionButton>
        ) : null}
        {m.state !== "undone" ? (
          <ActionButton disabled={busy} aria-label={`Not the same job, ${m.title} at ${m.source_name}`} onClick={() => onDecide("undo")}>
            Not the same job
          </ActionButton>
        ) : null}
        {decided ? (
          <ActionButton disabled={busy} aria-label={`Decide again, ${m.title} at ${m.source_name}`} onClick={() => onDecide("reset")}>
            Decide again
          </ActionButton>
        ) : null}
      </div>
    </li>
  );
}

/** Where else a pasted posting appears, why we think so, and a way to say we are wrong. */
export function Sightings({ jobId }: { jobId: string }) {
  const [data, setData] = useState<JobMatches | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetchMatches(jobId, controller.signal)
      .then(setData)
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) setFailed(true);
      });
    return () => controller.abort();
  }, [jobId]);

  const decide = useCallback(
    async (m: PostingMatch, verb: "confirm" | "undo" | "reset") => {
      setBusy(true);
      setProblem(null);
      try {
        setData(await decideMatch(jobId, m.group_id, verb));
        setMessage(verb === "undo" ? "Marked as not the same job." : verb === "confirm" ? "Marked as the same job." : "Back to the automatic answer.");
      } catch (caught) {
        setProblem(caught instanceof ApiError ? caught.message : "That could not be saved. Nothing was changed.");
      } finally {
        setBusy(false);
      }
    },
    [jobId],
  );

  if (failed) return null; // this section is extra: the page works without it
  if (!data) return <Skeleton label="Looking for other copies of this job" lines={2} />;
  return (
    <Section title="Where else this job appears">
      <p className="studio__lead">
        Jobs fetched from permitted sources are compared with the posting you pasted. Your posting stays private: nothing here is shared, and your choices are yours alone.
      </p>
      <ul className="sightings__list">
        {data.sightings.map((s, i) => (
          <SightingLine key={`${s.kind}-${i}`} s={s} />
        ))}
      </ul>
      {data.note ? <p className="sightings__meta">{data.note}</p> : null}
      {data.matches.length > 0 ? (
        <ul className="sightings__matches">
          {data.matches.map((m) => (
            <Match key={m.group_id} m={m} busy={busy} onDecide={(verb) => void decide(m, verb)} />
          ))}
        </ul>
      ) : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}
      <p role="status" className="visually-hidden">
        {message}
      </p>
    </Section>
  );
}
