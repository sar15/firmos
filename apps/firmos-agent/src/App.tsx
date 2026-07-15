import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { invoke } from '@tauri-apps/api/core'
import './App.css'

type Company = { name: string; guid: string }
type Probe = { healthy: boolean; tally_version: string; license_mode: string; protocols: string[]; companies: Company[] }
type Config = { cloud_url: string; device_name: string; company_name: string; company_guid: string; port: number; write_enabled: boolean }
type Status = { paired: boolean; config?: Config; tally?: Probe }

const tallyDate = (date: Date) => date.toISOString().slice(0, 10).replaceAll('-', '')

export function App() {
  const [status, setStatus] = useState<Status>({ paired: false })
  const [probe, setProbe] = useState<Probe>()
  const [cloudUrl, setCloudUrl] = useState('https://app.firmos.in')
  const [code, setCode] = useState('')
  const [deviceName, setDeviceName] = useState('Accounts computer')
  const [companyGuid, setCompanyGuid] = useState('')
  const [port, setPort] = useState(9000)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('Checking this computer…')

  const [period] = useState(() => {
    const now = new Date()
    return { from_date: tallyDate(new Date(now.getFullYear(), now.getMonth(), 1)), to_date: tallyDate(now) }
  })

  const load = useCallback(async () => {
    try {
      const current = await invoke<Status>('get_status')
      setStatus(current)
      setProbe(current.tally)
      setMessage(current.paired ? 'FirmOS is connected to this computer.' : 'Open TallyPrime, then connect this computer.')
    } catch (error) { setMessage(String(error)) }
  }, [])

  useEffect(() => { void load() }, [load])

  const checkTally = async () => {
    setBusy('probe')
    try {
      const result = await invoke<Probe>('probe_tally', { port })
      setProbe(result)
      setCompanyGuid((value) => value || result.companies[0]?.guid || '')
      setMessage(result.companies.length ? 'TallyPrime is ready.' : 'TallyPrime is running, but no company is open.')
    } catch (error) { setMessage(String(error)) } finally { setBusy('') }
  }

  const pair = async (event: FormEvent) => {
    event.preventDefault()
    const company = probe?.companies.find((item) => item.guid === companyGuid)
    if (!company) return setMessage('Choose an open Tally company.')
    setBusy('pair')
    try {
      const current = await invoke<Status>('pair_agent', { input: {
        cloud_url: cloudUrl, pairing_code: code, device_name: deviceName,
        company_name: company.name, company_guid: company.guid, port,
      } })
      setStatus(current)
      setMessage('Connected securely. FirmOS can now read Tally and process approved purchases.')
    } catch (error) { setMessage(String(error)) } finally { setBusy('') }
  }

  const sync = async () => {
    setBusy('sync')
    try {
      const result = await invoke<{ ledgers: number; vouchers: number }>('sync_now', { period })
      setMessage(`Sync complete: ${result.ledgers} ledgers and ${result.vouchers} vouchers checked.`)
      await load()
    } catch (error) { setMessage(String(error)) } finally { setBusy('') }
  }

  const disconnect = async () => {
    setBusy('disconnect')
    try { await invoke('disconnect'); setStatus({ paired: false }); setMessage('This computer is disconnected.') }
    catch (error) { setMessage(String(error)) } finally { setBusy('') }
  }

  const toggleWrite = async () => {
    const enabled = !status.config?.write_enabled
    if (enabled && !window.confirm('Allow this installation to process only FirmOS-approved purchase vouchers? Every write is read back and verified.')) return
    setBusy('write')
    try {
      const current = await invoke<Status>('set_write_enabled', { enabled })
      setStatus(current)
      setMessage(enabled ? 'Local write permission is on. Cloud approval and all safety gates still apply.' : 'Local write permission is off.')
    } catch (error) { setMessage(String(error)) } finally { setBusy('') }
  }

  const diagnostics = async () => {
    setBusy('diagnostics')
    try {
      const path = await invoke<string>('create_diagnostics')
      setMessage(`Redacted diagnostics saved to ${path}`)
    } catch (error) { setMessage(String(error)) } finally { setBusy('') }
  }

  const connected = status.paired && status.config
  return <main>
    <header>
      <div className="mark" aria-hidden="true">F</div>
      <div><p className="eyebrow">FirmOS</p><h1>Tally Agent</h1></div>
      <span className={`badge ${connected ? 'good' : ''}`}><i />{connected ? 'Connected' : 'Not connected'}</span>
    </header>

    <section className="hero">
      <p className="eyebrow">Local, secure connection</p>
      <h2>{connected ? status.config?.company_name : 'Connect TallyPrime to FirmOS'}</h2>
      <p aria-live="polite">{message}</p>
    </section>

    {connected ? <>
      <section className="card health">
        <div><span>TallyPrime</span><strong>{status.tally?.healthy ? 'Running' : 'Needs attention'}</strong></div>
        <div><span>Protocol</span><strong>{status.tally?.protocols.join(', ') || 'XML'}</strong></div>
        <div><span>Company ID</span><strong title={status.config?.company_guid}>{status.config?.company_guid.slice(0, 12)}…</strong></div>
      </section>
      <section className="card actions">
        <div><h3>Keep FirmOS up to date</h3><p>Checks ledgers and purchase and sales vouchers for this month.</p></div>
        <button onClick={sync} disabled={!!busy}>{busy === 'sync' ? 'Checking…' : 'Sync now'}</button>
      </section>
      <section className="card permission">
        <div><p className="eyebrow">Write permission</p><h3>{status.config?.write_enabled ? 'Enabled on this computer' : 'Read-only'}</h3>
          <p>Only an approved purchase voucher can be posted. Unsupported Tally versions remain blocked.</p></div>
        <button className={status.config?.write_enabled ? 'danger' : ''} onClick={toggleWrite} disabled={!!busy}>
          {status.config?.write_enabled ? 'Turn off writes' : 'Enable approved writes'}
        </button>
      </section>
      <section className="detailGrid" aria-label="Diagnostics and updates">
        <article className="card mini"><p className="eyebrow">Diagnostics</p><h3>{status.tally?.healthy ? 'Local checks pass' : 'Tally needs attention'}</h3>
          <p>Agent 1.0.0 · Tally {status.tally?.tally_version || 'unknown'} · {status.tally?.license_mode || 'unknown license'}</p>
          <button className="miniButton" onClick={diagnostics} disabled={!!busy}>Create support file</button></article>
        <article className="card mini"><p className="eyebrow">Updates</p><h3>Release channel: stable</h3><p>Signed automatic updates stay disabled until the Windows release channel is certified.</p></article>
      </section>
      <p className="scope">Device requests are signed. Executed actions are journaled locally until FirmOS confirms the result.</p>
      <button className="textButton" onClick={disconnect} disabled={!!busy}>Disconnect this computer</button>
    </> : <form className="card form" onSubmit={pair}>
      <ol className="steps" aria-label="Connection steps">
        <li className={probe ? 'done' : 'current'}><span>1</span>Detect Tally</li>
        <li className={companyGuid ? 'done' : ''}><span>2</span>Choose company</li>
        <li className={code ? 'current' : ''}><span>3</span>Map client</li>
      </ol>
      <div className="row">
        <label>Tally port<input type="number" min="1" max="65535" value={port} onChange={(e) => setPort(Number(e.target.value))} /></label>
        <button type="button" className="secondary" onClick={checkTally} disabled={!!busy}>{busy === 'probe' ? 'Checking…' : 'Check Tally'}</button>
      </div>
      {probe && <><div className="probeSummary"><strong>Tally {probe.tally_version}</strong><span>{probe.license_mode} · XML integration</span></div>
      <label>Open company<select value={companyGuid} onChange={(e) => setCompanyGuid(e.target.value)} required>
        <option value="">Choose a company</option>{probe.companies.map((company) => <option key={company.guid} value={company.guid}>{company.name}</option>)}
      </select><small>FirmOS binds the company GUID, never the editable display name.</small></label></>}
      <label>FirmOS address<input value={cloudUrl} onChange={(e) => setCloudUrl(e.target.value)} type="url" required /></label>
      <label>One-time pairing code<input value={code} onChange={(e) => setCode(e.target.value)} minLength={20} required placeholder="Paste the 15-minute code from FirmOS" /><small>No permanent token is pasted or stored in a command.</small></label>
      <label>Computer name<input value={deviceName} onChange={(e) => setDeviceName(e.target.value)} minLength={2} required /></label>
      <button disabled={!probe || !!busy}>{busy === 'pair' ? 'Connecting…' : 'Connect securely'}</button>
    </form>}
    <footer>FirmOS never stores your Tally password. The device key stays in Windows Credential Manager.</footer>
  </main>
}

export default App
