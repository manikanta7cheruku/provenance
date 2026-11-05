import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { fetchPreparation, isWriting } from "../../lib/preparation-api";
import type { Preparation } from "../../lib/preparation-api";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import {
  ActionButton,
  Notice,
  PageHeader,
  SegmentedControl,
  Skeleton,
} from "../../ui";
import { PrepMock } from "./PrepMock";
import { PrepOverview } from "./PrepOverview";
import { PrepPlan } from "./PrepPlan";
import { PrepPractice } from "./PrepPractice";
import "./preparation.css";

type Tab = "overview" | "practice" | "mock" | "plan";

const REFRESH_MS = 2000;

/** What to prepare for one job and why, practice material, a mock interview and a plan. */
export function PreparationPage() {
  const { jobId = "" } = useParams();
  useDocumentTitle("Prepare");
  const loaded = useAsync((signal) => fetchPreparation(jobId, signal), [jobId]);
  const [local, setLocal] = useState<Preparation | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [problem, setProblem] = useState<string | null>(null);
  const current = local ?? loaded.data;

  // Anything that changes the preparation returns the whole of it, so the screen just takes it.
  const update = useCallback((next: Preparation) => {
    setLocal(next);
    setProblem(null);
  }, []);
  const fail = useCallback((caught: unknown, fallback: string) => {
    setProblem(caught instanceof ApiError ? caught.message : fallback);
  }, []);

  // While something is being written, look again every couple of seconds.
  const writing = current ? isWriting(current) : false;
  useEffect(() => {
    if (!writing) return;
    const timer = window.setInterval(() => {
      void fetchPreparation(jobId)
        .then(setLocal)
        .catch(() => undefined);
    }, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [writing, jobId]);

  if (loaded.error && !current) {
    return (
      <>
        <PageHeader title="Prepare" />
        <Notice tone="danger" title="This could not be loaded">
          <p>{loaded.error.message}</p>
          <p>
            <ActionButton onClick={loaded.reload}>Try again</ActionButton>{" "}
            <Link to="/opportunities">Back to your jobs</Link>
          </p>
        </Notice>
      </>
    );
  }
  if (!current) {
    return (
      <>
        <PageHeader title="Prepare" />
        <Skeleton label="Loading your preparation" lines={4} />
      </>
    );
  }

  const heading = [current.title, current.company].filter(Boolean).join(" at ");
  return (
    <>
      <PageHeader
        title="Prepare"
        description={`${heading || "This job"}. What to prepare, in what order, and why. Everything here is built from the job and your own evidence.`}
      />
      <p className="prep__back">
        <Link to={`/opportunities/${jobId}`}>Back to the job</Link>
      </p>
      {current.blocker ? (
        <Notice tone="warn" title="Check this job first">
          <p>{current.blocker}</p>
          <p>
            <Link to={`/opportunities/${jobId}`}>
              Go to the job and run the evidence check
            </Link>
          </p>
        </Notice>
      ) : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}
      <div className="prep__tabs">
        <SegmentedControl<Tab>
          legend="Show"
          value={tab}
          onChange={setTab}
          options={[
            { value: "overview", label: "What to prepare" },
            { value: "practice", label: "Practice material" },
            { value: "mock", label: "Mock interview" },
            { value: "plan", label: "Plan and company" },
          ]}
        />
        <p className="prep__progress" role="status">
          Progress: {current.progress.done} of {current.progress.total} done (
          {current.progress.percent} percent)
        </p>
      </div>
      {tab === "overview" ? (
        <PrepOverview
          jobId={jobId}
          data={current}
          onUpdate={update}
          onProblem={fail}
        />
      ) : null}
      {tab === "practice" ? (
        <PrepPractice
          jobId={jobId}
          data={current}
          onUpdate={update}
          onProblem={fail}
        />
      ) : null}
      {tab === "mock" ? (
        <PrepMock
          jobId={jobId}
          data={current}
          onUpdate={update}
          onProblem={fail}
        />
      ) : null}
      {tab === "plan" ? (
        <PrepPlan
          jobId={jobId}
          data={current}
          onUpdate={update}
          onProblem={fail}
        />
      ) : null}
    </>
  );
}
