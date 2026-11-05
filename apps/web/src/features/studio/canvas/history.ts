/**
 * Undo and redo for any value. A change is recorded before it is applied. Changes that share a key
 * and arrive close together (typing, dragging, a held arrow key) become one step, so a drag is one
 * undo, not hundreds. Each step carries a short label, so the person can see what an undo will take
 * back and go back several steps at once.
 */
export class History<T> {
  private undoStack: T[] = [];
  private undoLabels: string[] = [];
  private redoStack: T[] = [];
  private redoLabels: string[] = [];
  private last: { key: string; at: number } | null = null;

  constructor(
    private readonly limit = 100,
    private readonly window = 800,
  ) {}

  /** Record `before` as a step to return to. Skipped when it continues the previous coalesced step. */
  record(before: T, key?: string, now = Date.now(), label = "Change"): void {
    const continuing = key !== undefined && this.last !== null && this.last.key === key && now - this.last.at < this.window;
    this.last = key === undefined ? null : { key, at: now };
    if (continuing && this.undoStack.length > 0) return;
    this.undoStack.push(before);
    this.undoLabels.push(label);
    if (this.undoStack.length > this.limit) {
      this.undoStack.shift();
      this.undoLabels.shift();
    }
    this.redoStack = [];
    this.redoLabels = [];
  }

  undo(current: T): T | null {
    const previous = this.undoStack.pop();
    if (previous === undefined) return null;
    this.redoStack.push(current);
    this.redoLabels.push(this.undoLabels.pop() ?? "Change");
    this.last = null;
    return previous;
  }

  redo(current: T): T | null {
    const next = this.redoStack.pop();
    if (next === undefined) return null;
    this.undoStack.push(current);
    this.undoLabels.push(this.redoLabels.pop() ?? "Change");
    this.last = null;
    return next;
  }

  /** Go back `steps` changes at once. Returns the value to show, or null when there is nothing to undo. */
  undoMany(current: T, steps: number): T | null {
    let value: T | null = null;
    let at = current;
    for (let i = 0; i < steps; i += 1) {
      const previous = this.undo(at);
      if (previous === null) break;
      value = previous;
      at = previous;
    }
    return value;
  }

  /** The next change starts a new step, even with the same key. */
  seal(): void {
    this.last = null;
  }

  clear(): void {
    this.undoStack = [];
    this.undoLabels = [];
    this.redoStack = [];
    this.redoLabels = [];
    this.last = null;
  }

  /** What an undo would take back, most recent first. */
  get undoable(): readonly string[] {
    return [...this.undoLabels].reverse();
  }

  /** What a redo would bring back, next first. */
  get redoable(): readonly string[] {
    return [...this.redoLabels].reverse();
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }
}

/** A short name for a kind of change, from the key the editor gave it. */
export function labelForKey(key?: string): string {
  if (!key) return "Change";
  const kind = key.split("-")[0]!;
  switch (kind) {
    case "move":
    case "nudge":
      return "Moved";
    case "resize":
    case "keysize":
      return "Resized";
    case "text":
      return "Edited text";
    case "style":
      return "Changed the page style";
    default:
      return "Changed";
  }
}
