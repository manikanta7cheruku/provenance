import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { fetchJobs, fetchSources, planSearch } from "../../lib/search-api";
import type { CompanyDecision, FetchedJob, IntentFields, SearchPlan, SourceDecision, SourceInfo } from "../../lib/search-api";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { ActionButton, Notice, PageHeader, Section, Select, Skeleton, Status, TextArea, TextField } from "../../ui";
import type { Tone } from "../../ui";
import "./search.css";

const OUTCOME: Record<SourceDecision["outcome"], { label: string; tone: Tone }> = {
  search: { label: "Searched", tone: "ok" },
  import_required: { label: "Import needed", tone: "neutral" },
  unavailable: { label: "Unavailable", tone: "warn" },
};

const COMPLIANCE: Record<SourceInfo["compliance_status"], string> = {
  verified: "Terms read and confirmed",
  unverified: "Terms not confirmed yet",
  restricted: "Terms restrict this use",
  prohibited: "Automated access not allowed",
};

const HEALTH: Record<SourceInfo["health_status"], { label: string; tone: Tone }> = {
  unknown: { label: "Not asked yet", tone: "neutral" },
  healthy: { label: "Healthy", tone: "ok" },
  degraded: { label: "Slow to answer", tone: "warn" },
  down: { label: "Paused after failures", tone: "danger" },
};

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : null);

const split = (text: string) =>
  text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

function intentLines(intent: Record<string, unknown>): string[] {
  const list = (key: string) => (Array.isArray(intent[key]) ? (intent[key] as string[]) : []);
  const lines: string[] = [];
  if (list("roles").length) lines.push(`Roles: ${list("roles").join(", ")}`);
  if (list("skills").length) lines.push(`Skills: ${list("skills").join(", ")}`);
  if (intent.min_years !== null || intent.max_years !== null) {
    lines.push(`Experience: ${intent.min_years ?? 0} to ${intent.max_years ?? "any"} years`);
  }
  if (list("locations").length) lines.push(`Places: ${list("locations").join(", ")}`);
  if (intent.work_mode && intent.work_mode !== "any") lines.push(`Work mode: ${String(intent.work_mode)}`);
  if (list("employment_types").length) lines.push(`Kind of job: ${list("employment_types").join(", ")}`);
  const pay = intent.compensation as { min: number; currency: string; period: string } | null;
  if (pay) lines.push(`Pay at least: ${pay.min.toLocaleString()} ${pay.currency} a ${pay.period}`);
  if (list("companies").length) lines.push(`Companies: ${list("companies").join(", ")}`);
  const sources = list("sources");
  lines.push(sources.length === 1 && sources[0] === "all_permitted" ? "Sources: every permitted source" : `Sources: ${sources.join(", ")}`);
  if (list("exclusions").length) lines.push(`Not wanted: ${list("exclusions").join(", ")}`);
  return lines;
}

function SourceList({ title, items }: { title: string; items: SourceDecision[] }) {
  if (items.length === 0) return null;
  return (
    <div className="find__group">
      <h4 className="find__subtitle">{title}</h4>
      <ul className="find__list">
        {items.map((d) => (
          <li key={d.key} className="find__item">
            <p className="find__line">
              <strong>{d.display_name}</strong> <Status tone={OUTCOME[d.outcome].tone} label={OUTCOME[d.outcome].label} />
              {d.named_by_person ? <span className="find__meta"> You asked for this one.</span> : null}
            </p>
            <p>{d.message}</p>
            {d.notes.map((n) => (
              <p key={n} className="find__meta">
                {n}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Companies({ items, onPick }: { items: CompanyDecision[]; onPick: (query: string, name: string) => void }) {
  if (items.length === 0) return null;
  return (
    <Section title="Companies">
      <ul className="find__list">
        {items.map((c) => (
          <li key={c.query} className="find__item">
            <p className="find__line">
              <strong>{c.company ? c.company.name : c.query}</strong>{" "}
              <Status tone={c.status === "resolved" ? "ok" : "warn"} label={c.status === "resolved" ? "Found" : c.status === "ambiguous" ? "Which one?" : "Not in our list"} />
            </p>
            <p>{c.message}</p>
            {c.status === "ambiguous" ? (
              <div className="find__choices" role="group" aria-label={`Choose the company for ${c.query}`}>
                {c.candidates.map((cand) => (
                  <ActionButton key={cand.key} onClick={() => onPick(c.query, cand.name)}>
                    {cand.name}
                  </ActionButton>
                ))}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Jobs({ plan }: { plan: SearchPlan }) {
  const [jobs, setJobs] = useState<FetchedJob[] | null>(null);
  const [failed, setFailed] = useState(false);
  const list = (key: string) => (Array.isArray(plan.intent[key]) ? (plan.intent[key] as string[]) : []);
  const searched = plan.sources.filter((d) => d.outcome === "search").map((d) => d.key);
  const companies = plan.companies.flatMap((c) => (c.company ? [c.company.key] : []));
  const signature = JSON.stringify([list("roles"), list("locations"), companies, searched, plan.intent.work_mode]);

  useEffect(() => {
    const controller = new AbortController();
    setJobs(null);
    setFailed(false);
    fetchJobs(
      { roles: list("roles"), locations: list("locations"), companies, sources: searched, work_mode: String(plan.intent.work_mode ?? "any") },
      controller.signal,
    )
      .then(setJobs)
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) setFailed(true);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  if (failed) {
    return (
      <Notice tone="danger">
        <p>The jobs could not be loaded. Nothing was changed.</p>
      </Notice>
    );
  }
  if (jobs === null) return <Skeleton label="Loading jobs" lines={3} />;
  if (jobs.length === 0) return <p>No jobs have been fetched for this search yet. The sources are asked politely, a few times a day at most.</p>;
  return (
    <ul className="find__list">
      {jobs.map((job) => (
        <li key={job.id} className="find__item">
          <p className="find__line">
            <strong>{job.title}</strong>
            {job.company_name ? <span>, {job.company_name}</span> : null}
          </p>
          <p className="find__meta">
            {[job.location, job.workplace, job.employment_type?.replace("_", " "), job.department].filter(Boolean).join(" | ")}
          </p>
          {job.excerpt ? <p>{job.excerpt}</p> : null}
          <p className="find__meta">
            Source: {job.source_name}
            {job.attribution_text ? `. ${job.attribution_text}` : ""}. Found {when(job.first_seen_at)}.{" "}
            <a href={job.url} target="_blank" rel="noopener noreferrer">
              Open the original posting<span className="visually-hidden"> for {job.title}</span>
            </a>
          </p>
        </li>
      ))}
    </ul>
  );
}

function Registry() {
  const sources = useAsync((signal) => fetchSources(signal), []);
  if (sources.loading) return <Skeleton label="Loading the sources" lines={3} />;
  if (sources.error || !sources.data) {
    return (
      <Notice tone="danger">
        <p>The source list could not be loaded.</p>
      </Notice>
    );
  }
  return (
    <ul className="find__list">
      {sources.data.map((s) => (
        <li key={s.key} className="find__item">
          <p className="find__line">
            <strong>{s.display_name}</strong> <Status tone={OUTCOME[s.outcome].tone} label={OUTCOME[s.outcome].label} />
          </p>
          <p className="find__meta">
            {COMPLIANCE[s.compliance_status]}
            {s.terms_checked_at ? `, terms read on ${s.terms_checked_at}` : ""}.{" "}
            {s.terms_url ? (
              <a href={s.terms_url} target="_blank" rel="noopener noreferrer">
                Read the terms<span className="visually-hidden"> of {s.display_name}</span>
              </a>
            ) : null}
          </p>
          {s.reason ? <p className="find__meta">{s.reason}</p> : null}
          {s.outcome === "search" || s.health_status !== "unknown" ? (
            <p className="find__meta">
              <Status tone={HEALTH[s.health_status].tone} label={HEALTH[s.health_status].label} />
              {s.last_success_at ? ` Last answered ${when(s.last_success_at)}.` : ""} {s.jobs_open} open {s.jobs_open === 1 ? "job" : "jobs"} kept.
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function FindJobsPage() {
  useDocumentTitle("Find jobs");
  const [query, setQuery] = useState("");
  const [fields, setFields] = useState({ roles: "", skills: "", locations: "", companies: "", work_mode: "any" });
  const [plan, setPlan] = useState<SearchPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<{ message: string; field?: string } | null>(null);

  async function run(input: { query: string } | { intent: IntentFields }) {
    setBusy(true);
    setProblem(null);
    try {
      setPlan(await planSearch(input));
    } catch (caught) {
      if (caught instanceof ApiError) {
        setProblem({ message: caught.fields?.query ?? caught.message, field: caught.fields?.query ? "query" : undefined });
      } else {
        setProblem({ message: "The search could not be planned. Nothing was searched." });
      }
    } finally {
      setBusy(false);
    }
  }

  const fromFields = (): IntentFields => ({
    roles: split(fields.roles),
    skills: split(fields.skills),
    locations: split(fields.locations),
    companies: split(fields.companies),
    work_mode: fields.work_mode,
  });

  const searching = plan?.sources.filter((d) => d.outcome === "search") ?? [];
  const importing = plan?.sources.filter((d) => d.outcome === "import_required") ?? [];
  const unavailable = plan?.sources.filter((d) => d.outcome === "unavailable") ?? [];

  return (
    <>
      <PageHeader
        title="Find jobs"
        description="Say what you are looking for. You see where it can be searched, where you need to import jobs yourself, and why. Nothing is claimed as searched unless it was."
      />
      <Section title="What are you looking for?">
        <form
          className="find__form"
          onSubmit={(event) => {
            event.preventDefault();
            void run({ query });
          }}
        >
          <TextArea
            label="Describe the search"
            hint="For example: backend engineer at Google in India, 0 to 2 years, remote."
            rows={3}
            value={query}
            error={problem?.field === "query" ? problem.message : undefined}
            onChange={(event) => setQuery(event.target.value)}
          />
          <ActionButton variant="primary" type="submit" disabled={busy || query.trim() === ""}>
            {busy ? "Planning" : "Plan this search"}
          </ActionButton>
        </form>
        <details className="find__fields">
          <summary>Or fill in the details yourself</summary>
          <div className="find__grid">
            <TextField label="Roles" hint="Separate with commas." value={fields.roles} onChange={(e) => setFields({ ...fields, roles: e.target.value })} />
            <TextField label="Skills" hint="Separate with commas." value={fields.skills} onChange={(e) => setFields({ ...fields, skills: e.target.value })} />
            <TextField label="Places" hint="A city or a country." value={fields.locations} onChange={(e) => setFields({ ...fields, locations: e.target.value })} />
            <TextField label="Companies" hint="Separate with commas." value={fields.companies} onChange={(e) => setFields({ ...fields, companies: e.target.value })} />
            <Select label="Work mode" value={fields.work_mode} onChange={(e) => setFields({ ...fields, work_mode: e.target.value })}>
              <option value="any">Any</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On site</option>
            </Select>
          </div>
          <ActionButton onClick={() => void run({ intent: fromFields() })} disabled={busy}>
            Plan with these details
          </ActionButton>
        </details>
        {problem && problem.field !== "query" ? (
          <Notice tone="danger">
            <p>{problem.message}</p>
          </Notice>
        ) : null}
      </Section>

      {plan ? (
        <>
          <Section title="What we understood">
            <p role="status" className="find__headline">
              {plan.headline}
            </p>
            <p className="find__meta">Read by {plan.interpreted_by}.</p>
            <ul className="find__facts">
              {intentLines(plan.intent).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {plan.notes.map((n) => (
              <p key={n} className="find__meta">
                {n}
              </p>
            ))}
            <p className="find__meta">
              Work authorization comes from {plan.authorization.origin}
              {plan.authorization.countries.length ? `: ${plan.authorization.countries.join(", ")}` : ", where nothing is set yet"}. It is never read from what you type.
            </p>
          </Section>
          <Section title="Where this can go">
            <SourceList title="Searched" items={searching} />
            <SourceList title="You import these" items={importing} />
            <SourceList title="Unavailable" items={unavailable} />
            {searching.length === 0 ? (
              <p>
                You can import jobs yourself: paste a posting in <Link to="/opportunities">Opportunities</Link>, and it is read and checked against your profile like any other.
              </p>
            ) : null}
          </Section>
          {plan.can_search_now ? (
            <Section title="Jobs from the sources searched">
              <Jobs plan={plan} />
            </Section>
          ) : null}
          <Companies items={plan.companies} onPick={(q, name) => void run({ intent: { ...fromFields(), companies: [name] } })} />
        </>
      ) : null}

      <Section title="Sources and how they are used">
        <p className="studio__lead">
          Every source has a record of where its terms were read. A source is used only while that record says it may be. Jobs you import are always shown as imported by you.
        </p>
        <Registry />
      </Section>
    </>
  );
}
