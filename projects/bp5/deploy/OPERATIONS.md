# Operate Prata on the existing VPS

The only managed destination is `/home/openclaw/prata`, operated as `openclaw` (uid996/gid987). Docker runs `prata-app` as that nonroot identity with a read-only filesystem, 1536 MiB memory cap, 1.8 CPU cap, dropped capabilities, bounded logs and a private persistent `/data` volume. Models are mounted read-only. The app binds only `127.0.0.1:8788`; the existing Caddy service serves `/apps/bp5/` over HTTPS. Other dashboard routes remain unchanged.

## Release

Run the product checks and independent review first. Use `engine.vps_product_delivery.deploy(profile, selected_job, workspace, checkpoint)` for the selected BP5 version3-or-later scope. It packages an exact byte manifest, verifies staged files on the server, builds the image, checks a private candidate on8789, takes a consistent encrypted recovery backup, and activates8788. It verifies the public HTTPS health/readiness before committing deployment metadata. Do not replace this with an unchecked tar or expose the legacy app entry point.

The rollout journal lives in `operations/`. A cancelled/failed operation preserves the active database and attempts to restore the prior managed container. It never blindly restores old SQLite over newer user writes. Network loss cannot guarantee remote cancellation: inspect the operation journal before retrying; the next managed activation performs recovery. Destructive schema migrations require a separate tested migration/recovery design.

## Backup and recovery

Install `backup_runner.py` at the managed root and the two supplied systemd units in the operator's user unit directory. Enable `prata-backup.timer`; it runs daily at02:17UTC and catches up after downtime. The runner selects the last committed release from `deployment.json`.

SQLite's backup API makes a consistent snapshot, verifies integrity, then age encrypts it atomically. Plain temporary snapshots are removed. Routine encrypted files and inactive managed recovery copies expire under the daily schedule within seven days. Active container mounts and the live database are never retention targets. `backup-status.json` records successful completion; inspect systemd failures as well as the timestamp. Expiry runs even if creating the next backup fails.

The VPS has only the public age recipient. Keep the private recovery identity securely outside the VPS; losing it makes encrypted backups unrecoverable. Copy encrypted backups to another machine when available. Same-VPS copies alone do not protect against losing the VPS.

`pythonw -m engine.prata_backup_sync --profile <absolute-profile-path>` mirrors the newest verified encrypted file into `<runtime_root>/prata-backups`. It uses strict known-host SSH, checks length and SHA-256, writes atomically, and expires only unchanged files tracked in its local manifest. No decryption key is sent to the VPS. `sync-status.json` records the result without key or account data. The installed Windows task `prata-backup-sync` runs once daily at 04:47 local time, after the UTC backup in both Stockholm winter and summer time, catches up when the user session is available and uses hidden Python/SSH. It does not poll the job queue. Laptop-off time delays this second copy; this is not continuous off-site replication. The recovery identity is private in that folder with access restricted to the owner and SYSTEM.

To restore, decrypt a selected backup into a new isolated directory using the private identity, run SQLite integrity checks and verify expected account/history records. Stop the known application before an authorized production restore, preserve its current database, and test the restored service before changing the live volume. Never overwrite an active database merely because a code rollout failed.

On 1 November 2026, a real encrypted backup containing a disposable account was restored into an isolated service: integrity, password login, saved history and a reading response passed through HTTP. The plaintext test directory was removed. This verified account/history recovery; speech dependencies were checked separately on the hosted service.

## Accounts and checks

Create an invitation privately with `docker exec prata-app python server/manage.py create-invite --output /data/<new-private-file>`. Retrieve the file over SSH and remove that specific token file after delivery. Never put invitation, session, recovery, password or backup-key material in Git, logs or public URLs. Invitation codes expire after seven days. Users choose their own passwords and save their recovery codes.

Run `docker exec prata-app python server/smoke_http.py` for a real HTTP check. It creates only its own disposable accounts and removes them; it must preserve other users. It checks54 missions, isolation/recovery, speech round trips and cancellation. Review the sanitized result and perform a browser journey separately. Six public human-read audio clips and responsive viewport testing do not establish learner-accent accuracy or physical iPhone/Android compatibility.

Monitor `/health`, `/ready`, container restart/health state, free disk and the last backup. Read-only health checks require no account. One speech operation at a time is deliberate for this VPS; concurrent users receive a retryable busy response. No cloud API fallback, customer-key harvesting or surprise paid compute is configured.
