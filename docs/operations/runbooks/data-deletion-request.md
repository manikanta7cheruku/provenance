# Runbook: data deletion request

## Detection
- A person used Settings, Your data, Delete my account (almost always), or
- a person writes to say they want their data deleted or a copy of it.

## Diagnosis (when they ask by message)
1. Confirm who they are the way you would for a password reset: the request must come from the account email, or they sign in and do it themselves. Never delete or export an account on an unverified message.
2. Ask which they want: a copy, deletion, or both. Tell them they can do both themselves in Settings, Your data, and that deletion cannot be undone.

## Mitigation (they cannot use the product)
- A copy: sign-in is needed for the download. If they cannot sign in, reset their password from Users, then ask them to download.
- Deletion: ask them to sign in (reset the password if needed) and use the button. The button checks their password and the words typed, signs them out everywhere and queues the deletion.

## Recovery (what happens, and how to check)
1. The request marks the account inactive and queues a `delete_account` task. The worker removes every stored file first, then the user row, which removes every table that holds their data. It takes a few minutes.
2. Check the task finished: Admin, Queue (no dead letter for `delete_account`) and `select status, requested_at, completed_at, files_removed from account_deletions order by requested_at desc limit 5;`. `done` is complete. `failed` with `STORAGE_FAILED` means a file could not be removed and nothing else was deleted: fix the storage problem, then requeue the task from Queue.
3. The record names no one. It cannot be used to find the person.
4. Backups: their data stays in backups until those backups expire (30 days). Say so if they ask. If a backup is restored during that time, repeat the deletion for anyone deleted since that backup (compare `account_deletions` after the restore date).

## Prevention
- The deletion test walks every foreign key to users, every table with an owner column and the storage, so a table added later that would block or miss deletion fails the build.
- Keep the privacy policy and the backup retention (`BACKUP_KEEP_DAYS`) in step: the policy says 30 days.
