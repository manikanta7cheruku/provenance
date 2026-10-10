import { useSession } from "../../lib/session";
import { Button, Notice } from "../../ui";

/** Shown when the session could not be checked at all (the API is unreachable). */
export function SessionUnavailable({ message }: { message: string }) {
  const { refresh } = useSession();
  return (
    <Notice tone="danger" title="We could not check your session.">
      <p>
        Nothing was changed and your data is safe. The page does not retry on its own. {message}
      </p>
      <Button onClick={() => void refresh()}>Try again</Button>
    </Notice>
  );
}
