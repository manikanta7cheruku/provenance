import { useState } from "react";
import { answerMock, finishMock, startMock } from "../../lib/preparation-api";
import type { MockTurn } from "../../lib/preparation-api";
import { ActionButton, Notice, Section, TextArea } from "../../ui";
import type { PrepProps } from "./PrepOverview";

function Feedback({ turn }: { turn: MockTurn }) {
  return (
    <div className="prep__feedback">
      <p>
        <strong>
          {turn.total} out of {turn.maximum}
        </strong>{" "}
        for this answer ({turn.words} words).
      </p>
      <ul>
        {turn.rubric.map((r) => (
          <li key={r.name}>
            <strong>
              {r.name}, {r.score} of 3:
            </strong>{" "}
            {r.note}
          </li>
        ))}
      </ul>
      <p>{turn.follow_up}</p>
    </div>
  );
}

/** One question at a time. Each answer is scored from the answer itself, and anything in it that is
 *  not in your profile is named. */
export function PrepMock({ jobId, data, onUpdate, onProblem }: PrepProps) {
  const mock = data.mock;
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>();

  async function begin() {
    setBusy(true);
    try {
      onUpdate(await startMock(jobId));
      setAnswer("");
    } catch (caught) {
      onProblem(caught, "The practice interview could not be started.");
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    if (!mock) return;
    setBusy(true);
    setError(undefined);
    try {
      onUpdate(await answerMock(jobId, mock.id, answer));
      setAnswer("");
    } catch (caught) {
      const fields = (caught as { fields?: Record<string, string> }).fields;
      if (fields?.answer) setError(fields.answer);
      else onProblem(caught, "Your answer could not be saved.");
    } finally {
      setBusy(false);
    }
  }
  async function end() {
    if (!mock) return;
    setBusy(true);
    try {
      onUpdate(await finishMock(jobId, mock.id));
    } catch (caught) {
      onProblem(caught, "That could not be done.");
    } finally {
      setBusy(false);
    }
  }

  const last =
    mock && mock.turns.length > 0 ? mock.turns[mock.turns.length - 1] : null;
  return (
    <Section title="Mock interview">
      <p className="field__hint">
        Practise out loud or in writing, one question at a time. The questions
        come from what this job asks for, most important first. A thing your
        profile does not show is asked as a gap: how would you approach it.
        Feedback is about the answer, not about you.
      </p>
      {!data.can_prepare ? (
        <Notice tone="warn">
          <p>{data.blocker}</p>
        </Notice>
      ) : null}
      {!mock || mock.state === "finished" ? (
        <>
          <p>
            <ActionButton
              variant="primary"
              onClick={() => void begin()}
              disabled={busy || !data.can_prepare}
            >
              {mock
                ? "Start a new practice interview"
                : "Start a practice interview"}
            </ActionButton>
          </p>
          {mock && mock.turns.length > 0 ? (
            <>
              <p role="status">
                Finished. You answered {mock.turns.length} of{" "}
                {mock.question_count} questions,{" "}
                {mock.turns.reduce((n, t) => n + t.total, 0)} of{" "}
                {mock.turns.reduce((n, t) => n + t.maximum, 0)} points.
              </p>
              <ol className="prep__turns">
                {mock.turns.map((turn, index) => (
                  <li key={turn.question}>
                    <h3 className="group__title">Question {index + 1}</h3>
                    <p>{turn.question}</p>
                    <blockquote>{turn.answer}</blockquote>
                    <Feedback turn={turn} />
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </>
      ) : (
        <>
          {last ? (
            <div className="prep__last">
              <h3 className="group__title">Feedback on your last answer</h3>
              <Feedback turn={last} />
            </div>
          ) : null}
          <h3 className="group__title">
            Question {mock.current_index + 1} of {mock.question_count}
          </h3>
          <p className="prep__question">{mock.current_question}</p>
          <TextArea
            label="Your answer"
            hint="As you would say it: the situation, what you did, and what changed."
            value={answer}
            error={error}
            onChange={(event) => setAnswer(event.target.value)}
          />
          <div className="prep__row">
            <ActionButton
              variant="primary"
              onClick={() => void submit()}
              disabled={busy || answer.trim().length === 0}
            >
              Get feedback
            </ActionButton>
            <ActionButton onClick={() => void end()} disabled={busy}>
              Finish now
            </ActionButton>
          </div>
        </>
      )}
    </Section>
  );
}
