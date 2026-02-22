import { useState, useRef, useCallback, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const STEPS = [
  { key: 'upload',    label: 'Upload PDF',            pct: 5  },
  { key: 'parse',     label: 'Parse PDF structure',   pct: 20 },
  { key: 'detect',    label: 'Detect currency & units',pct: 30 },
  { key: 'identify',  label: 'Identify IS sections',  pct: 40 },
  { key: 'ai',        label: 'AI extraction engine',  pct: 55 },
  { key: 'normalize', label: 'Normalize line items',  pct: 75 },
  { key: 'validate',  label: 'Arithmetic validation', pct: 82 },
  { key: 'excel',     label: 'Generate Excel output', pct: 90 },
  { key: 'done',      label: 'Complete',              pct: 100 },
]

function StepIndicator({ progress, stepLabel }) {
  const currentStep = STEPS.findIndex(s => s.pct > progress) - 1
  const displayStep = Math.max(0, Math.min(currentStep, STEPS.length - 1))

  return (
    <div className="space-y-3">
      {STEPS.map((step, i) => {
        const done = progress >= step.pct
        const active = i === displayStep + 1
        return (
          <div key={step.key} className="flex items-center gap-3">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
              done ? 'bg-teal-500 text-white' :
              active ? 'bg-blue-500 text-white spin-slow ring-2 ring-blue-300' :
              'bg-gray-200 text-gray-400'
            }`}>
              {done ? (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <div className={`w-2 h-2 rounded-full ${active ? 'bg-white' : 'bg-gray-400'}`} />
              )}
            </div>
            <span className={`text-sm transition-all duration-300 ${
              done ? 'text-teal-700 font-medium' :
              active ? 'text-blue-700 font-semibold' :
              'text-gray-400'
            }`}>{step.label}</span>
          </div>
        )
      })}
    </div>
  )
}

function Badge({ color, children }) {
  const colors = {
    green: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-100 text-amber-700 border-amber-200',
    red: 'bg-red-100 text-red-700 border-red-200',
    blue: 'bg-blue-100 text-blue-700 border-blue-200',
    gray: 'bg-gray-100 text-gray-600 border-gray-200',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${colors[color] || colors.gray}`}>
      {children}
    </span>
  )
}

function ConfBadge({ confidence }) {
  if (!confidence || confidence === 'N/A') return <Badge color="gray">N/A</Badge>
  if (confidence === 'HIGH') return <Badge color="green">HIGH</Badge>
  if (confidence === 'MEDIUM') return <Badge color="amber">MEDIUM</Badge>
  return <Badge color="red">LOW</Badge>
}

function ResultsTable({ summary, jobId }) {
  const valStatus = summary.validation_status
  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Currency', value: summary.currency, icon: '💱' },
          { label: 'Unit', value: summary.unit, icon: '📏' },
          { label: 'Years Found', value: summary.years?.join(', ') || '—', icon: '📅' },
          { label: 'Items Extracted', value: `${summary.line_items_found} / 20`, icon: '✅' },
        ].map(card => (
          <div key={card.label} className="bg-white rounded-xl border border-gray-200 p-3 text-center shadow-sm">
            <div className="text-2xl mb-1">{card.icon}</div>
            <div className="text-xs text-gray-500 uppercase tracking-wide font-medium">{card.label}</div>
            <div className="text-sm font-bold text-gray-800 mt-0.5 truncate">{card.value}</div>
          </div>
        ))}
      </div>

      {/* Validation status */}
      <div className={`rounded-xl border px-4 py-3 flex items-start gap-3 ${
        valStatus === 'PASSED' ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'
      }`}>
        <span className="text-xl mt-0.5">{valStatus === 'PASSED' ? '✅' : '⚠️'}</span>
        <div>
          <div className={`font-semibold text-sm ${valStatus === 'PASSED' ? 'text-emerald-700' : 'text-amber-700'}`}>
            Arithmetic Validation: {valStatus}
          </div>
          {summary.warnings?.length > 0 ? (
            <ul className="text-xs text-amber-600 mt-1 space-y-0.5 list-disc list-inside">
              {summary.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          ) : (
            <div className="text-xs text-emerald-600 mt-0.5">All arithmetic cross-checks passed.</div>
          )}
        </div>
      </div>

      {/* Download button */}
      <a
        href={`${API_BASE}/download/${jobId}`}
        download="financial_extraction.xlsx"
        className="flex items-center justify-center gap-2 w-full bg-gradient-to-r from-blue-900 to-teal-700 text-white font-semibold py-3.5 px-6 rounded-xl shadow-lg hover:opacity-90 transition-opacity text-sm"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        Download Excel Workbook (.xlsx)
      </a>

      <p className="text-xs text-gray-400 text-center">
        Includes Income Statement tab, Extraction Metadata tab, and How to Read This guide.
      </p>
    </div>
  )
}

export default function App() {
  const [phase, setPhase] = useState('idle') // idle | uploading | processing | done | error
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState(0)
  const [stepLabel, setStepLabel] = useState('')
  const [summary, setSummary] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState('')
  const fileInputRef = useRef()
  const pollRef = useRef()

  const startPolling = useCallback((id) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${id}`)
        const data = await res.json()
        setProgress(data.progress || 0)
        setStepLabel(data.step || '')

        if (data.status === 'done') {
          clearInterval(pollRef.current)
          setPhase('done')
          setSummary(data.summary)
        } else if (data.status === 'error') {
          clearInterval(pollRef.current)
          setPhase('error')
          setErrorMsg(data.step || 'Unknown error')
        }
      } catch {
        // ignore poll errors, keep retrying
      }
    }, 1200)
  }, [])

  useEffect(() => () => clearInterval(pollRef.current), [])

  const handleFile = useCallback(async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setPhase('error')
      setErrorMsg('Please upload a PDF file.')
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      setPhase('error')
      setErrorMsg('File too large. Please use a PDF under 20MB.')
      return
    }

    setFileName(file.name)
    setPhase('uploading')
    setProgress(5)
    setStepLabel('Uploading PDF...')
    setErrorMsg('')
    setSummary(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_BASE}/extract`, { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }
      const { job_id } = await res.json()
      setJobId(job_id)
      setPhase('processing')
      startPolling(job_id)
    } catch (e) {
      setPhase('error')
      setErrorMsg(e.message)
    }
  }, [startPolling])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }, [handleFile])

  const onDragOver = (e) => { e.preventDefault(); setDragging(true) }
  const onDragLeave = () => setDragging(false)

  const reset = () => {
    clearInterval(pollRef.current)
    setPhase('idle')
    setJobId(null)
    setProgress(0)
    setStepLabel('')
    setSummary(null)
    setErrorMsg('')
    setFileName('')
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      {/* Navbar */}
      <header className="bg-gradient-to-r from-blue-950 to-teal-800 text-white px-6 py-4 shadow-xl">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center text-lg">📊</div>
          <div>
            <div className="font-bold text-sm tracking-wide">INTERNAL RESEARCH PORTAL</div>
            <div className="text-blue-200 text-xs">Financial Statement Extraction Tool — Option A</div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8 space-y-6">

        {/* Info bar */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 flex flex-wrap gap-4 text-xs text-blue-700">
          <span>🎯 <strong>Upload</strong> an annual report or financial statement PDF</span>
          <span>🤖 <strong>AI extracts</strong> all Income Statement line items</span>
          <span>📥 <strong>Download</strong> structured, analyst-ready Excel workbook</span>
          <span className="text-blue-400">Max file size: 20MB · Processing: ~30–60s</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

          {/* LEFT PANEL */}
          <div className="lg:col-span-3 space-y-5">

            {/* Upload zone */}
            {(phase === 'idle' || phase === 'error') && (
              <div
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className={`bg-white border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 shadow-sm
                  ${dragging ? 'border-teal-500 bg-teal-50 scale-[1.01]' : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50/30'}`}
              >
                <div className="text-5xl mb-4">{dragging ? '📂' : '📄'}</div>
                <div className="text-lg font-bold text-gray-700 mb-1">
                  {dragging ? 'Drop to extract' : 'Drop PDF here'}
                </div>
                <div className="text-sm text-gray-500 mb-4">or click to browse files</div>
                <div className="inline-flex items-center gap-2 bg-blue-900 text-white text-sm font-semibold px-5 py-2.5 rounded-lg shadow hover:bg-blue-800 transition-colors">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  Select PDF
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={e => handleFile(e.target.files[0])}
                />
                <div className="mt-4 text-xs text-gray-400">Supports: 10-Ks, Annual Reports, Financial Statements</div>
              </div>
            )}

            {/* Error message */}
            {phase === 'error' && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                <span className="text-xl">❌</span>
                <div>
                  <div className="font-semibold text-red-700 text-sm">Extraction Failed</div>
                  <div className="text-red-600 text-sm mt-0.5">{errorMsg}</div>
                  <button onClick={reset} className="mt-2 text-xs text-red-600 underline hover:text-red-800">Try again</button>
                </div>
              </div>
            )}

            {/* Processing view */}
            {(phase === 'uploading' || phase === 'processing') && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
                    <svg className="w-5 h-5 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                  </div>
                  <div>
                    <div className="font-bold text-gray-800 text-sm">Processing: {fileName}</div>
                    <div className="text-xs text-gray-500">{stepLabel}</div>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-600 to-teal-500 rounded-full transition-all duration-700 pulse-bar"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="text-right text-xs text-gray-400">{progress}%</div>
              </div>
            )}

            {/* Done view */}
            {phase === 'done' && summary && (
              <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center text-xl">✅</div>
                    <div>
                      <div className="font-bold text-gray-800">Extraction Complete</div>
                      <div className="text-xs text-gray-500">{fileName}</div>
                    </div>
                  </div>
                  <button onClick={reset} className="text-xs text-gray-400 hover:text-gray-600 underline">
                    New file
                  </button>
                </div>
                <ResultsTable summary={summary} jobId={jobId} />
              </div>
            )}
          </div>

          {/* RIGHT PANEL — steps & info */}
          <div className="lg:col-span-2 space-y-5">

            {/* Pipeline steps */}
            <div className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm">
              <div className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Extraction Pipeline</div>
              <StepIndicator progress={progress} stepLabel={stepLabel} />
            </div>

            {/* What you get */}
            <div className="bg-gradient-to-br from-blue-950 to-teal-800 rounded-2xl p-5 text-white shadow-sm">
              <div className="text-xs font-bold text-blue-300 uppercase tracking-widest mb-3">Output Includes</div>
              <ul className="space-y-2 text-sm text-blue-100">
                {[
                  '20 canonical Income Statement line items',
                  'Multi-year columns (all years in doc)',
                  'Source label & page reference per item',
                  'HIGH / MEDIUM / LOW confidence badges',
                  'Arithmetic validation (Gross Profit, OpInc)',
                  'Not Reported for absent line items',
                  'Extraction metadata & audit trail tab',
                  'Color-coded analyst-ready Excel workbook',
                ].map(item => (
                  <li key={item} className="flex items-start gap-2">
                    <span className="text-teal-300 mt-0.5 flex-shrink-0">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Limitations */}
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
              <div className="text-xs font-bold text-amber-700 uppercase tracking-widest mb-2">Free Tier Limits</div>
              <ul className="space-y-1 text-xs text-amber-700">
                <li>• First request may take 15–30s (cold start)</li>
                <li>• Max file size: 20MB (recommend &lt;10MB)</li>
                <li>• 1 concurrent extraction at a time</li>
                <li>• Output not stored — download before leaving</li>
              </ul>
            </div>
          </div>
        </div>
      </main>

      <footer className="text-center py-4 text-xs text-gray-400 border-t border-gray-200 bg-white mt-4">
        Internal Research Portal · Financial Statement Extraction Tool · L2 Assignment · Powered by Claude claude-sonnet-4-6
      </footer>
    </div>
  )
}
