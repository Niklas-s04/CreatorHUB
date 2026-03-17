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
      <div className="page-header">
        <div>
          <h2 className="page-title">Einstellungen</h2>
          <div className="page-subtitle">
            Brand Voice / Policy / Templates für den E-Mail-Assistenten.
          </div>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
      <div className="section-gap">
        {docs.map(d => <DocEditor key={d.id} doc={d} onSave={save} />)}
        {!docs.length && <div className="empty-state">Keine Docs.</div>}
      </div>
    </div>
  )
}

function DocEditor({ doc, onSave }: any) {
  const [title, setTitle] = useState(doc.title)
  const [content, setContent] = useState(doc.content)

  return (
    <div className="card section-gap no-margin">
      <div className="page-header no-margin">
        <div>
          <div className="pill">{doc.type}</div>
          <div className="title-strong mt8">{doc.title}</div>
        </div>
        <button className="btn" onClick={() => onSave({ ...doc, title, content })}>Speichern</button>
      </div>
      <div className="section-gap">
        <div className="field-label">Titel</div>
        <input className="full-width" value={title} onChange={e => setTitle(e.target.value)} />
      </div>
      <div className="section-gap">
        <div className="field-label">Inhalt</div>
        <textarea className="full-width" value={content} onChange={e => setContent(e.target.value)} rows={10} />
      </div>
    </div>
  )
}