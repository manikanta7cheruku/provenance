/**
 * Undo and redo for any value. A change is recorded before it is applied. Changes that share a key
 * and arrive close together (typing, dragging, a held arrow key) become one step, so a drag is one
 * undo, not hundreds.
 */
export class History<T> {
  private undoStack: T[] = [];
  private redoStack: T[] = [];
  private last: { key: string; at: number } | null = null;

  constructor(
    private readonly limit = 100,
    private readonly window = 800,
  ) {}

  /** Record `before` as a step to return to. Skipped when it continues the previous coalesced step. */
  record(before: T, key?: string, now = Date.now()): void {
    const continuing = key !== undefined && this.last !== null && this.last.key === key && now - this.last.at < this.window;
    this.last = key === undefined ? null : { key, at: now };
    if (continuing && this.undoStack.length > 0) return;
    this.undoStack.push(before);
    if (this.undoStack.length > this.limit) this.undoStack.shift();
    this.redoStack = [];
  }

  undo(current: T): T | null {
    const previous = this.undoStack.pop();
    if (previous === undefined) return null;
    this.redoStack.push(current);
    this.last = null;
    return previous;
  }

  redo(current: T): T | null {
    const next = this.redoStack.pop();
    if (next === undefined) return null;
    this.undoStack.push(current);
    this.last = null;
    return next;
  }

  /** The next change starts a new step, even with the same key. */
  seal(): void {
    this.last = null;
  }

  clear(): void {
    this.undoStack = [];
    this.redoStack = [];
    this.last = null;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }
}
