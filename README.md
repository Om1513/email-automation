# Gmail Outreach Automation

Production-grade CLI for sending personalized outreach emails from
**yuktasethi@gmail.com** using the Gmail API. It creates personalized Gmail
**drafts** with your resume attached, records local scheduling metadata, and a
separate command sends each draft once its scheduled time arrives.

---

## 1. What this project does

Given a CSV of contacts (`name,email,company`) and a resume PDF, the tool:

1. Personalizes a fixed email template per recipient (first name, company,
   LinkedIn URL).
2. Creates a real Gmail **draft** for each recipient with the resume attached.
3. Stores scheduling metadata locally (default: **tomorrow at 8:00 AM** local
   time).
4. Sends the drafts later, when you run `send-due` (driven by cron / Task
   Scheduler).
5. Tracks campaign state in JSON, prevents duplicate emails, and is safe to
   rerun.

## 2. Gmail API limitations (important)

The Gmail API supports OAuth authentication, draft creation, draft sending,
attachments, and message sending — **but it does NOT expose Gmail's native
"Schedule Send" feature as an API endpoint.**

This tool does **not** fake scheduling. Instead:

- **Step 1 — `create-drafts`:** create Gmail drafts immediately.
- **Step 2:** store the intended send time locally in the campaign state file.
- **Step 3 — `send-due`:** a separate command sends only the drafts whose
  scheduled time has arrived. You run it on a schedule (cron / Task Scheduler).

## 3. Why drafts + a scheduler

This design is reliable and production-friendly:

- Drafts are visible and editable in Gmail before anything is sent — a built-in
  review step.
- Scheduling is decoupled from creation, so a machine reboot or a missed run
  never loses state — `send-due` simply sends whatever is now due.
- State + backups make reruns idempotent and recoverable.

---

## 4. Google Cloud setup

1. Go to <https://console.cloud.google.com/> and create a project (e.g.
   `gmail-outreach`).
2. **APIs & Services → Library →** search **Gmail API → Enable**.
3. **APIs & Services → OAuth consent screen:**
   - User type: **External**.
   - Fill in app name, your support email, and developer email.
   - **Scopes:** you can leave this empty here; the app requests
     `gmail.compose` at runtime.
   - **Test users:** add **yuktasethi@gmail.com** (required while the app is in
     "Testing" mode).
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID:**
   - Application type: **Desktop app**.
   - Create, then **Download JSON**.

## 5. OAuth setup (local)

1. Rename the downloaded file to `credentials.json` and place it in the project
   **root** (next to `requirements.txt`).
2. The first time you run `create-drafts` (or any authenticated command), a
   browser window opens for consent. Approve it **with the
   yuktasethi@gmail.com account**.
3. A `token.json` is written to the root and reused on later runs. If the
   authenticated account is not `yuktasethi@gmail.com`, the tool aborts with a
   clear error — delete `token.json` and retry with the correct account.

> `credentials.json` and `token.json` are git-ignored and never logged.

## 6. Installing dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.9+.

## 7. CSV format

A header row plus one row per contact. Required columns: `name`, `email`,
`company` (header casing is ignored).

```csv
name,email,company
Jane Smith,jane@example.com,Goldman Sachs
Rahul Mehta,rahul@example.com,Jane Street
```

Validation rejects missing columns, missing fields, invalid email formats, and
**duplicate emails within the file**. See `contacts_sample.csv`.

## 8. Resume attachment setup

Place the resume PDF anywhere readable (the suggested location is `files/`) and
pass it with `--resume`. It must exist, be readable, and end in `.pdf`.

```bash
--resume "./files/Yukta_Sethi_Resume.pdf"
```

---

## 9. Dry run (preview only — no drafts, no sends)

```bash
python -m src.main dry-run \
  --contacts contacts.csv \
  --resume "./files/Yukta_Sethi_Resume.pdf" \
  --campaign-id "quant-risk-june-2026" \
  --linkedin-url "https://linkedin.com/in/yourprofile"
```

Logs the personalized subject/body and resolved send time for each recipient,
and records them with status `previewed`.

## 10. Create drafts

```bash
python -m src.main create-drafts \
  --contacts contacts.csv \
  --resume "./files/Yukta_Sethi_Resume.pdf" \
  --campaign-id "quant-risk-june-2026" \
  --linkedin-url "https://linkedin.com/in/yourprofile"
```

Creates Gmail drafts, stores `gmail_draft_id` / `gmail_message_id`, and sets the
scheduled send time (default tomorrow 08:00 local; override with
`--schedule-at "2026-06-15 08:00"`). Use `--limit 10` to test on a subset and
`--force` to recreate drafts despite duplicate protection.

## 11. Viewing drafts in Gmail

Open Gmail → **Drafts**. Each draft is addressed to one recipient with the
resume attached. Review/edit freely before they are sent — editing the draft in
Gmail does not change the draft id, so `send-due` still sends the latest
version.

## 12. Sending drafts

```bash
python -m src.main send-due --campaign-id "quant-risk-june-2026"
```

Sends only drafts whose `scheduled_send_time` is now or in the past, records the
sent message id, marks them `sent`, and saves after each send. A failed send is
marked `failed` (with the error captured) and processing continues. Tune the
gap between sends with `--send-delay-seconds` (default 5).

## 13. Scheduling with cron (macOS / Linux)

Run `send-due` every 10 minutes; it only acts when something is actually due.

```cron
*/10 * * * * cd /absolute/path/to/gmail_outreach && /absolute/path/to/.venv/bin/python -m src.main send-due --campaign-id "quant-risk-june-2026" >> logs/cron.log 2>&1
```

To fire once at 8:00 AM the next day instead:

```cron
0 8 * * * cd /absolute/path/to/gmail_outreach && /absolute/path/to/.venv/bin/python -m src.main send-due --campaign-id "quant-risk-june-2026" >> logs/cron.log 2>&1
```

Edit your crontab with `crontab -e`.

## 14. Scheduling with Windows Task Scheduler

1. Open **Task Scheduler → Create Task**.
2. **Triggers:** New → Daily → 8:00 AM (or "Repeat task every 10 minutes").
3. **Actions:** New → Start a program:
   - Program/script:
     `C:\path\to\gmail_outreach\.venv\Scripts\python.exe`
   - Add arguments:
     `-m src.main send-due --campaign-id "quant-risk-june-2026"`
   - Start in: `C:\path\to\gmail_outreach`
4. Save. Provide credentials if prompted to run whether or not you are logged
   in.

## 15. Duplicate prevention

Within a campaign, if a recipient's email already has status `draft_created` or
`sent`, `create-drafts` **skips** it. Pass `--force` to override and recreate.
This makes reruns safe — you will not double-draft or double-send.

## 16. State files

State lives at `state/{campaign_id}.json`, e.g.
`state/quant-risk-june-2026.json`. It tracks `campaign_id`, `created_at`,
`updated_at`, and a per-recipient record:

```
name, email, company, first_name, subject,
gmail_draft_id, gmail_message_id, scheduled_send_time,
status, created_at, updated_at, error_message
```

Valid statuses: `previewed`, `draft_created`, `sent`, `failed`, `skipped`.

## 17. Campaign backups

Before any state-mutating command, a timestamped copy is written to
`state/backups/{campaign_id}_{timestamp}.json`. Folders are created
automatically. To recover, copy a backup back over
`state/{campaign_id}.json`.

## 18. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `credentials.json not found` | Download the Desktop OAuth client JSON and save it as `credentials.json` in the root. |
| `Authenticated Gmail account does not match` | You logged in with the wrong account. Delete `token.json` and re-auth as `yuktasethi@gmail.com`. |
| Browser doesn't open / headless server | Run `create-drafts` once on a machine with a browser to mint `token.json`, then copy it to the server. |
| `access_denied` during consent | Add `yuktasethi@gmail.com` as a **Test user** on the OAuth consent screen. |
| `invalid_grant` on later runs | Token revoked/expired. Delete `token.json` and re-authenticate. |
| `Resume must be a .pdf file` | Pass a real `.pdf` path to `--resume`. |
| `Duplicate email addresses detected` | Remove duplicate rows from the CSV. |
| Rate limit / 429 errors | Increase `--send-delay-seconds`. |
| Nothing sends on `send-due` | The scheduled time hasn't arrived, or no drafts are in `draft_created` status. Check the state file and `logs/outreach.log`. |

## 19. Safe reruns

- Re-running `create-drafts` skips already-drafted/sent recipients (unless
  `--force`).
- Re-running `send-due` only sends drafts that are due and still in
  `draft_created` — already-sent recipients are untouched.
- State is saved after every recipient, and every mutating run is backed up
  first, so an interrupted run can simply be re-run.

---

## Example outputs

### Dry run

```
2026-06-14 18:30:01 | INFO     | outreach.main | DRY RUN — campaign quant-risk-june-2026
2026-06-14 18:30:01 | INFO     | outreach.main | Scheduled send time (local): 2026-06-15T08:00:00-04:00
2026-06-14 18:30:01 | INFO     | outreach.main | Recipients to preview: 2
2026-06-14 18:30:01 | INFO     | outreach.main | [1/2] To: Jane Smith <jane@example.com>
2026-06-14 18:30:01 | INFO     | outreach.main | Subject: Quant, Risk, and a real love of the numbers!
...
2026-06-14 18:30:01 | INFO     | outreach.main | Dry run complete. No drafts created, no emails sent.
```

### Create drafts

```
2026-06-14 18:32:10 | INFO     | outreach.auth | Authenticated as yuktasethi@gmail.com
2026-06-14 18:32:11 | INFO     | outreach.main | [1/2] DRAFT created for jane@example.com (draft r-883...)
2026-06-14 18:32:12 | INFO     | outreach.main | [2/2] DRAFT created for rahul@example.com (draft r-884...)
2026-06-14 18:32:12 | INFO     | outreach.main | Done. created=2 skipped=0 failed=0
```

### Send due

```
2026-06-15 08:00:03 | INFO     | outreach.main | SEND DUE — campaign quant-risk-june-2026 (now=2026-06-15T08:00:03-04:00)
2026-06-15 08:00:03 | INFO     | outreach.main | Drafts due to send: 2
2026-06-15 08:00:04 | INFO     | outreach.main | [1/2] SENT to jane@example.com (message 1900...)
2026-06-15 08:00:09 | INFO     | outreach.main | [2/2] SENT to rahul@example.com (message 1901...)
2026-06-15 08:00:09 | INFO     | outreach.main | Send complete. sent=2 failed=0
```

---

## Final checklist

1. Place `credentials.json` in the project root.
2. Put the resume PDF in `files/`.
3. Fill in `contacts.csv` (start from `contacts_sample.csv`).
4. Run `dry-run` and review the previews.
5. Run `create-drafts`.
6. Verify the drafts in Gmail.
7. Schedule `send-due` for tomorrow at 8:00 AM (cron / Task Scheduler).
8. Monitor `logs/outreach.log`.
