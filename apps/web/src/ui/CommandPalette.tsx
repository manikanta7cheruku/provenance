import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import "./data.css";
import "./palette.css";

export interface Command {
  id: string;
  label: string;
  /** What kind of thing it is, shown beside the name and searchable. */
  group: string;
  /** Extra words that find it. */
  keywords?: string;
  /** A shortcut to show, for example "Ctrl Z". */
  shortcut?: string;
  disabled?: boolean;
  run: () => void;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  commands: readonly Command[];
  label?: string;
}

/** Keep the commands that contain every word typed. Names that start with the text come first. */
export function filterCommands(commands: readonly Command[], query: string): Command[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const usable = commands.filter((c) => !c.disabled);
  if (words.length === 0) return [...usable];
  const scored: { command: Command; score: number }[] = [];
  for (const command of usable) {
    const label = command.label.toLowerCase();
    const haystack = `${label} ${command.group.toLowerCase()} ${(command.keywords ?? "").toLowerCase()}`;
    if (!words.every((w) => haystack.includes(w))) continue;
    const score = label.startsWith(words[0]!) ? 0 : label.includes(words[0]!) ? 1 : 2;
    scored.push({ command, score });
  }
  return scored.sort((a, b) => a.score - b.score).map((s) => s.command);
}

/**
 * Type to find and run anything the editor can do. A native modal dialog holds focus and returns it,
 * the input is a combobox over a listbox (arrow keys move, Enter runs, Escape closes), and the number
 * of matches is announced. Commands that cannot run right now are left out, not greyed.
 */
export function CommandPalette({ open, onClose, commands, label = "Commands" }: CommandPaletteProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const matches = useMemo(() => filterCommands(commands, query), [commands, query]);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      setQuery("");
      setActive(0);
      element.showModal();
      input.current?.focus();
    }
    if (!open && element.open) element.close();
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  function run(command: Command | undefined) {
    if (!command) return;
    onClose();
    // Let the dialog close and focus return first, so a command that moves focus wins.
    window.setTimeout(() => command.run(), 0);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (matches.length === 0 ? 0 : (i + 1) % matches.length));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (matches.length === 0 ? 0 : (i - 1 + matches.length) % matches.length));
    } else if (event.key === "Home") {
      event.preventDefault();
      setActive(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActive(Math.max(0, matches.length - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      run(matches[active]);
    }
  }

  const optionId = (index: number) => `${listId}-${index}`;
  const current = matches[active];

  return (
    <dialog
      ref={dialog}
      className="palette"
      aria-label={label}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        // A click on the backdrop (the dialog element itself) closes it.
        if (event.target === dialog.current) onClose();
      }}
    >
      <div className="palette__box">
        <label className="visually-hidden" htmlFor={`${listId}-input`}>
          Search {label.toLowerCase()}
        </label>
        <input
          ref={input}
          id={`${listId}-input`}
          className="palette__input"
          type="text"
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={current ? optionId(active) : undefined}
          autoComplete="off"
          spellCheck={false}
          placeholder="Type what you want to do"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <ul id={listId} role="listbox" aria-label={label} className="palette__list">
          {matches.map((command, index) => (
            <li
              key={command.id}
              id={optionId(index)}
              role="option"
              aria-selected={index === active}
              className="palette__item"
              onMouseMove={() => setActive(index)}
              onClick={() => run(command)}
            >
              <span className="palette__label">{command.label}</span>
              <span className="palette__meta">
                <span>{command.group}</span>
                {command.shortcut ? <kbd className="palette__key">{command.shortcut}</kbd> : null}
              </span>
            </li>
          ))}
        </ul>
        {matches.length === 0 ? <p className="palette__empty">Nothing matches that. Try fewer words.</p> : null}
        <p className="visually-hidden" role="status" aria-live="polite">
          {matches.length === 0 ? "No commands match." : `${matches.length} ${matches.length === 1 ? "command" : "commands"}.`}
        </p>
        <p className="palette__foot" aria-hidden="true">
          <span>Up and down to choose</span>
          <span>Enter to run</span>
          <span>Escape to close</span>
        </p>
      </div>
    </dialog>
  );
}
