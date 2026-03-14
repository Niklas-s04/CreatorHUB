import React, { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export default function SettingsPage() {
  const [docs, setDocs] = useState<any[]>([])
  const [err, setErr] = useState<string | null>(null)

  async function load() {
    try {
      setErr(null)
      const d = await apiFetch('/knowledge')
      setDocs(d)
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  useEffect(() => { load() }, [])

  async function save(doc: any) {
    try {
      setErr(null)
      await apiFetch(`/knowledge/${doc.id}`, { method: 'PATCH', body: JSON.stringify({ title: doc.title, content: doc.content, type: doc.type }) })
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  return (
    <div className="container">
      <h2>Einstellungen</h2>
      <div className="muted">
        Brand Voice / Policy / Templates (werden vom E-Mail-Assistenten zusätzlich zu festen Creator-Regeln verwendet).
      </div>
      {err && <div className="error">{err}</div>}
      <div style={{ marginTop: 12 }}>
        {docs.map(d => <DocEditor key={d.id} doc={d} onSave={save} />)}
        {!docs.length && <div className="muted">Keine Docs.</div>}
      </div>
    </div>
  )
}

function DocEditor({ doc, onSave }: any) {
  const [title, setTitle] = useState(doc.title)
  const [content, setContent] = useState(doc.content)

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div>
          <div className="pill">{doc.type}</div>
          <div style={{ fontSize: 18, fontWeight: 800, marginTop: 6 }}>{doc.title}</div>
        </div>
        <button className="btn" onClick={() => onSave({ ...doc, title, content })}>Speichern</button>
      </div>
      <div style={{ marginTop: 10 }}>
        <div className="muted">Titel</div>
        <input value={title} onChange={e => setTitle(e.target.value)} style={{ width: '100%' }} />
      </div>
      <div style={{ marginTop: 10 }}>
        <div className="muted">Inhalt</div>
        <textarea value={content} onChange={e => setContent(e.target.value)} rows={10} style={{ width: '100%' }} />
      </div>
    </div>
  )
}