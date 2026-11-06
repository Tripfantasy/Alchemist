# Local backend (only when site.json says `"backend": "local"`)

Read this file only on a site that chose a local or mounted directory in
`/setup`. On a Globus site it does not apply, and nothing in it changes a Globus
rule, script or permission. Where it applies, it is binding alongside
`CLAUDE.md`, and it adds to the workflow; it never relaxes a rule there.

forage then reads data from the directories in `site.json` `local_roots` (a NAS
mount, a lab server, a local disk) instead of a Globus collection. No Globus
credentials are needed. Inventories have the same format, so everything from
`build_index.py` onward (index, search, reports, snapshot, sigil) is unchanged.

## Read-only, on a path nothing else protects

The rule is the same as on Globus: only read. Never edit, move, copy, rename or
delete anything under a local root. What enforces it differs, because there is
no server to reject a write:

1. **The binding layer is the mount**: a read-only mount, or an account that
   can only read. `scan_local.py` checks every root before it walks and
   **refuses** one this account can write to.
2. **`--allow-writable` overrides that refusal.** It exists only in
   `scan_local.py`; no Globus script has it. Pass it only after the researcher
   approves it in this session, for these roots. Never pass it on your own to
   get past a refusal, and never carry an approval into a later session.
   Recommend a read-only mount first:
   `sudo mount --bind /data/lab /mnt/lab && sudo mount -o remount,bind,ro /mnt/lab`
3. **The code backstop**: the walk uses only `os.scandir` and `stat` and never
   opens a file; `--zip` opens an archive `'rb'` and reads only its index.
4. **Scope**: every `--path` and `--zip` must lie inside `local_roots`, so a
   mistyped path cannot walk a whole disk.

`scan_local.py` refuses to run at all unless `backend` is `local`.

## Commands, by workflow step

| Step | Globus (the workflow as written) | Local |
| --- | --- | --- |
| Before the first scan | `verify_readonly.py <COLLECTION_UUID>` | `scan_local.py --check` (ok / WRITABLE per root, no walk) |
| 2a — survey | `scan_endpoint.py <UUID> --path / --depth 2` | `scan_local.py --depth 2 --out knowledge/survey.jsonl` (no `--path` = all `local_roots`) |
| 3 — scan | `scan_endpoint.py <UUID> --path ... --depth 5` | `scan_local.py --path /mnt/lab/projects/ --depth 5 --out knowledge/inventory.jsonl` (same options) |
| 3a — find archives | `zip_index.py --find <inventory>` | the same; it is local and makes no network calls |
| 3a — list archives | `zip_index.py "$GLOBUS_AGENT_COLLECTION_ID" --zip ...` | `scan_local.py --zip /mnt/lab/a.zip --out knowledge/inventory_zip_<name>.jsonl` |

A local walk takes minutes where a Globus walk takes hours, but Steps 2 and 2a
still apply: scoping is about what the researcher's goal needs, not only cost.
The archive ask in Step 3a is unchanged too: listing is cheap, but the
researcher decides which archives to open, and extracting stays their job.

## Identity

Local records carry `collection_id` = `local_label` from `site.json`, else
`local:<hostname>`. It is part of every `file_key`, so keep it stable: set
`local_label` when the same mount is scanned from more than one host.
