# FirmOS Tally Agent

The Windows desktop bridge between a firm's local TallyPrime installation and FirmOS. It
discovers open companies, performs read snapshots, and executes only approved purchase
voucher writes after explicit local enablement. Financial payloads stay out of logs and
diagnostics.

## Development

```bash
npm ci
npm run lint
npm run build
npm run tauri dev
```

The app stores device credentials in the operating-system keyring and its durable queue in
`agent.db` under the app-data directory. It starts with Windows, runs from the system tray,
and resumes recorded work after a restart.

## Release boundary

Production claims require all three:

- an exact Tally version listed in `docs/current/SUPPORTED_VERSIONS.md`;
- a Windows installer signed by `.github/workflows/tally-agent-release.yml`;
- the physical TA-026 certification record.

Until that evidence exists, the backend refuses Tally writes by design.
