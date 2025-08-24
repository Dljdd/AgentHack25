import React, { useEffect, useMemo, useState } from 'react'

const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://127.0.0.1:8000'

type Customer = {
  id: number
  name: string
  email?: string | null
  external_id?: string | null
  stripe_customer_id?: string | null
}

type Run = {
  id: number
  customer_id: number
  prompt: string
  provider?: string | null
  model?: string | null
  success: boolean
  cost_usd: number
  calls: number
  started_at?: string | null
  ended_at?: string | null
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<T>
}

export default function App() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')

  const [selectedCustomerId, setSelectedCustomerId] = useState<number | ''>('')
  const [prompt, setPrompt] = useState('Write a haiku about Postgres and Alembic')
  const [runs, setRuns] = useState<Run[]>([])
  const selectedCustomer = useMemo(
    () => customers.find((c) => c.id === selectedCustomerId),
    [customers, selectedCustomerId]
  )

  async function loadCustomers() {
    setLoading(true)
    setError(null)
    try {
      const data = await api<Customer[]>('/customers/')
      setCustomers(data)
    } catch (e: any) {
      setError(e?.message || 'Failed to load customers')
    } finally {
      setLoading(false)
    }
  }

  async function loadRuns(cid: number) {
    try {
      const data = await api<Run[]>(`/runs/by_customer/${cid}`)
      setRuns(data)
      return data
    } catch (e) {
      console.error(e)
      return [] as Run[]
    }
  }

  useEffect(() => {
    loadCustomers()
  }, [])

  useEffect(() => {
    if (typeof selectedCustomerId === 'number') loadRuns(selectedCustomerId)
  }, [selectedCustomerId])

  async function onAddCustomer(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    setError(null)
    try {
      const c = await api<Customer>('/customers/', {
        method: 'POST',
        body: JSON.stringify({ name, email: email || undefined }),
      })
      setCustomers((prev) => [c, ...prev])
      setName('')
      setEmail('')
      setSelectedCustomerId(c.id)
    } catch (e: any) {
      setError(e?.message || 'Failed to add customer')
    } finally {
      setLoading(false)
    }
  }

  async function onStartRun(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedCustomerId || !prompt.trim()) return
    setLoading(true)
    setError(null)
    try {
      const started = await api<Run>('/runs/start', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: selectedCustomerId,
          prompt,
          provider: 'google',
          model: 'google/gemini-2.0-flash',
        }),
      })
      // Auto-poll runs until this run completes or timeout
      const runId = (started as any)?.id as number | undefined
      let attempts = 0
      const maxAttempts = 12 // ~12s
      const poll = async () => {
        if (typeof selectedCustomerId !== 'number') return
        const latest = await loadRuns(selectedCustomerId)
        attempts += 1
        if (runId) {
          const r = latest.find((r) => r.id === runId)
          if (r && r.ended_at) return // completed
        }
        if (attempts < maxAttempts) {
          setTimeout(poll, 1000)
        }
      }
      setTimeout(poll, 700)
    } catch (e: any) {
      setError(e?.message || 'Failed to start run')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <header>
        <h1>RunLedger</h1>
        <span className="muted">Backend: {API_BASE}</span>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="panel">
        <h2>Add Customer</h2>
        <form onSubmit={onAddCustomer} className="row gap">
          <input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            placeholder="Email (optional)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button disabled={loading || !name.trim()} type="submit">
            Add
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Customers</h2>
        {loading && customers.length === 0 ? (
          <div>Loading…</div>
        ) : customers.length === 0 ? (
          <div className="muted">No customers yet.</div>
        ) : (
          <div className="list">
            {customers.map((c) => (
              <button
                key={c.id}
                className={c.id === selectedCustomerId ? 'item selected' : 'item'}
                onClick={() => setSelectedCustomerId(c.id)}
              >
                <div className="title">{c.name}</div>
                <div className="sub">{c.email || '—'}</div>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Start Run</h2>
        <form onSubmit={onStartRun} className="col gap">
          <select
            value={selectedCustomerId}
            onChange={(e) => setSelectedCustomerId(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">Select customer…</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <textarea
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <div className="row gap">
            <button disabled={loading || !selectedCustomerId || !prompt.trim()} type="submit">
              Start
            </button>
            {selectedCustomer && (
              <button
                type="button"
                onClick={() => loadRuns(selectedCustomer.id)}
              >
                Refresh Runs
              </button>
            )}
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Runs {selectedCustomer ? `for ${selectedCustomer.name}` : ''}</h2>
        {selectedCustomer ? (
          runs.length === 0 ? (
            <div className="muted">No runs yet.</div>
          ) : (
            <table className="runs">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Success</th>
                  <th>Calls</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td>{r.provider || '—'}</td>
                    <td>{r.model || '—'}</td>
                    <td>{!r.ended_at ? 'Pending' : r.success ? 'Yes' : 'No'}</td>
                    <td>{r.calls}</td>
                    <td>${r.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          <div className="muted">Select a customer to view runs.</div>
        )}
      </section>

      <footer>
        <span className="muted">React + Vite</span>
      </footer>
    </div>
  )
}
