import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import {
  chooseRepos,
  disconnectGitHub,
  fetchGitHub,
  isSyncing,
  startGitHub,
  syncGitHub,
} from "../../lib/github-api";
import type { GitHubRepo } from "../../lib/github-api";
import { useAsync } from "../../lib/useAsync";
import {
  ActionButton,
  Checkbox,
  ConfirmDialog,
  Notice,
  Section,
  Skeleton,
  Status,
} from "../../ui";

const POLL_MS = 2000;

interface GitHubSectionProps {
  /** Called when entries may have changed (evidence was added or removed). */
  onChanged: () => void;
}

function RepoRow({
  repo,
  checked,
  disabled,
  onToggle,
}: {
  repo: GitHubRepo;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const facts = [
    repo.language,
    repo.stars > 0
      ? `${repo.stars} ${repo.stars === 1 ? "star" : "stars"}`
      : "",
    repo.fork ? "a fork" : "",
    repo.archived ? "archived" : "",
  ].filter(Boolean);
  return (
    <li className="github__repo">
      <Checkbox
        label={repo.full_name}
        hint={[
          repo.description,
          facts.join(", "),
          repo.suggested ? "Suggested: it looks worth showing." : "",
        ]
          .filter(Boolean)
          .join(" ")}
        checked={checked}
        disabled={disabled}
        onChange={onToggle}
      />
    </li>
  );
}

/**
 * Connect GitHub so public repositories can become evidence. The screen says plainly what is asked
 * of GitHub (nothing beyond public information), what is read, and how to leave.
 */
export function GitHubSection({ onChanged }: GitHubSectionProps) {
  const { data, error, loading, reload } = useAsync(
    (signal) => fetchGitHub(signal),
    [],
  );
  const [picked, setPicked] = useState<Set<number> | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [keepEntries, setKeepEntries] = useState(false);

  // While a read is running, look again every couple of seconds. When it finishes, the entries moved.
  const syncing = data ? isSyncing(data.sync_state) : false;
  useEffect(() => {
    if (!syncing) return;
    const timer = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(timer);
  }, [syncing, reload]);
  useEffect(() => {
    if (data && !syncing) onChanged();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncing, data?.last_synced_at]);

  const chosen = useMemo(
    () =>
      picked ??
      new Set((data?.repos ?? []).filter((r) => r.selected).map((r) => r.id)),
    [picked, data],
  );

  function fail(caught: unknown, fallback: string) {
    setMessage(null);
    setProblem(caught instanceof ApiError ? caught.message : fallback);
  }

  async function connect() {
    setBusy(true);
    setProblem(null);
    try {
      const { authorize_url } = await startGitHub();
      window.location.assign(authorize_url);
    } catch (caught) {
      fail(caught, "GitHub could not be started. Nothing was changed.");
      setBusy(false);
    }
  }

  async function readAgain() {
    setBusy(true);
    setProblem(null);
    try {
      await syncGitHub();
      setMessage("Reading your repositories again.");
      reload();
    } catch (caught) {
      fail(
        caught,
        "Your repositories could not be read just now. Nothing was changed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveChoice() {
    setBusy(true);
    setProblem(null);
    try {
      await chooseRepos([...chosen]);
      setPicked(null);
      setMessage(
        chosen.size === 0
          ? "No repositories are used as evidence."
          : `Using ${chosen.size} ${chosen.size === 1 ? "repository" : "repositories"} as evidence. They appear under Your entries in a moment.`,
      );
      reload();
    } catch (caught) {
      fail(caught, "Your choice could not be saved. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  async function leave() {
    setBusy(true);
    setProblem(null);
    try {
      const result = await disconnectGitHub(keepEntries);
      setLeaving(false);
      setPicked(null);
      setMessage(
        `GitHub is disconnected and its token is deleted. ${result.revoked ? "GitHub confirmed the access was revoked." : "GitHub did not confirm the revoke, so also remove Provenance at github.com/settings/applications."} ${keepEntries ? "The entries stay as yours." : result.entries_removed > 0 ? `${result.entries_removed} ${result.entries_removed === 1 ? "entry was" : "entries were"} removed.` : ""}`.trim(),
      );
      reload();
      onChanged();
    } catch (caught) {
      setLeaving(false);
      fail(caught, "GitHub could not be disconnected. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <Section title="GitHub">
        <Notice tone="danger" title="GitHub could not be loaded">
          <p>{error.message}</p>
          <p>
            <ActionButton onClick={reload}>Try again</ActionButton>
          </p>
        </Notice>
      </Section>
    );
  }
  if (loading || !data) {
    return (
      <Section title="GitHub">
        <Skeleton label="Loading GitHub" lines={3} />
      </Section>
    );
  }
  const changed = picked !== null;
  const over = chosen.size > data.max_selected;
  return (
    <Section title="GitHub">
      <p>
        Connect GitHub and pick the projects that show what you can do. Each one
        becomes an entry you can read, edit and delete, marked as coming from
        GitHub, and a job is then checked against it like anything else in your
        profile.
      </p>
      <p className="field__hint">{data.scope_sentence}</p>
      {message ? (
        <Notice tone="info">
          <p>{message}</p>
        </Notice>
      ) : null}
      {problem ? (
        <Notice tone="danger">
          <p>{problem}</p>
        </Notice>
      ) : null}

      {!data.available ? (
        <Notice tone="warn" title="GitHub is not set up on this server">
          <p>
            The person running Provenance has to create a GitHub OAuth app and
            add its client id and secret to the server settings first. Until
            then nothing can be connected, and nothing is lost.
          </p>
        </Notice>
      ) : !data.connected ? (
        <div className="github__connect">
          <ActionButton
            variant="primary"
            onClick={() => void connect()}
            disabled={busy}
          >
            {busy ? "Opening GitHub" : "Connect GitHub"}
          </ActionButton>
          <span className="field__hint">
            You will sign in on github.com and be sent back here. Provenance
            never sees your password.
          </span>
        </div>
      ) : (
        <>
          <p className="github__who">
            <Status
              tone={
                data.sync_state === "failed"
                  ? "danger"
                  : isSyncing(data.sync_state)
                    ? "neutral"
                    : "ok"
              }
              label={`Connected as ${data.login ?? ""}`}
            />
            {data.profile_url ? (
              <>
                {" "}
                <a
                  href={data.profile_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  Open on GitHub
                </a>
              </>
            ) : null}
          </p>
          <p className="field__hint" role="status">
            {isSyncing(data.sync_state)
              ? "Reading your repositories."
              : data.sync_state === "failed"
                ? ""
                : data.last_synced_at
                  ? `Your repositories were last read on ${formatDateTime(data.last_synced_at)}.`
                  : "Your repositories have not been read yet."}
          </p>
          {data.sync_state === "failed" && data.sync_error ? (
            <Notice tone="warn" title="The last read did not work">
              <p>{data.sync_error}</p>
            </Notice>
          ) : null}

          {data.repos.length === 0 && !isSyncing(data.sync_state) ? (
            <p className="job__note">
              No public repositories were found. Only public ones are ever read.
            </p>
          ) : (
            <fieldset className="github__repos">
              <legend className="group__title">
                Repositories to use as evidence
              </legend>
              <p className="field__hint">
                Choose up to {data.max_selected}. A few well chosen projects
                read better than many. Forks and archived repositories are not
                suggested.
              </p>
              <ul>
                {data.repos.map((repo) => (
                  <RepoRow
                    key={repo.id}
                    repo={repo}
                    checked={chosen.has(repo.id)}
                    disabled={busy}
                    onToggle={() =>
                      setPicked((current) => {
                        const next = new Set(current ?? chosen);
                        if (next.has(repo.id)) next.delete(repo.id);
                        else next.add(repo.id);
                        return next;
                      })
                    }
                  />
                ))}
              </ul>
              {over ? (
                <p className="field__error" role="alert">
                  Choose at most {data.max_selected} repositories.
                </p>
              ) : null}
            </fieldset>
          )}

          <div className="github__actions">
            <ActionButton
              variant="primary"
              onClick={() => void saveChoice()}
              disabled={busy || !changed || over}
            >
              Use these as evidence
            </ActionButton>
            <ActionButton
              onClick={() => void readAgain()}
              disabled={busy || isSyncing(data.sync_state)}
            >
              Read my repositories again
            </ActionButton>
            <ActionButton onClick={() => setLeaving(true)} disabled={busy}>
              Disconnect GitHub
            </ActionButton>
          </div>
        </>
      )}

      <details className="github__others">
        <summary>Evidence from places that cannot be connected</summary>
        <p className="field__hint">
          Some platforms do not allow other products to read your profile. Here
          is what to do instead.
        </p>
        <ul>
          {data.platforms.map((platform) => (
            <li key={platform.name}>
              <strong>{platform.name}.</strong> {platform.why} {platform.what}
            </li>
          ))}
        </ul>
      </details>

      <ConfirmDialog
        open={leaving}
        title="Disconnect GitHub?"
        confirmLabel="Disconnect"
        danger
        busy={busy}
        onCancel={() => setLeaving(false)}
        onConfirm={() => void leave()}
      >
        <p>
          The stored access token is deleted and Provenance asks GitHub to
          revoke it. The entries made from your repositories are removed from
          your profile.
        </p>
        <Checkbox
          label="Keep those entries as mine"
          hint="They stay in your profile as your own entries, without the GitHub label."
          checked={keepEntries}
          onChange={(event) => setKeepEntries(event.target.checked)}
        />
      </ConfirmDialog>
    </Section>
  );
}
