import { ActionButton, Dialog } from "../../ui";

export const SHORTCUTS: [string, string][] = [
  ["J or Down arrow", "Next job"],
  ["K or Up arrow", "Previous job"],
  ["Enter", "Open the job"],
  ["S", "Save, or unsave"],
  ["D", "Dismiss, or undo a dismiss"],
  ["P", "Approve for preparation"],
  ["A", "Mark applied (asks first)"],
  ["X", "Select or unselect the job for a bulk action"],
  ["/", "Search"],
  ["?", "Show these shortcuts"],
  ["Escape", "Clear the selection, or close this window"],
];

/** Every shortcut, written out. Each one also has a visible button, so none is required. */
export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog
      open={open}
      title="Keyboard shortcuts"
      onClose={onClose}
      actions={
        <ActionButton variant="primary" onClick={onClose} autoFocus>
          Close
        </ActionButton>
      }
    >
      <p>Shortcuts work when you are not typing in a field. They act on the job that is marked as the current one.</p>
      <table className="data-table">
        <caption className="visually-hidden">Keyboard shortcuts</caption>
        <thead>
          <tr>
            <th scope="col">Key</th>
            <th scope="col">What it does</th>
          </tr>
        </thead>
        <tbody>
          {SHORTCUTS.map(([key, what]) => (
            <tr key={key}>
              <th scope="row">
                <kbd>{key}</kbd>
              </th>
              <td>{what}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Dialog>
  );
}
