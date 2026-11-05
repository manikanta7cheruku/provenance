import { PRIORITY_ORDER, tick, VERDICT_WORDS } from "../../lib/preparation-api";
import type { PrepConcept, Preparation } from "../../lib/preparation-api";
import { Checkbox, Notice, Section } from "../../ui";

export interface PrepProps {
  jobId: string;
  data: Preparation;
  onUpdate: (next: Preparation) => void;
  onProblem: (caught: unknown, fallback: string) => void;
}

const GROUP_TITLES: Record<string, string> = {
  critical: "Critical gaps",
  high: "High-priority preparation areas",
  useful: "Useful to prepare",
  optional: "Already supported or optional",
};

function Concept({
  concept,
  jobId,
  onUpdate,
  onProblem,
}: { concept: PrepConcept } & Omit<PrepProps, "data">) {
  return (
    <li className="prep__concept">
      <Checkbox
        label={concept.text}
        hint={`${VERDICT_WORDS[concept.verdict] ?? concept.verdict}. ${concept.why} Difficulty: ${concept.difficulty}.`}
        checked={concept.done}
        onChange={(event) => {
          tick(jobId, concept.key, event.target.checked)
            .then(onUpdate)
            .catch((caught: unknown) =>
              onProblem(caught, "That could not be saved. Try again."),
            );
        }}
      />
    </li>
  );
}

/** What to prepare, grouped by how much it matters, and how much of the job is already covered. */
export function PrepOverview({ jobId, data, onUpdate, onProblem }: PrepProps) {
  const cov = data.coverage;
  const groups = PRIORITY_ORDER.map((p) => ({
    priority: p,
    items: data.concepts.filter((c) => c.priority === p),
  })).filter((g) => g.items.length > 0);
  return (
    <>
      <Section title="How much of the job your profile covers">
        {cov.required === 0 ? (
          <p>This job lists no separate requirements to prepare for.</p>
        ) : (
          <p>
            Of {cov.required} required {cov.required === 1 ? "thing" : "things"}
            : {cov.met} shown by your profile, {cov.partial} partly shown,{" "}
            {cov.not_shown} not shown
            {cov.unchecked > 0 ? `, ${cov.unchecked} not checked yet` : ""}.
          </p>
        )}
        <p className="field__hint">
          Not shown does not mean you cannot do it. It means your profile does
          not say so yet. Add what you have done, or use it to decide what to
          learn.
        </p>
      </Section>
      <Section title="What to prepare">
        <p className="field__hint">
          {data.likely_label} Tick things as you finish them.
        </p>
        {groups.length === 0 ? (
          <Notice tone="info">
            <p>
              Nothing to prepare yet. Run the evidence check on the job first.
            </p>
          </Notice>
        ) : (
          groups.map((group) => (
            <section
              key={group.priority}
              className={`prep__group prep__group--${group.priority}`}
              aria-label={GROUP_TITLES[group.priority]}
            >
              <h3 className="group__title">
                {GROUP_TITLES[group.priority]} ({group.items.length})
              </h3>
              <ul>
                {group.items.map((concept) => (
                  <Concept
                    key={concept.key}
                    concept={concept}
                    jobId={jobId}
                    onUpdate={onUpdate}
                    onProblem={onProblem}
                  />
                ))}
              </ul>
            </section>
          ))
        )}
        <p className="field__hint">
          How this is decided: a required thing your profile does not show is a
          critical gap, one it shows only in part is high priority, a preferred
          thing not shown is useful, and the rest is optional (
          {data.rules_version}).
        </p>
      </Section>
    </>
  );
}
