# Tally agent certification

Code completion is not a release certification. A tester must run this checklist on each
exact Tally `$$Version` and Windows build before adding it to `SUPPORTED_VERSIONS.md`.

## Required evidence

- Record Windows edition/build, Tally exact version, license mode, agent version, installer
  hash, signing certificate identity, test date, and tester.
- Install without Python or a terminal; confirm signature, per-machine install, autostart,
  tray operation, restart recovery, clean uninstall, and signed upgrade/rollback behavior.
- Confirm company discovery uses the stable company GUID and never a display name alone.
- Confirm full ledger/voucher sync, deterministic retry, integer-paise totals, deactivation,
  and no duplicate rows after interruption and restart.
- Confirm purchase creation uses the approved company/client/ledger mappings, balanced ledger
  entries, deterministic remote ID, strict Tally import result, and exact post-write readback.
- Confirm writes remain blocked for Educational mode, uncertified versions, missing mappings,
  incomplete sync, unhealthy devices, disabled local write access, and revoked devices.
- Confirm closed Tally, disabled port, no open company, permission failure, malformed XML,
  timeout, clock skew, replayed nonce, tampered body, lease expiry, and offline recovery each
  produce the expected safe state without duplicate financial writes.
- Inspect rotated logs and exported diagnostics: neither may contain voucher XML, amounts,
  ledger names, GST details, signing keys, or finance payloads.

## Release decision

Certification passes only when every item above has attached evidence and no open severity-1
or severity-2 defect. Record the exact version in `SUPPORTED_VERSIONS.md`; never certify a
version range by inference. The repository currently contains no completed physical record,
so the certified-version allowlist is intentionally empty and production writes stay blocked.
