// GroundConnect AI — Supplemental pages for remaining SRS gaps
// Covers: CIT-21, DSH-04, DSH-08, LNG-02/03/05, COM-07/08/11, NTF-01/03/04,
//         CIT-19, IDN-03, TPI-02/03, OFF improved UI, EVD-02 full flow

import { useState, useEffect, useRef } from 'react'
import { AlertTriangle, CheckCircle2, XCircle, Clock, Map, Globe, Bell, BellOff, BarChart2, Shield, Smartphone, Wifi, WifiOff, Upload, Lock, Languages, RefreshCw, PlusCircle, Send, Zap, Filter, Download, Eye, AlertCircle, Activity, Server } from 'lucide-react'
import { SectionHeader, KpiCard, StatusBadge, Alert, Modal, Confirm, FilterPills, Avatar } from '../components/UI'
import { RadialProgress, LineMetricChart } from '../components/Charts'
import { CITIZEN_ISSUES, OFFLINE_QUEUE, TPI_QUEUE } from '../data'

// ── i18n stub (LNG-02: externalised strings) ──────────────────────────────
const STRINGS = {
  en: {
    submit_issue: 'Report an issue', track_issue: 'Track issue', my_issues: 'My issues',
    category: 'Category', describe: 'Describe the issue', submit: 'Submit report',
    reference: 'Reference number', otp: 'One-time code', track: 'Track status',
    voice_sufficient: 'A voice recording alone is sufficient.',
  },
  hi: {
    submit_issue: 'समस्या दर्ज करें', track_issue: 'समस्या ट्रैक करें', my_issues: 'मेरी समस्याएं',
    category: 'श्रेणी', describe: 'समस्या का विवरण दें', submit: 'रिपोर्ट सबमिट करें',
    reference: 'संदर्भ संख्या', otp: 'एक बार कोड', track: 'स्थिति ट्रैक करें',
    voice_sufficient: 'केवल वॉइस रिकॉर्डिंग पर्याप्त है।',
  },
  kn: {
    submit_issue: 'ದೂರು ದಾಖಲಿಸಿ', track_issue: 'ದೂರು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ', my_issues: 'ನನ್ನ ದೂರುಗಳು',
    category: 'ವರ್ಗ', describe: 'ಸಮಸ್ಯೆಯನ್ನು ವಿವರಿಸಿ', submit: 'ವರದಿ ಸಲ್ಲಿಸಿ',
    reference: 'ಉಲ್ಲೇಖ ಸಂಖ್ಯೆ', otp: 'ಒಂದು ಬಾರಿ ಕೋಡ್', track: 'ಸ್ಥಿತಿ ಟ್ರ್ಯಾಕ್ ಮಾಡಿ',
    voice_sufficient: 'ಧ್ವನಿ ರೆಕಾರ್ಡಿಂಗ್ ಮಾತ್ರ ಸಾಕು.',
  },
}
export function useStrings(lang = 'en') { return STRINGS[lang] || STRINGS.en }

// ══════════════════════════════════════════════════════════════════════════
// SERVICE DEBT INDEX — CIT-21, DSH-08
// ══════════════════════════════════════════════════════════════════════════
export function ServiceDebtIndex({ accent = '#4f46e5' }) {
  const [drillNode, setDrillNode] = useState(null)

  const nodes = [
    {
      name: 'Zone A — Booth 12', sdi: 34, grade: 'Low',
      components: { unresolved: { value: 12, weight: 0.35, label: 'Unresolved volume (age+severity weighted)' }, confirmedRate: { value: 88, weight: 0.30, label: 'Confirmed-resolution rate (%)' }, corroboration: { value: 4.2, weight: 0.20, label: 'Corroboration-weighted severity' }, slaBreach: { value: 2, weight: 0.15, label: 'SLA breach frequency (last 30d)' } },
      issues: 14, resolved: 12, confirmed: 11, size: 8, intake: 1.75,
    },
    {
      name: 'Zone B — Booth 19', sdi: 61, grade: 'Medium',
      components: { unresolved: { value: 28, weight: 0.35, label: 'Unresolved volume (age+severity weighted)' }, confirmedRate: { value: 71, weight: 0.30, label: 'Confirmed-resolution rate (%)' }, corroboration: { value: 6.8, weight: 0.20, label: 'Corroboration-weighted severity' }, slaBreach: { value: 8, weight: 0.15, label: 'SLA breach frequency (last 30d)' } },
      issues: 22, resolved: 16, confirmed: 11, size: 6, intake: 3.67,
    },
    {
      name: 'Zone C — Booth 31', sdi: 87, grade: 'High',
      components: { unresolved: { value: 51, weight: 0.35, label: 'Unresolved volume (age+severity weighted)' }, confirmedRate: { value: 42, weight: 0.30, label: 'Confirmed-resolution rate (%)' }, corroboration: { value: 9.1, weight: 0.20, label: 'Corroboration-weighted severity' }, slaBreach: { value: 19, weight: 0.15, label: 'SLA breach frequency (last 30d)' } },
      issues: 31, resolved: 18, confirmed: 8, size: 5, intake: 6.2,
    },
    {
      name: 'Zone D — Booth 44', sdi: 22, grade: 'Low',
      components: { unresolved: { value: 7, weight: 0.35, label: 'Unresolved volume (age+severity weighted)' }, confirmedRate: { value: 95, weight: 0.30, label: 'Confirmed-resolution rate (%)' }, corroboration: { value: 2.1, weight: 0.20, label: 'Corroboration-weighted severity' }, slaBreach: { value: 1, weight: 0.15, label: 'SLA breach frequency (last 30d)' } },
      issues: 9, resolved: 9, confirmed: 8, size: 7, intake: 1.29,
    },
  ]

  const gradeColor = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' }
  const gradeClass = { Low: 'badge-success', Medium: 'badge-warning', High: 'badge-danger' }

  return (
    <div className="space-y-4 page">
      <Alert type="info">
        Service Debt Index measures service backlog only. It contains <strong>no input derived from citizen identity, opinion, or political attributes</strong> (CIT-22). Always shown with full component breakdown and drill-through.
      </Alert>

      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Avg SDI (district)" value="51" delta="3 points up vs last month" deltaPos={false} icon={BarChart2} accent={accent}/>
        <KpiCard label="Confirmed resolution" value="69%" delta="vs 84% claimed" deltaPos={false} icon={CheckCircle2} accent="#10b981" sub="Gap: 15 pts (CIT-19)"/>
        <KpiCard label="Claimed resolution" value="84%" delta="Declared by workers" deltaPos icon={Activity} accent="#f59e0b"/>
        <KpiCard label="Active disputes" value="1" delta="Reopened with shorter SLA" deltaPos={false} icon={XCircle} accent="#f43f5e"/>
      </div>

      {/* Confirmed vs claimed gap — CIT-19 */}
      <div className="card p-5">
        <SectionHeader title="Confirmed vs claimed resolution gap" icon={BarChart2} accent={accent}/>
        <Alert type="warning" className="mb-4">
          Confirmed resolution (citizen-verified) is tracked separately from claimed resolution (worker-declared). The gap between them is a headline metric (CIT-19).
        </Alert>
        <div className="grid grid-cols-3 gap-4">
          {[
            { label:'Claimed resolved', value:84, color:'#f59e0b', sub:'Worker declared' },
            { label:'Confirmed resolved', value:69, color:'#10b981', sub:'Citizen verified' },
            { label:'Disputed and reopened', value:5, color:'#f43f5e', sub:'Shorter SLA clock (CIT-20)' },
          ].map(m => (
            <div key={m.label} className="flex flex-col items-center gap-2">
              <RadialProgress value={m.value} color={m.color} size={110} label={m.label} sublabel={m.sub}/>
            </div>
          ))}
        </div>
      </div>

      {/* Per-node SDI table with drill-through */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
          <SectionHeader title="Per-unit Service Debt Index" icon={BarChart2} accent={accent}>
            <span className="text-[10px] text-slate-400">Normalised for unit size and intake · Click to drill through</span>
          </SectionHeader>
        </div>
        <table className="tbl">
          <thead><tr><th>Unit</th><th>SDI score</th><th>Grade</th><th>Issues</th><th>Resolved</th><th>Confirmed</th><th>Intake/member</th><th>Drill</th></tr></thead>
          <tbody>
            {nodes.map(n => (
              <tr key={n.name} className="cursor-pointer hover:bg-primary-50/30 dark:hover:bg-primary-950/10" onClick={() => setDrillNode(n)}>
                <td className="font-semibold text-slate-800 dark:text-slate-200">{n.name}</td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                      <div className="h-1.5 rounded-full transition-all" style={{ width: `${n.sdi}%`, background: gradeColor[n.grade] }}/>
                    </div>
                    <span className="font-black text-sm" style={{ color: gradeColor[n.grade] }}>{n.sdi}</span>
                  </div>
                </td>
                <td><span className={`badge ${gradeClass[n.grade]}`}>{n.grade}</span></td>
                <td className="text-slate-500">{n.issues}</td>
                <td className="text-slate-500">{n.resolved}</td>
                <td><span className={`font-bold ${n.confirmed/n.resolved < 0.8 ? 'text-rose-500' : 'text-emerald-600'}`}>{n.confirmed}</span></td>
                <td className="text-slate-500 font-mono">{n.intake.toFixed(2)}</td>
                <td><button className="btn-xs btn-outline" onClick={e => { e.stopPropagation(); setDrillNode(n) }}>Drill through</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Drill-through modal */}
      <Modal open={!!drillNode} onClose={() => setDrillNode(null)} title={`SDI breakdown — ${drillNode?.name}`} size="md">
        {drillNode && (
          <div className="space-y-4">
            <Alert type="info">The index is never an opaque number. Every component and its weight is shown here and links to source records (CIT-21).</Alert>
            <div className="flex items-center gap-4">
              <div className="text-4xl font-black" style={{ color: gradeColor[drillNode.grade] }}>{drillNode.sdi}</div>
              <div>
                <div className="font-bold text-slate-900 dark:text-white">{drillNode.grade} debt</div>
                <div className="text-xs text-slate-400">Normalised for {drillNode.size} members · {drillNode.intake.toFixed(2)} intake/member</div>
              </div>
            </div>
            <div className="space-y-3">
              {Object.entries(drillNode.components).map(([key, comp]) => (
                <div key={key} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{comp.label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-slate-400 font-mono">weight: {(comp.weight * 100).toFixed(0)}%</span>
                      <span className="font-black text-sm text-primary-600">{comp.value}{key === 'confirmedRate' ? '%' : ''}</span>
                    </div>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                    <div className="h-1.5 rounded-full bg-primary-600" style={{ width: `${Math.min(100, key === 'confirmedRate' ? comp.value : comp.value * 2)}%` }}/>
                  </div>
                </div>
              ))}
            </div>
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800">
              <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Source issues (drill-through)</div>
              {CITIZEN_ISSUES.filter(c => c.location.includes(drillNode.name.split('—')[1]?.trim() || 'Zone')).slice(0,3).map(c => (
                <div key={c.id} className="flex items-center gap-2 text-xs py-1.5 border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <span className="font-mono font-black text-primary-600">{c.id}</span>
                  <span className="flex-1 truncate text-slate-600 dark:text-slate-400">{c.title}</span>
                  <StatusBadge status={c.status}/>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// GEOGRAPHIC VIEW — DSH-04 (permission-scoped map layer)
// ══════════════════════════════════════════════════════════════════════════
export function GeographicView({ accent = '#4f46e5' }) {
  const [mapLayer, setMapLayer] = useState('issues')
  const [hoveredZone, setHoveredZone] = useState(null)

  // Synthetic SVG map of the district zones
  const zones = [
    { id: 'zone-a', label: 'Zone A\nBooth 12', x: 80, y: 80, w: 170, h: 130, issues: 14, tasks: 5, status: 'active', sdi: 34, color: '#10b981' },
    { id: 'zone-b', label: 'Zone B\nBooth 19', x: 270, y: 80, w: 160, h: 130, issues: 22, tasks: 3, status: 'active', sdi: 61, color: '#f59e0b' },
    { id: 'zone-c', label: 'Zone C\nBooth 31', x: 80, y: 230, w: 170, h: 130, issues: 31, tasks: 7, status: 'dark', sdi: 87, color: '#f43f5e' },
    { id: 'zone-d', label: 'Zone D\nBooth 44', x: 270, y: 230, w: 160, h: 130, issues: 9, tasks: 4, status: 'active', sdi: 22, color: '#10b981' },
  ]

  const getColor = (zone) => {
    if (mapLayer === 'issues') return zone.issues > 25 ? '#f43f5e' : zone.issues > 15 ? '#f59e0b' : '#10b981'
    if (mapLayer === 'sdi') return zone.sdi > 70 ? '#f43f5e' : zone.sdi > 45 ? '#f59e0b' : '#10b981'
    if (mapLayer === 'status') return zone.status === 'dark' ? '#f59e0b' : '#10b981'
    return '#4f46e5'
  }

  const getValue = (zone) => {
    if (mapLayer === 'issues') return `${zone.issues} issues`
    if (mapLayer === 'sdi') return `SDI ${zone.sdi}`
    if (mapLayer === 'status') return zone.status
    return `${zone.tasks} tasks`
  }

  const h = hoveredZone

  return (
    <div className="space-y-4 page">
      <Alert type="info">Geographic view renders only data within the viewer's authorized subtree — including in map tiles, clusters, and counts (DSH-04).</Alert>

      <div className="flex items-center gap-3 flex-wrap">
        <FilterPills options={['issues', 'sdi', 'status', 'tasks']} active={mapLayer} onChange={setMapLayer}/>
        <div className="ml-auto flex items-center gap-2">
          <div className="flex gap-3 text-[10px] text-slate-400">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-500"/>&nbsp;Low</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-amber-400"/>&nbsp;Medium</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-rose-500"/>&nbsp;High</span>
          </div>
        </div>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 260px' }}>
        {/* Map canvas */}
        <div className="card p-4">
          <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-3">North District — authorized subtree</div>
          <svg viewBox="0 0 480 390" className="w-full rounded-xl" style={{ background: '#f8fafc' }}>
            {/* District boundary */}
            <rect x="60" y="50" width="390" height="330" rx="12" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="6 4"/>
            <text x="245" y="44" textAnchor="middle" fontSize="11" fill="#94a3b8" fontWeight="600">North District</text>

            {zones.map(zone => {
              const color = getColor(zone)
              const isHov = hoveredZone?.id === zone.id
              return (
                <g key={zone.id} onMouseEnter={() => setHoveredZone(zone)} onMouseLeave={() => setHoveredZone(null)} style={{ cursor: 'pointer' }}>
                  <rect x={zone.x} y={zone.y} width={zone.w} height={zone.h} rx="10"
                    fill={color + (isHov ? 'cc' : '28')} stroke={color} strokeWidth={isHov ? 2.5 : 1.5}
                    style={{ transition: 'all 0.15s' }}/>
                  {zone.status === 'dark' && (
                    <circle cx={zone.x + zone.w - 18} cy={zone.y + 18} r="8" fill="#f59e0b"/>
                  )}
                  {zone.label.split('\n').map((line, i) => (
                    <text key={i} x={zone.x + zone.w / 2} y={zone.y + zone.h / 2 - 8 + i * 16}
                      textAnchor="middle" fontSize="11" fontWeight="700" fill={color === '#10b981' ? '#065f46' : color === '#f59e0b' ? '#92400e' : '#9f1239'}>
                      {line}
                    </text>
                  ))}
                  <text x={zone.x + zone.w / 2} y={zone.y + zone.h / 2 + 26}
                    textAnchor="middle" fontSize="12" fontWeight="800" fill={color}>
                    {getValue(zone)}
                  </text>
                </g>
              )
            })}

            {/* Issue markers */}
            {mapLayer === 'issues' && zones.map(zone =>
              zone.issues > 20 ? (
                <circle key={`m-${zone.id}`} cx={zone.x + zone.w / 2} cy={zone.y + 22} r="10"
                  fill="#f43f5e" opacity="0.9"/>
              ) : null
            )}
          </svg>
        </div>

        {/* Detail panel */}
        <div className="card p-4">
          {h ? (
            <>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-3 h-3 rounded-full" style={{ background: getColor(h) }}/>
                <div className="font-black text-sm text-slate-900 dark:text-white">{h.label.replace('\n', ' ')}</div>
              </div>
              <StatusBadge status={h.status}/>
              <div className="space-y-2 mt-4">
                {[['Open issues', h.issues], ['Active tasks', h.tasks], ['SDI score', h.sdi], ['Status', h.status]].map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs border-b border-slate-50 dark:border-slate-800/60 pb-2">
                    <span className="text-slate-400">{k}</span>
                    <span className="font-bold text-slate-700 dark:text-slate-300">{v}</span>
                  </div>
                ))}
              </div>
              {h.status === 'dark' && <Alert type="warning" className="mt-3">Dark unit — no field reports in 7+ days. This is an absence signal, not a loyalty judgment.</Alert>}
            </>
          ) : (
            <div className="h-48 flex flex-col items-center justify-center text-slate-300 dark:text-slate-600 gap-2 text-xs">
              <Map size={28} strokeWidth={1.5}/><span>Hover a zone to inspect</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// MESSAGE ADVANCED — COM-07 recall, COM-08 scheduled, COM-09 receipts, COM-11 watermark
// ══════════════════════════════════════════════════════════════════════════
export function MessageAdvanced({ accent = '#4f46e5' }) {
  const [tab, setTab] = useState('scheduled')
  const [confirmRecall, setConfirmRecall] = useState(null)
  const [showCompose, setShowCompose] = useState(false)
  const [showWatermark, setShowWatermark] = useState(false)

  const scheduled = [
    { id: 'SCH-001', subject: 'Weekly briefing — all coordinators', target: 'North District', recipients: 890, scheduledFor: 'Aug 15 09:00', status: 'pending', dispatched: 0 },
    { id: 'SCH-002', subject: 'Performance review reminder', target: 'State HQ', recipients: 12400, scheduledFor: 'Aug 20 08:00', status: 'pending', dispatched: 0 },
    { id: 'SCH-003', subject: 'Emergency drill notification', target: 'East District', recipients: 1240, scheduledFor: 'Aug 14 07:00', status: 'dispatching', dispatched: 620 },
  ]

  const receipts = [
    { recipient: 'Sita Devi', role: 'Coordinator', sent: '09:14:02', delivered: '09:14:05', read: '09:16:30', ack: '09:17:45', status: 'acknowledged' },
    { recipient: 'Kiran Rao', role: 'Leader', sent: '09:14:02', delivered: '09:14:08', read: '09:15:12', ack: null, status: 'read' },
    { recipient: 'Arjun Patel', role: 'Field Worker', sent: '09:14:02', delivered: '09:14:22', read: null, ack: null, status: 'delivered' },
    { recipient: 'Dev Patel', role: 'Coordinator', sent: '09:14:02', delivered: null, read: null, ack: null, status: 'failed', failReason: 'Device unreachable — offline >72h' },
    { recipient: 'Venkat Rao', role: 'Field Worker', sent: '09:14:02', delivered: '09:14:45', read: '09:19:00', ack: null, status: 'read' },
  ]

  return (
    <div className="space-y-4 page">
      <div className="flex gap-1 p-1 bg-slate-100 dark:bg-slate-800 rounded-xl w-fit">
        {['scheduled', 'receipts', 'watermark'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-xs font-bold capitalize transition-all ${tab === t ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
            {t === 'watermark' ? 'Watermarking' : t === 'receipts' ? 'Delivery receipts' : 'Scheduled sends'}
          </button>
        ))}
      </div>

      {/* Scheduled sends — COM-08: cancellable before dispatch */}
      {tab === 'scheduled' && (
        <div className="space-y-3">
          <Alert type="info">Scheduled sends are cancellable at any point before dispatch begins (COM-08). In-flight sends can be halted within 30 seconds (COM-07).</Alert>
          <div className="flex justify-end">
            <button onClick={() => setShowCompose(true)} className="btn-primary btn-sm"><PlusCircle size={13}/>Schedule new send</button>
          </div>
          <div className="card overflow-hidden">
            <table className="tbl">
              <thead><tr><th>ID</th><th>Subject</th><th>Target</th><th>Recipients</th><th>Scheduled for</th><th>Progress</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                {scheduled.map(s => (
                  <tr key={s.id}>
                    <td className="font-mono font-black text-primary-600 dark:text-primary-400">{s.id}</td>
                    <td className="font-semibold text-slate-800 dark:text-slate-200 max-w-xs truncate">{s.subject}</td>
                    <td className="text-slate-500">{s.target}</td>
                    <td>{s.recipients.toLocaleString()}</td>
                    <td className="text-slate-400">{s.scheduledFor}</td>
                    <td>
                      {s.dispatched > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                            <div className="h-1.5 rounded-full bg-primary-600" style={{ width: `${(s.dispatched / s.recipients) * 100}%` }}/>
                          </div>
                          <span className="text-[10px] text-slate-400">{s.dispatched.toLocaleString()}/{s.recipients.toLocaleString()}</span>
                        </div>
                      ) : <span className="text-slate-300 text-xs">Not started</span>}
                    </td>
                    <td><StatusBadge status={s.status === 'dispatching' ? 'In Progress' : 'pending'}/></td>
                    <td>
                      <div className="flex gap-1">
                        {s.status === 'pending' && (
                          <button onClick={() => setConfirmRecall(s)} className="btn-xs btn-secondary">Cancel</button>
                        )}
                        {s.status === 'dispatching' && (
                          <button onClick={() => setConfirmRecall({ ...s, isRecall: true })} className="btn-xs btn-danger">Halt now</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Per-recipient delivery receipts — COM-09 */}
      {tab === 'receipts' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Alert type="info" className="flex-1 mr-4">Per-recipient telemetry: sent → delivered → read → acknowledged timestamps for every recipient (COM-09).</Alert>
            <button className="btn-outline btn-sm flex-shrink-0"><Download size={13}/>Export CSV</button>
          </div>
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: 'Sent', value: 5, color: '#4f46e5' }, { label: 'Delivered', value: 4, color: '#10b981' },
              { label: 'Read', value: 3, color: '#8b5cf6' }, { label: 'Acknowledged', value: 1, color: '#f59e0b' },
              { label: 'Failed', value: 1, color: '#f43f5e' },
            ].map(m => (
              <div key={m.label} className="card p-3 text-center">
                <div className="text-2xl font-black" style={{ color: m.color }}>{m.value}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">{m.label}</div>
              </div>
            ))}
          </div>
          <div className="card overflow-hidden">
            <table className="tbl">
              <thead><tr><th>Recipient</th><th>Role</th><th>Sent</th><th>Delivered</th><th>Read</th><th>Acknowledged</th><th>Status</th><th>Failure reason</th></tr></thead>
              <tbody>
                {receipts.map((r, i) => (
                  <tr key={i}>
                    <td className="font-semibold">{r.recipient}</td>
                    <td className="text-slate-500 text-[10px]">{r.role}</td>
                    <td className="font-mono text-[10px] text-slate-400">{r.sent}</td>
                    <td className="font-mono text-[10px] text-slate-400">{r.delivered || '—'}</td>
                    <td className="font-mono text-[10px] text-slate-400">{r.read || '—'}</td>
                    <td className="font-mono text-[10px] text-slate-400">{r.ack || '—'}</td>
                    <td><StatusBadge status={r.status === 'acknowledged' ? 'active' : r.status === 'failed' ? 'denied' : r.status === 'read' ? 'read' : 'pending'}/></td>
                    <td className="text-rose-500 text-[10px]">{r.failReason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Dynamic watermark — COM-11 */}
      {tab === 'watermark' && (
        <div className="space-y-4">
          <Alert type="info">Sensitive messages render with a dynamic watermark containing: user ID, organisation, branch, message ID, and timestamp (COM-11). This deters leakage but cannot prevent photographing a screen.</Alert>
          <div className="card p-5">
            <SectionHeader title="Watermark preview" icon={Eye} accent={accent}/>
            <div className="relative p-6 rounded-xl bg-slate-50 dark:bg-slate-800 border border-dashed border-slate-200 dark:border-slate-700 overflow-hidden">
              {/* Simulated message content */}
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-4">
                Immediate mobilisation required across all 7 districts. Report to designated assembly points by 11:00 AM. This message is classified as Emergency priority.
              </p>
              {/* Watermark overlay — tiled */}
              <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-[0.08] dark:opacity-[0.12]" style={{ userSelect: 'none' }}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="text-[9px] font-mono text-slate-900 dark:text-white whitespace-nowrap"
                    style={{ transform: `rotate(-25deg) translateY(${i * 28}px) translateX(-10%)`, position: 'absolute', top: `${i * 50 - 20}px`, left: '-10%', width: '130%' }}>
                    RK-IDN-005 · STATE-HQ · MSG-001 · {new Date().toISOString().slice(0, 19)}Z
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-3 text-xs text-slate-400 flex items-center gap-2">
              <AlertCircle size={12}/>
              Watermark content: <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1.5 rounded">USER_ID · ORG · BRANCH · MSG_ID · TIMESTAMP</code>
            </div>
          </div>
          <div className="card p-4">
            <SectionHeader title="Sensitivity configuration" icon={Shield} accent={accent}/>
            <div className="space-y-3">
              {[
                { type: 'Emergency', watermark: true, expiry: true, forwardBlock: true },
                { type: 'Instruction', watermark: false, expiry: true, forwardBlock: true },
                { type: 'Announcement', watermark: false, expiry: false, forwardBlock: false },
                { type: 'Survey', watermark: false, expiry: true, forwardBlock: false },
              ].map(t => (
                <div key={t.type} className="flex items-center justify-between p-3 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">{t.type}</span>
                  <div className="flex gap-3">
                    <span className={`flex items-center gap-1 ${t.watermark ? 'text-emerald-600' : 'text-slate-300'}`}>
                      {t.watermark ? <CheckCircle2 size={11}/> : <XCircle size={11}/>} Watermark
                    </span>
                    <span className={`flex items-center gap-1 ${t.expiry ? 'text-emerald-600' : 'text-slate-300'}`}>
                      {t.expiry ? <CheckCircle2 size={11}/> : <XCircle size={11}/>} Expiry
                    </span>
                    <span className={`flex items-center gap-1 ${t.forwardBlock ? 'text-emerald-600' : 'text-slate-300'}`}>
                      {t.forwardBlock ? <CheckCircle2 size={11}/> : <XCircle size={11}/>} Block forward
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Schedule compose modal */}
      <Modal open={showCompose} onClose={() => setShowCompose(false)} title="Schedule a message" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={() => setShowCompose(false)}>Cancel</button><button className="btn-primary btn-sm">Schedule</button></>}>
        <div className="space-y-4">
          <div><label className="label">Subject</label><input className="input" placeholder="Message subject…"/></div>
          <div><label className="label">Target</label><select className="select"><option>North District</option><option>State HQ</option><option>All districts</option></select></div>
          <div><label className="label">Message body</label><textarea className="textarea" rows={4}/></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Send at</label><input className="input" type="datetime-local"/></div>
            <div><label className="label">Time zone</label><select className="select"><option>IST (UTC+5:30)</option></select></div>
          </div>
          <Alert type="warning">Scheduled sends can be cancelled at any time before dispatch begins. Once dispatching starts, halt stops remaining not-yet-dispatched messages within 30 seconds.</Alert>
        </div>
      </Modal>

      {/* Confirm recall/cancel */}
      <Confirm
        open={!!confirmRecall}
        onClose={() => setConfirmRecall(null)}
        onConfirm={() => setConfirmRecall(null)}
        title={confirmRecall?.isRecall ? 'Halt in-flight send?' : 'Cancel scheduled send?'}
        message={confirmRecall?.isRecall
          ? `This will halt ${confirmRecall?.subject}. Already-dispatched messages (${confirmRecall?.dispatched?.toLocaleString()}) cannot be recalled. Remaining ${(confirmRecall?.recipients - confirmRecall?.dispatched)?.toLocaleString()} will not be sent. This action is audited.`
          : `Cancel scheduled send "${confirmRecall?.subject}" to ${confirmRecall?.recipients?.toLocaleString()} recipients? No messages will be sent.`}
        danger
      />
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// NOTIFICATION SETTINGS — NTF-01, NTF-03, NTF-04
// ══════════════════════════════════════════════════════════════════════════
export function NotificationSettings({ accent = '#4f46e5' }) {
  const [quietFrom, setQuietFrom] = useState('22:00')
  const [quietTo, setQuietTo] = useState('07:00')
  const [showSaved, setShowSaved] = useState(false)

  const CHANNEL_CONFIG = [
    { id: 'push', label: 'Push notification', sub: 'In-app and mobile push', supported: true, default: true, suppressible: true },
    { id: 'sms', label: 'SMS fallback', sub: 'When push fails — cost shown in blast-radius preview (NTF-03)', supported: true, default: false, suppressible: true },
    { id: 'email', label: 'Email', sub: 'For non-urgent notifications', supported: true, default: true, suppressible: true },
    { id: 'whatsapp', label: 'WhatsApp', sub: 'Subject to platform policy approvals (NTF-01)', supported: false, default: false, suppressible: true },
  ]

  const NOTIF_CLASSES = [
    { id: 'emergency', label: 'Emergency messages', suppressible: false, quiet: false, desc: 'Cannot be suppressed. Bypass quiet hours (COM-13, NTF-02).' },
    { id: 'security', label: 'Security alerts', suppressible: false, quiet: false, desc: 'Cannot be suppressed. Bypass quiet hours (NTF-02, NTF-04).' },
    { id: 'task', label: 'Task assignments and overdue', suppressible: true, quiet: true, desc: 'Obeys quiet hours.' },
    { id: 'message', label: 'New messages', suppressible: true, quiet: true, desc: 'Obeys quiet hours.' },
    { id: 'issue', label: 'Citizen issue updates', suppressible: true, quiet: true, desc: 'Obeys quiet hours.' },
    { id: 'system', label: 'System and TPI approvals', suppressible: false, quiet: true, desc: 'Cannot be suppressed.' },
  ]

  const [enabled, setEnabled] = useState(() => {
    const s = {}
    CHANNEL_CONFIG.forEach(c => { s[c.id] = c.default })
    NOTIF_CLASSES.forEach(n => { s[`class_${n.id}`] = true })
    return s
  })

  const save = () => { setShowSaved(true); setTimeout(() => setShowSaved(false), 2500) }

  return (
    <div className="space-y-5 page">
      {showSaved && <Alert type="success">Notification preferences saved.</Alert>}
      <Alert type="warning">Emergency and security notifications cannot be suppressed or rescheduled. All other classes obey quiet hours (NTF-04).</Alert>

      {/* Channels — NTF-01 */}
      <div className="card p-5">
        <SectionHeader title="Delivery channels" icon={Bell} accent={accent}/>
        <div className="space-y-3">
          {CHANNEL_CONFIG.map(ch => (
            <div key={ch.id} className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${enabled[ch.id] ? 'border-primary-100 dark:border-primary-900/50 bg-primary-50/30 dark:bg-primary-950/10' : 'border-slate-100 dark:border-slate-800'}`}>
              <div className="flex items-center gap-3">
                <Bell size={15} className={enabled[ch.id] ? 'text-primary-600' : 'text-slate-300'}/>
                <div>
                  <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">{ch.label}</div>
                  <div className="text-[10px] text-slate-400">{ch.sub}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {!ch.supported && <span className="badge badge-neutral">Pending approval</span>}
                <button
                  onClick={() => ch.supported && ch.suppressible && setEnabled(e => ({ ...e, [ch.id]: !e[ch.id] }))}
                  className={`w-11 h-6 rounded-full transition-all ${enabled[ch.id] && ch.supported ? 'bg-primary-600' : 'bg-slate-200 dark:bg-slate-700'} ${!ch.suppressible || !ch.supported ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}>
                  <div className={`w-5 h-5 rounded-full bg-white mx-0.5 transition-transform ${enabled[ch.id] && ch.supported ? 'translate-x-5' : 'translate-x-0'}`}/>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quiet hours — NTF-04 */}
      <div className="card p-5">
        <SectionHeader title="Quiet hours" icon={BellOff} accent={accent}/>
        <Alert type="info" className="mb-4">Emergency and security notifications bypass quiet hours regardless of this setting (NTF-04).</Alert>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Quiet from</label><input className="input" type="time" value={quietFrom} onChange={e => setQuietFrom(e.target.value)}/></div>
          <div><label className="label">Quiet until</label><input className="input" type="time" value={quietTo} onChange={e => setQuietTo(e.target.value)}/></div>
        </div>
        <div className="mt-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800 text-xs text-slate-500">
          Quiet hours active: <strong>{quietFrom}</strong> → <strong>{quietTo}</strong> IST. Emergency and security notifications still arrive immediately.
        </div>
      </div>

      {/* Per-class toggles — NTF-02 */}
      <div className="card p-5">
        <SectionHeader title="Notification classes" icon={Filter} accent={accent}/>
        <div className="space-y-2">
          {NOTIF_CLASSES.map(n => (
            <div key={n.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
              <div>
                <div className="font-semibold text-slate-700 dark:text-slate-300">{n.label}</div>
                <div className="text-slate-400 mt-0.5">{n.desc}</div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {n.quiet && <span className="badge badge-neutral">Quiet hours apply</span>}
                {!n.suppressible
                  ? <span className="badge badge-danger flex items-center gap-1"><Lock size={9}/>Required</span>
                  : (
                    <button onClick={() => setEnabled(e => ({ ...e, [`class_${n.id}`]: !e[`class_${n.id}`] }))}
                      className={`w-10 h-5 rounded-full transition-all cursor-pointer ${enabled[`class_${n.id}`] ? 'bg-primary-600' : 'bg-slate-200 dark:bg-slate-700'}`}>
                      <div className={`w-4 h-4 rounded-full bg-white mx-0.5 transition-transform ${enabled[`class_${n.id}`] ? 'translate-x-5' : 'translate-x-0'}`}/>
                    </button>
                  )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <button onClick={save} className="btn-primary">Save preferences</button>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// i18n / LANGUAGE SETTINGS — LNG-02, LNG-03, LNG-05
// ══════════════════════════════════════════════════════════════════════════
export function LanguageSettings({ accent = '#4f46e5', onLangChange }) {
  const [lang, setLang] = useState('en')
  const [dateFormat, setDateFormat] = useState('DD MMM YYYY')
  const [numeral, setNumeral] = useState('latin')
  const [saved, setSaved] = useState(false)

  const LANGS = [
    { code: 'en', label: 'English', script: 'Latin', dir: 'ltr', quality: 'Primary' },
    { code: 'hi', label: 'हिन्दी (Hindi)', script: 'Devanagari', dir: 'ltr', quality: 'Primary' },
    { code: 'kn', label: 'ಕನ್ನಡ (Kannada)', script: 'Kannada', dir: 'ltr', quality: 'Primary' },
    { code: 'ta', label: 'தமிழ் (Tamil)', script: 'Tamil', dir: 'ltr', quality: 'Caution' },
    { code: 'te', label: 'తెలుగు (Telugu)', script: 'Telugu', dir: 'ltr', quality: 'Caution' },
  ]

  const SAMPLE_STRINGS = {
    en: { greeting: 'Good morning, Ravi Kumar', task: 'You have 3 tasks overdue', submit: 'Submit report' },
    hi: { greeting: 'सुप्रभात, रवि कुमार', task: 'आपके 3 कार्य अतिदेय हैं', submit: 'रिपोर्ट सबमिट करें' },
    kn: { greeting: 'ಶುಭೋದಯ, ರವಿ ಕುಮಾರ್', task: 'ನಿಮಗೆ 3 ಕಾರ್ಯಗಳು ಬಾಕಿ ಇವೆ', submit: 'ವರದಿ ಸಲ್ಲಿಸಿ' },
    ta: { greeting: 'காலை வணக்கம், ரவி குமார்', task: 'உங்களிடம் 3 பணிகள் தாமதமானது', submit: 'அறிக்கை சமர்பிக்கவும்' },
    te: { greeting: 'శుభోదయం, రవి కుమార్', task: 'మీకు 3 పనులు గడువు మించాయి', submit: 'నివేదిక సమర్పించండి' },
  }

  const save = () => { setSaved(true); onLangChange && onLangChange(lang); setTimeout(() => setSaved(false), 2000) }

  return (
    <div className="space-y-5 page">
      {saved && <Alert type="success">Language preferences saved. UI will update.</Alert>}
      <Alert type="info">All UI strings are externalised (LNG-02). Adding a new language is configuration-only — no code changes required (LNG-01). Indic script, numerals, and date formats adapt per locale (LNG-05).</Alert>

      <div className="card p-5">
        <SectionHeader title="Display language" icon={Globe} accent={accent}/>
        <div className="space-y-2">
          {LANGS.map(l => (
            <label key={l.code} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${lang === l.code ? 'border-primary-300 dark:border-primary-700 bg-primary-50 dark:bg-primary-950/20' : 'border-slate-100 dark:border-slate-800 hover:border-slate-200'}`}>
              <input type="radio" name="lang" value={l.code} checked={lang === l.code} onChange={() => setLang(l.code)} className="hidden"/>
              <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${lang === l.code ? 'border-primary-600' : 'border-slate-300'}`}>
                {lang === l.code && <div className="w-2 h-2 rounded-full bg-primary-600"/>}
              </div>
              <div className="flex-1">
                <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">{l.label}</div>
                <div className="text-[10px] text-slate-400">{l.script} · {l.dir === 'ltr' ? 'Left to right' : 'Right to left'}</div>
              </div>
              <span className={`badge ${l.quality === 'Primary' ? 'badge-success' : 'badge-warning'}`}>{l.quality}</span>
            </label>
          ))}
        </div>
        {LANGS.find(l => l.code === lang)?.quality === 'Caution' && (
          <Alert type="warning" className="mt-3">This language pair is below primary quality threshold. UI is labelled "machine-translated" where confidence is low (LNG-04).</Alert>
        )}
      </div>

      {/* Live preview — LNG-03 respond in user language */}
      <div className="card p-5">
        <SectionHeader title="Preview — UI in selected language" icon={Languages} accent={accent}/>
        <div className="space-y-2">
          {Object.entries(SAMPLE_STRINGS[lang] || SAMPLE_STRINGS.en).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800 text-sm">
              <span className="text-[10px] text-slate-400 font-mono w-20 flex-shrink-0">{k}</span>
              <span className="text-slate-800 dark:text-slate-200 font-medium">{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Locale settings — LNG-05 */}
      <div className="card p-5">
        <SectionHeader title="Locale settings" icon={Globe} accent={accent}/>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Date format</label>
            <select className="select" value={dateFormat} onChange={e => setDateFormat(e.target.value)}>
              <option value="DD MMM YYYY">15 Aug 2026 (default)</option>
              <option value="DD/MM/YYYY">15/08/2026</option>
              <option value="YYYY-MM-DD">2026-08-15 (ISO)</option>
            </select>
            <div className="text-[10px] text-slate-400 mt-1">Sample: {new Date().toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' })}</div>
          </div>
          <div>
            <label className="label">Numeral style</label>
            <select className="select" value={numeral} onChange={e => setNumeral(e.target.value)}>
              <option value="latin">Latin (0123456789)</option>
              <option value="devanagari">Devanagari (०१२३४५६७८९)</option>
              <option value="kannada">Kannada (೦೧೨೩೪೫೬೭೮೯)</option>
            </select>
          </div>
        </div>
      </div>

      <button onClick={save} className="btn-primary">Save language preferences</button>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// TPI ENHANCED — TPI-02 in-app MFA approval, TPI-03 break-glass + notifications
// ══════════════════════════════════════════════════════════════════════════
export function TPIApprovalFlow({ accent = '#dc2626' }) {
  const [step, setStep] = useState('list')
  const [selected, setSelected] = useState(null)
  const [mfaCode, setMfaCode] = useState('')
  const [mfaError, setMfaError] = useState('')
  const [approved, setApproved] = useState(false)
  const [showBreakglass, setShowBreakglass] = useState(false)

  const approveTpi = () => {
    if (mfaCode.length !== 6 || mfaCode === '000000') { setMfaError('Invalid code.'); return }
    setMfaError(''); setApproved(true); setStep('done')
  }

  const startApprove = (item) => { setSelected(item); setMfaCode(''); setMfaError(''); setApproved(false); setStep('mfa') }

  return (
    <div className="space-y-4 page">
      <Alert type="warning">Two-person approval requires a <strong>second, distinct human</strong> — not the requester and not an account they created — to approve in-app with MFA within the configured window (TPI-02). Break-glass use is immediately logged and both Compliance Officer and Security Admin are notified (TPI-03).</Alert>

      {step === 'list' && (
        <div className="space-y-3">
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <SectionHeader title="Pending TPI actions" icon={Shield} accent={accent}/>
              <button onClick={() => setShowBreakglass(true)} className="btn-xs btn-danger flex items-center gap-1.5"><Zap size={11}/>Break-glass</button>
            </div>
            <table className="tbl">
              <thead><tr><th>ID</th><th>Action</th><th>Requested by</th><th>Threshold</th><th>Expires</th><th>Status</th><th>Approver actions</th></tr></thead>
              <tbody>
                {TPI_QUEUE.map(t => (
                  <tr key={t.id}>
                    <td className="font-mono font-black text-rose-600 dark:text-rose-400">{t.id}</td>
                    <td className="font-semibold max-w-xs truncate">{t.action}</td>
                    <td className="text-slate-500">{t.requester}</td>
                    <td className="text-slate-400 text-[10px]">{t.threshold}</td>
                    <td className={`font-mono text-[10px] ${t.expires === 'Expired' ? 'text-rose-500 font-bold' : 'text-slate-400'}`}>{t.expires}</td>
                    <td><StatusBadge status={t.status}/></td>
                    <td>
                      {t.status === 'pending' && (
                        <div className="flex gap-1">
                          <button onClick={() => startApprove(t)} className="btn-xs btn-success">Approve with MFA</button>
                          <button className="btn-xs btn-danger">Reject</button>
                        </div>
                      )}
                      {t.status === 'approved' && <span className="text-[10px] text-emerald-600 font-semibold">Approved</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card p-4">
            <SectionHeader title="Approver identity check" icon={Shield} accent={accent}/>
            <div className="space-y-2 text-xs">
              <Alert type="info">You are Rahul Das (Security Admin). You can approve TPI requests as long as you are not the requester and did not create the requester's account.</Alert>
              {[['Your identity', 'Rahul Das · Security Admin · RD-IDN-004'],['MFA status','Authenticated via TOTP — 8 min ago'],['Approver eligibility','Eligible for all pending TPI items'],['Session integrity','Registered device · IP 192.168.1.10']].map(([k,v])=>(
                <div key={k} className="flex justify-between border-b border-slate-50 dark:border-slate-800/60 pb-2">
                  <span className="text-slate-400">{k}</span><span className="font-semibold text-slate-700 dark:text-slate-300">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {step === 'mfa' && selected && (
        <div className="card p-6 max-w-md mx-auto">
          <div className="text-sm font-black text-slate-900 dark:text-white mb-1">Approve TPI action</div>
          <div className="text-xs text-slate-400 mb-5">{selected.id} · {selected.action}</div>
          <Alert type="danger" className="mb-5">You are approving a privileged action: <strong>{selected.action}</strong> — threshold: {selected.threshold}. This action will be permanently attributed to your identity.</Alert>
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800 text-xs mb-5 space-y-1">
            <div className="flex justify-between"><span className="text-slate-400">Requester</span><span className="font-semibold">{selected.requester}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">You (approver)</span><span className="font-semibold text-emerald-600">Rahul Das — distinct identity ✓</span></div>
          </div>
          <label className="label">Enter your MFA code to approve</label>
          <div className="flex gap-2 mb-4">
            <input className="input font-mono text-center text-lg tracking-widest" maxLength={6} value={mfaCode} onChange={e => setMfaCode(e.target.value.replace(/\D/g,'').slice(0,6))} placeholder="6-digit code"/>
          </div>
          {mfaError && <Alert type="danger" className="mb-3">{mfaError}</Alert>}
          <div className="flex gap-3">
            <button onClick={() => setStep('list')} className="btn-secondary btn-sm flex-1">Cancel</button>
            <button onClick={approveTpi} disabled={mfaCode.length !== 6} className="btn-success btn-sm flex-1">Approve with MFA</button>
          </div>
        </div>
      )}

      {step === 'done' && (
        <div className="card p-8 text-center max-w-md mx-auto space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto"><CheckCircle2 size={28} className="text-emerald-500"/></div>
          <div className="font-black text-slate-900 dark:text-white">Action approved</div>
          <p className="text-sm text-slate-500">{selected?.action} approved with MFA. Permanently logged as: <strong>Rahul Das acting as second approver</strong>.</p>
          <Alert type="success">Compliance Officer and Security Admin notified. Audit record written (TPI-03).</Alert>
          <button onClick={() => setStep('list')} className="btn-secondary btn-sm">Back to queue</button>
        </div>
      )}

      {/* Break-glass modal — TPI-03 */}
      <Modal open={showBreakglass} onClose={() => setShowBreakglass(false)} title="Break-glass emergency bypass" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={() => setShowBreakglass(false)}>Cancel</button><button className="btn-danger btn-sm">Use break-glass (logged permanently)</button></>}>
        <div className="space-y-4">
          <Alert type="danger">Break-glass bypasses the two-person requirement for genuine emergencies only. Use is immediately and permanently logged, and both the Compliance Officer and Security Administrator are notified in real-time (TPI-03).</Alert>
          <div><label className="label">Emergency reason (mandatory)</label><textarea className="textarea" rows={3} placeholder="State the specific emergency justifying this bypass…"/></div>
          <div><label className="label">Action being bypassed</label><select className="select">{TPI_QUEUE.filter(t=>t.status==='pending').map(t=><option key={t.id}>{t.id}: {t.action}</option>)}</select></div>
          <Alert type="warning">A review board will audit this use within 24 hours. Unjustified break-glass use is a disciplinary matter.</Alert>
        </div>
      </Modal>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// OFFLINE SYNC ENHANCED — OFF-01 through OFF-07
// ══════════════════════════════════════════════════════════════════════════
export function OfflineSyncDashboard({ accent = '#0284c7' }) {
  const [online, setOnline] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const queue = [
    { id:'Q-001', type:'Field report', task:'TSK-001', size:'2.4 MB', status:'accepted', captured:'10:23', attestation:'attested-offline', retries: 0 },
    { id:'Q-002', type:'Photo evidence', task:'TSK-001', size:'1.1 MB', status:'uploading', captured:'10:24', attestation:'attested-offline', retries: 0 },
    { id:'Q-003', type:'Voice note', task:'TSK-003', size:'0.3 MB', status:'pending', captured:'10:12', attestation:'attested-offline', retries: 2 },
    { id:'Q-004', type:'Task completion', task:'TSK-002', size:'0.1 KB', status:'pending', captured:'10:31', attestation:'attested', retries: 0 },
    { id:'Q-005', type:'Photo evidence', task:'TSK-005', size:'3.2 MB', status:'failed', captured:'09:58', attestation:'attested-offline', retries: 5, failReason: 'Max size exceeded — compressing' },
  ]

  const totalPending = queue.filter(q => ['pending','uploading','failed'].includes(q.status)).length
  const totalAccepted = queue.filter(q => q.status === 'accepted').length
  const totalSize = '7.1 MB'

  const simulateSync = async () => {
    if (!online) return
    setSyncing(true)
    await new Promise(r => setTimeout(r, 2000))
    setSyncing(false)
  }

  return (
    <div className="space-y-4 page max-w-lg mx-auto">
      {/* Connection status */}
      <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-semibold ${online ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-100 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400' : 'bg-amber-50 dark:bg-amber-900/20 border-amber-100 dark:border-amber-800 text-amber-700 dark:text-amber-400'}`}>
        {online ? <Wifi size={16}/> : <WifiOff size={16}/>}
        <span>{online ? 'Online — sync active' : 'Offline — capturing locally'}</span>
        <button onClick={() => setOnline(v => !v)} className="ml-auto text-[10px] btn-xs btn-secondary">Simulate {online ? 'offline' : 'online'}</button>
      </div>

      {!online && (
        <Alert type="info">All captures are locally attested (device key + timestamp + hash) and will sync as <strong>attested-offline</strong> on reconnection (OFF-03). Local data is encrypted with keystore-protected key (OFF-02).</Alert>
      )}

      {/* Queue summary */}
      <div className="grid grid-cols-3 gap-2">
        <div className="card p-3 text-center"><div className="text-xl font-black text-amber-500">{totalPending}</div><div className="section-title mt-0.5">Pending</div></div>
        <div className="card p-3 text-center"><div className="text-xl font-black text-emerald-500">{totalAccepted}</div><div className="section-title mt-0.5">Accepted</div></div>
        <div className="card p-3 text-center"><div className="text-sm font-black text-slate-700 dark:text-slate-300 mt-0.5">{totalSize}</div><div className="section-title mt-0.5">Queued size</div></div>
      </div>

      {/* Sync queue — OFF-04: durable, ordered, resumable, idempotent */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <SectionHeader title="Sync queue" icon={Upload} accent={accent}/>
          <button onClick={simulateSync} disabled={!online || syncing} className="btn-sm btn-primary gap-1.5">
            {syncing ? <><RefreshCw size={12} className="animate-spin"/>Syncing…</> : <><Upload size={12}/>Sync now</>}
          </button>
        </div>
        <div className="p-3 space-y-2">
          {queue.map(q => (
            <div key={q.id} className={`p-3 rounded-xl border text-xs ${q.status === 'failed' ? 'border-rose-100 bg-rose-50 dark:bg-rose-900/10 dark:border-rose-900' : q.status === 'accepted' ? 'border-emerald-100 bg-emerald-50 dark:bg-emerald-900/10 dark:border-emerald-900' : 'border-slate-100 dark:border-slate-800'}`}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-black text-[10px] text-slate-400">{q.id}</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-300">{q.type}</span>
                  <span className="font-mono text-[10px] text-primary-600">{q.task}</span>
                </div>
                <StatusBadge status={q.status}/>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-slate-400">
                  <span>{q.size}</span>
                  <span>{q.captured}</span>
                  {q.retries > 0 && <span className="text-amber-500">{q.retries} retries</span>}
                </div>
                <span className="badge badge-neutral text-[9px]">{q.attestation}</span>
              </div>
              {q.failReason && <div className="mt-1.5 text-rose-500">{q.failReason}</div>}
              {/* Resumable progress for uploading — OFF-07 */}
              {q.status === 'uploading' && (
                <div className="mt-2 w-full h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                  <div className="h-1.5 rounded-full bg-primary-600 animate-pulse" style={{ width: '48%' }}/>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Device security — OFF-02 */}
      <div className="card p-4">
        <SectionHeader title="Device security" icon={Lock} accent={accent}/>
        <div className="space-y-2 text-xs">
          {[
            ['Encryption', 'AES-256 — Android Keystore protected'],
            ['Wipe trigger', 'Remote revocation or 10 failed unlocks'],
            ['Scope purge', 'On first contact after transfer (OFF-06)'],
            ['Local attestation', 'ECDSA device key + SHA-256 hash + GPS + timestamp'],
            ['Storage used', '18 MB / 200 MB limit'],
          ].map(([k,v]) => (
            <div key={k} className="flex justify-between border-b border-slate-50 dark:border-slate-800/60 pb-2">
              <span className="text-slate-400">{k}</span><span className="font-semibold text-slate-700 dark:text-slate-300">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// EVIDENCE INTEGRITY FULL FLOW — EVD-02 attestation chain
// ══════════════════════════════════════════════════════════════════════════
export function EvidenceIntegrityView({ accent = '#4f46e5' }) {
  const EVIDENCE = [
    { id:'EVD-A001', task:'TSK-001', type:'Photo', capturedAt:'10:23:14', method:'In-app camera', attestation:'attested', hash:'sha256:a4f8...', device:'Registered · Samsung Galaxy A54', location:'28.6139°N 77.2090°E', synced:true, note:'Captured in-app. Device key bound. GPS recorded. Chain complete.' },
    { id:'EVD-A002', task:'TSK-001', type:'Voice', capturedAt:'10:24:30', method:'In-app recorder', attestation:'attested-offline', hash:'sha256:b7c2...', device:'Registered · Samsung Galaxy A54', location:'28.6140°N 77.2091°E', synced:false, note:'Captured offline. Locally attested. Syncing when online (OFF-03).' },
    { id:'EVD-A003', task:'TSK-003', type:'Photo', capturedAt:'09:45:00', method:'Gallery upload', attestation:'unattested', hash:'sha256:c1d9...', device:'Registered', location:'Not recorded', synced:true, note:'Gallery upload — no device-key binding. Stored as lower-trust class (EVD-03).' },
    { id:'EVD-A004', task:'TSK-005', type:'Video', capturedAt:'08:12:05', method:'In-app camera', attestation:'flagged', hash:'sha256:d3e1...', device:'Registered', location:'28.7100°N 77.1000°E', synced:true, note:'Geo-timestamp inconsistency detected. Flagged for human review. Not auto-penalised (EVD-06).' },
  ]

  const [sel, setSel] = useState(null)
  const attColor = { attested:'#10b981', 'attested-offline':'#4f46e5', unattested:'#f59e0b', flagged:'#f43f5e' }

  return (
    <div className="space-y-4 page">
      <Alert type="info">Evidence integrity: the system flags, humans judge. A low attestation score never automatically penalises a worker (EVD-06). Every metric and AI summary discloses the evidence mix (EVD-07).</Alert>

      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Attested (in-app)" value="2" delta="Device key bound" deltaPos icon={CheckCircle2} accent="#10b981"/>
        <KpiCard label="Attested-offline" value="1" delta="Awaiting sync" deltaPos icon={Upload} accent="#4f46e5"/>
        <KpiCard label="Unattested" value="1" delta="Gallery upload" deltaPos={false} icon={AlertCircle} accent="#f59e0b"/>
        <KpiCard label="Flagged" value="1" delta="Human review needed" deltaPos={false} icon={AlertTriangle} accent="#f43f5e"/>
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
          <SectionHeader title="Evidence chain" icon={Shield} accent={accent}/>
        </div>
        <table className="tbl">
          <thead><tr><th>ID</th><th>Task</th><th>Type</th><th>Method</th><th>Attestation</th><th>Synced</th><th>Detail</th></tr></thead>
          <tbody>
            {EVIDENCE.map(e => (
              <tr key={e.id} className="cursor-pointer" onClick={() => setSel(e)}>
                <td className="font-mono font-black text-[10px]" style={{ color: attColor[e.attestation] }}>{e.id}</td>
                <td className="font-mono text-[10px] text-primary-600">{e.task}</td>
                <td><span className="badge badge-neutral">{e.type}</span></td>
                <td className="text-slate-500">{e.method}</td>
                <td><StatusBadge status={e.attestation}/></td>
                <td>{e.synced ? <CheckCircle2 size={14} className="text-emerald-500"/> : <Clock size={14} className="text-amber-500"/>}</td>
                <td><button className="btn-xs btn-outline" onClick={ev=>{ev.stopPropagation();setSel(e)}}>Inspect chain</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={!!sel} onClose={() => setSel(null)} title={`Evidence chain — ${sel?.id}`} size="md">
        {sel && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <StatusBadge status={sel.attestation}/>
              <span className="text-xs text-slate-500">{sel.note}</span>
            </div>
            <div className="space-y-2 text-xs">
              {[
                ['Captured at', sel.capturedAt],
                ['Capture method', sel.method],
                ['Device', sel.device],
                ['Location', sel.location],
                ['Content hash', sel.hash],
                ['Synced', sel.synced ? 'Yes — hash verified on server' : 'Pending — locally attested (OFF-03)'],
              ].map(([k,v]) => (
                <div key={k} className="flex justify-between border-b border-slate-50 dark:border-slate-800/60 pb-2">
                  <span className="text-slate-400">{k}</span>
                  <span className="font-mono font-semibold text-slate-700 dark:text-slate-300 text-right max-w-52 truncate">{v}</span>
                </div>
              ))}
            </div>
            {sel.attestation === 'flagged' && (
              <Alert type="warning">This evidence has been flagged for a geo-timestamp inconsistency. It requires human review before being used in any official record. The worker is not penalised unless a human makes that determination (EVD-06).</Alert>
            )}
            {sel.attestation === 'unattested' && (
              <Alert type="info">Gallery uploads are accepted but stored as lower-trust class. No device-key binding exists. Full capture metadata is retained separately from the EXIF-stripped release copy (EVD-03, DOC-02).</Alert>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
