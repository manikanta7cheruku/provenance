import { ActionButton } from "../../../ui";

interface SelectionBarProps {
  canEdit: boolean;
  onEdit: () => void;
  onDuplicate: () => void;
  onRemove: () => void;
  /** Move by this many millimetres. */
  onNudge: (dx: number, dy: number) => void;
}

const STEP = 1;

/**
 * Controls for a finger, shown under the pages when something is selected. A phone has no
 * keyboard, so editing text, duplicating, deleting and fine moves need buttons.
 */
export function SelectionBar({ canEdit, onEdit, onDuplicate, onRemove, onNudge }: SelectionBarProps) {
  return (
    <div className="cv-selbar" role="toolbar" aria-label="Selected element">
      {canEdit ? <ActionButton onClick={onEdit}>Edit text</ActionButton> : null}
      <ActionButton onClick={onDuplicate}>Duplicate</ActionButton>
      <ActionButton onClick={onRemove}>Delete</ActionButton>
      <span className="cv-selbar__pad" role="group" aria-label="Move a little">
        <ActionButton onClick={() => onNudge(-STEP, 0)} aria-label="Move left">Left</ActionButton>
        <ActionButton onClick={() => onNudge(0, -STEP)} aria-label="Move up">Up</ActionButton>
        <ActionButton onClick={() => onNudge(0, STEP)} aria-label="Move down">Down</ActionButton>
        <ActionButton onClick={() => onNudge(STEP, 0)} aria-label="Move right">Right</ActionButton>
      </span>
    </div>
  );
}
