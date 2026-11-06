import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import {
  chooseRepos,
  disconnectGitHub,
  fetchGitHub,
  isSyncing,
  linkGitHub,
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
  TextField,
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
  const [link, setLink] = useState("");
  const [changing, setChanging] = useState(false);

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

  async function addLink(event: React.FormEvent) {
    event.preventDefault();
    if (!link.trim()) return;
    setBusy(true);
    setProblem(null);
    setMessage(null);
    try {
      await linkGitHub(link.trim());
      setLink("");
      reload();
    } catch (caught) {
      fail(caught, "That link could not be used. Nothing was changed.");
    } finally {
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
      setChanging(false);
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
        `${data?.verified === false ? "The GitHub link is removed." : `GitHub is disconnected and its token is deleted. ${result.revoked ? "GitHub confirmed the access was revoked." : "GitHub did not confirm the revoke, so also remove Provenance at github.com/settings/applications."}`} ${keepEntries ? "The entries stay as yours." : result.entries_removed > 0 ? `${result.entries_removed} ${result.entries_removed === 1 ? "entry was" : "entries were"} removed.` : ""}`.trim(),
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
  const chosenRepos = data.repos.filter((repo) => repo.selected);
  const showPicker = changing || chosenRepos.length === 0 || picked !== null;
  const over = chosen.size > data.max_selected;
  return (
    <Section title="GitHub">
      <p>
        Paste your GitHub link and pick the projects that show what you can do.
        Each becomes an entry you can edit or delete.
      </p>
      <details className="github__others">
        <summary>What is read</summary>
        <p className="field__hint">{data.scope_sentence}</p>
      </details>
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

      {!data.connected ? (
        <div className="github__connect">
          <form className="github__paste" onSubmit={(e) => void addLink(e)}>
            <TextField
              label="GitHub link"
              placeholder="github.com/yourname"
              value={link}
              onChange={(event) => setLink(event.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
            <ActionButton type="submit" variant="primary" disabled={busy || !link.trim()}>
              {busy ? "Looking" : "Add"}
            </ActionButton>
          </form>
          {data.available ? (
            <p className="field__hint">
              Or{" "}
              <button type="button" className="github__verify" onClick={() => void connect()} disabled={busy}>
                sign in with GitHub
              </button>{" "}
              to prove the account is yours.
            </p>
          ) : null}
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
              label={`${data.verified ? "Connected as" : "Using"} ${data.login ?? ""}`}
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
          {!data.verified ? (
            <p className="field__hint">
              Added from a link, so it is not proven to be your account.
              {data.available ? (
                <>
                  {" "}
                  <button type="button" className="github__verify" onClick={() => void connect()} disabled={busy}>
                    Verify with GitHub
                  </button>
                </>
              ) : null}
            </p>
          ) : null}
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

          {chosenRepos.length > 0 && !showPicker ? (
            <div className="github__chosen">
              <p className="group__title">
                In your profile
              </p>
              <ul className="pills">
                {chosenRepos.map((repo) => (
                  <li key={repo.id} className="pill">
                    {repo.name}
                  </li>
                ))}
              </ul>
            </div>
          ) : data.repos.length === 0 && !isSyncing(data.sync_state) ? (
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
            {showPicker && data.repos.length > 0 ? (
              <ActionButton
                variant="primary"
                onClick={() => void saveChoice()}
                disabled={busy || !changed || over}
              >
                Use these as evidence
              </ActionButton>
            ) : null}
            {!showPicker ? (
              <ActionButton onClick={() => setChanging(true)} disabled={busy}>
                Change repositories
              </ActionButton>
            ) : null}
            <ActionButton
              onClick={() => void readAgain()}
              disabled={busy || isSyncing(data.sync_state)}
            >
              Read my repositories again
            </ActionButton>
            <ActionButton onClick={() => setLeaving(true)} disabled={busy}>
              {data.verified ? "Disconnect GitHub" : "Remove link"}
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
        title={data.verified ? "Disconnect GitHub?" : "Remove the GitHub link?"}
        confirmLabel={data.verified ? "Disconnect" : "Remove"}
        danger
        busy={busy}
        onCancel={() => setLeaving(false)}
        onConfirm={() => void leave()}
      >
        <p>
          {data.verified
            ? "The stored access token is deleted and Provenance asks GitHub to revoke it. "
            : ""}
          The entries made from your repositories are removed from your profile.
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
