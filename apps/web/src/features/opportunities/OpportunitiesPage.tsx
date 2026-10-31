import { useEffect } from "react";
import { Link } from "react-router-dom";
import { fetchJobs } from "../../lib/jobs-api";
import type { JobSummary } from "../../lib/jobs-api";
import { formatDateTime } from "../../lib/format";
import { describeEligibility, describeJobState, isJobBusy } from "../../lib/states";
import { useAsync } from "../../lib/useAsync";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { ActionButton, DataTable, EmptyState, Notice, PageHeader, Section, Skeleton, Status } from "../../ui";
import { PasteJobForm } from "./PasteJobForm";
import { acquisitionLabel, workLine } from "./labels";
import "./opportunities.css";

const REFRESH_MS = 2000;

function JobStatus({ job }: { job: JobSummary }) {
  if (job.ui_state !== "ready") {
    const info = describeJobState(job.ui_state);
    return <Status tone={info.tone} label={info.label} />;
  }
  const info = describeEligibility(job.eligibility ?? "uncertain");
  return <Status tone={info.tone} label={info.label} />;
}

export function OpportunitiesPage() {
  useDocumentTitle("Opportunities");
  const jobs = useAsync((signal) => fetchJobs(signal), []);
  const busy = jobs.data?.some((job) => isJobBusy(job.ui_state)) ?? false;

  // While a posting is being read, keep asking. Stops by itself when everything settled.
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(jobs.reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [busy, jobs.reload]);

  return (
    <>
      <PageHeader
        title="Opportunities"
        description="Jobs you have pasted, with whether you can take them and what each one asks for."
      />
      <PasteJobForm onPasted={jobs.reload} />

      <Section title="Your jobs">
        {jobs.error ? (
          <Notice tone="danger" title="Your jobs could not be loaded">
            <p>{jobs.error.message} Nothing was changed.</p>
            <p>
              <ActionButton onClick={jobs.reload}>Try again</ActionButton>
            </p>
          </Notice>
        ) : !jobs.data ? (
          <Skeleton label="Loading your jobs" lines={4} />
        ) : jobs.data.length === 0 ? (
          <EmptyState
            title="No jobs yet"
            why="Each job you paste is read for what it asks for and checked against your answers, so you can skip the ones that are not for you."
            next="Paste a job description above."
          />
        ) : (
          <DataTable caption={`Your jobs, ${jobs.data.length} saved`}>
            <thead>
              <tr>
                <th scope="col">Job</th>
                <th scope="col">Can you take it</th>
                <th scope="col">Work</th>
                <th scope="col">Source</th>
                <th scope="col" className="num">
                  Asks for
                </th>
                <th scope="col">Added</th>
              </tr>
            </thead>
            <tbody>
              {jobs.data.map((job) => (
                <tr key={job.id}>
                  <th scope="row">
                    <Link to={`/opportunities/${job.id}`} className="jobs__link">
                      {job.title ?? "Untitled posting"}
                    </Link>
                    <span className="row-sub">{job.company ?? "Company not stated"}</span>
                  </th>
                  <td>
                    <JobStatus job={job} />
                  </td>
                  <td>{workLine(job)}</td>
                  <td>
                    {job.source_name}
                    <span className="row-sub">{acquisitionLabel(job.acquisition_method)}</span>
                  </td>
                  <td className="num">{job.ui_state === "ready" ? job.requirement_count : ""}</td>
                  <td>{formatDateTime(job.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </Section>
    </>
  );
}
