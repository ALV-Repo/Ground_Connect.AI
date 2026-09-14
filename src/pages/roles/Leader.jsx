import { ServiceDebtIndex, GeographicView, MessageAdvanced } from '../Supplements'
import { useState } from 'react'
import { ClipboardCheck, AlertTriangle, Users, Moon, Send, Eye, GitBranch, Building2,
  BarChart2, Link2, PlusCircle, Search, MessageSquare, Filter, Download, ChevronRight,
  Clock, Shield, Zap, CheckCircle2, XCircle, Calendar, TrendingUp, TrendingDown,
  UserCheck, MapPin, Layers, AlertCircle, Star, Activity, Target, PhoneCall,
  Briefcase, Home, ChevronDown, ChevronUp, Info } from 'lucide-react'
import { TASK_CHART, MSG_CHART, CITIZEN_CHART, EVIDENCE_PIE, ORG_TREE,
  TASKS, MESSAGES, CITIZEN_ISSUES, DELEGATIONS, MEMBERS } from '../../data'
import { KpiCard, SectionHeader, FilterPills, StatusBadge, MsgBadge,
  Modal, Alert, DateRangePicker, Avatar, Confirm, EmptyState } from '../../components/UI'
import AIModule from '../../components/AIModule'
import { TaskBarChart, MsgAreaChart, CitizenBarChart, EvidenceDonut, ChartLegend } from '../../components/Charts'
import OrgTree from '../../components/OrgTree'

// ── Vibrant colour palette ──────────────────────────────────────────────────
const C = {
  indigo:'#4f46e5', rose:'#f43f5e', emerald:'#10b981', amber:'#f59e0b',
  violet:'#7c3aed', cyan:'#0891b2', orange:'#ea580c', pink:'#ec4899',
}

// ── Gradient KPI card ───────────────────────────────────────────────────────
function GKpi({ label, value, sub, icon: Icon, grad, trend, trendUp }) {
  return (
    <div className="relative overflow-hidden rounded-2xl p-5 text-white" style={{background: grad}}>
      <div className="absolute -right-4 -top-4 w-24 h-24 rounded-full bg-white/10"/>
      <div className="absolute -right-2 -bottom-6 w-20 h-20 rounded-full bg-white/10"/>
      <div className="relative">
        <div className="flex items-center justify-between mb-3">
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            <Icon size={20} className="text-white"/>
          </div>
          {trend && (
            <div className={`flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-lg bg-white/20`}>
              {trendUp ? <TrendingUp size={11}/> : <TrendingDown size={11}/>}
              {trend}
            </div>
          )}
        </div>
        <div className="text-3xl font-black tracking-tight mb-0.5">{value}</div>
        <div className="text-sm font-semibold text-white/80">{label}</div>
        {sub && <div className="text-[11px] text-white/60 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

// ── Date range bar ──────────────────────────────────────────────────────────
function DateRangeBar({ from, to, onFrom, onTo, quick, setQuick }) {
  const QUICK = ['Today','This week','This month','Last 3 months','All time']
  return (
    <div className="flex items-center gap-3 p-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 flex-wrap shadow-sm mb-4">
      <Calendar size={15} className="text-indigo-500 flex-shrink-0"/>
      <span className="text-xs font-bold text-slate-500">Date range</span>
      <div className="flex gap-1 flex-wrap">
        {QUICK.map(q=>(
          <button key={q} onClick={()=>setQuick(q)}
            className={`px-3 py-1 rounded-lg text-[11px] font-bold transition-all ${quick===q
              ? 'bg-indigo-600 text-white shadow'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 hover:text-indigo-600'}`}>
            {q}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2 ml-auto">
        <span className="text-[11px] text-slate-400">Custom:</span>
        <input type="date" value={from} onChange={e=>onFrom(e.target.value)}
          className="text-[11px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400"/>
        <span className="text-slate-300">→</span>
        <input type="date" value={to} onChange={e=>onTo(e.target.value)}
          className="text-[11px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400"/>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// DASHBOARD — bright, vibrant, date-picker driven
// ══════════════════════════════════════════════════════════════════════════
function Dashboard({ accent }) {
  const [quick, setQuick] = useState('This week')
  const [dateFrom, setDateFrom] = useState('2026-08-01')
  const [dateTo, setDateTo] = useState('2026-08-10')
  const [range, setRange] = useState('All')
  const s = { '1M':1,'3M':3,'6M':6,'All':8 }[range]||8

  return (
    <div className="space-y-5 page">
      {/* Date range picker */}
      <DateRangeBar from={dateFrom} to={dateTo} onFrom={setDateFrom} onTo={setDateTo} quick={quick} setQuick={setQuick}/>

      {/* Vibrant KPI row */}
      <div className="grid grid-cols-4 gap-4">
        <GKpi label="Tasks completed" value="1,415" trend="+12%" trendUp icon={ClipboardCheck}
          grad="linear-gradient(135deg,#4f46e5,#7c3aed)" sub={`Period: ${quick}`}/>
        <GKpi label="Overdue tasks" value="74" trend="-8%" trendUp icon={AlertTriangle}
          grad="linear-gradient(135deg,#f43f5e,#f97316)" sub="Needs attention"/>
        <GKpi label="Active members" value="8,234" trend="+5%" trendUp icon={Users}
          grad="linear-gradient(135deg,#10b981,#0891b2)" sub="Across all districts"/>
        <GKpi label="Dark units" value="3" trend="-40%" trendUp icon={Moon}
          grad="linear-gradient(135deg,#f59e0b,#f43f5e)" sub="Silence detected"/>
      </div>

      {/* Alert strip */}
      <div className="flex gap-3">
        {[
          { c:'#f43f5e', bg:'#fff1f2', label:'2 issues escalated', icon:AlertTriangle },
          { c:'#f59e0b', bg:'#fffbeb', label:'1 orphaned node', icon:AlertCircle },
          { c:'#4f46e5', bg:'#eef2ff', label:'2 TPI approvals pending', icon:Shield },
          { c:'#10b981', bg:'#ecfdf5', label:'69% confirmed resolution', icon:CheckCircle2 },
        ].map(({c,bg,label,icon:Icon})=>(
          <div key={label} className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold flex-1 border" style={{background:bg,borderColor:c+'33',color:c}}>
            <Icon size={14}/>{label}
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-black text-slate-800 dark:text-white">Performance overview</h3>
        <FilterPills options={['1M','3M','6M','All']} active={range} onChange={setRange}/>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="card p-5">
          <SectionHeader title="Task performance" icon={ClipboardCheck} accent={C.indigo}/>
          <ChartLegend items={[[C.indigo,'Completed'],[C.rose,'Overdue'],[C.amber,'Blocked']]}/>
          <TaskBarChart data={TASK_CHART.slice(-s)}/>
        </div>
        <div className="card p-5">
          <SectionHeader title="Message delivery" icon={Send} accent={C.emerald}/>
          <ChartLegend items={[[C.indigo,'Sent'],[C.emerald,'Delivered'],['#8b5cf6','Read']]}/>
          <MsgAreaChart data={MSG_CHART.slice(-s)}/>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="card p-5 col-span-2">
          <SectionHeader title="Citizen issues by category" icon={Building2} accent={C.emerald}/>
          <ChartLegend items={[[C.indigo,'Open'],[C.emerald,'Resolved'],[C.rose,'Escalated']]}/>
          <CitizenBarChart data={CITIZEN_CHART}/>
        </div>
        <div className="card p-5">
          <SectionHeader title="Evidence integrity" icon={Eye} accent="#8b5cf6"/>
          <EvidenceDonut data={EVIDENCE_PIE}/>
          <div className="space-y-2 mt-3">
            {EVIDENCE_PIE.map(e=>(
              <div key={e.name} className="flex justify-between items-center text-xs">
                <span className="flex items-center gap-1.5 text-slate-500">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{background:e.color}}/>
                  {e.name}
                </span>
                <span className="font-black text-slate-700 dark:text-slate-300">{e.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent messages */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <SectionHeader title="Recent messages" icon={Send} accent={C.indigo}/>
          <span className="text-[10px] text-slate-400 font-mono">Showing {quick}</span>
        </div>
        <table className="tbl">
          <thead><tr><th>Type</th><th>Subject</th><th>From</th><th>Recipients</th><th>Time</th><th>Status</th></tr></thead>
          <tbody>
            {MESSAGES.map(m=>(
              <tr key={m.id}>
                <td><MsgBadge type={m.type}/></td>
                <td className="font-semibold text-slate-800 dark:text-slate-200">{m.subject}</td>
                <td className="text-slate-500">{m.from}</td>
                <td>{m.recipients.toLocaleString()}</td>
                <td className="text-slate-400">{m.time}</td>
                <td><StatusBadge status={m.status}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// HIERARCHY — layman-friendly with plain English explanations
// ══════════════════════════════════════════════════════════════════════════
const STATUS_EXPLAINER = {
  active: { label:'Working normally', color:'#10b981', bg:'#ecfdf5', icon:'✓', desc:'This office has a person in charge and is actively reporting.' },
  orphaned: { label:'No person in charge!', color:'#f43f5e', bg:'#fff1f2', icon:'!', desc:'Nobody is assigned to run this office right now. All incoming work is being sent up to the nearest office that has a leader.' },
  dark: { label:'Gone silent', color:'#f59e0b', bg:'#fffbeb', icon:'?', desc:'This office has stopped sending reports. We have not heard from them in 7+ days. This could mean they are busy, unreachable, or have a problem.' },
}

function NodeCard({ node, onSelect, selected }) {
  const s = STATUS_EXPLAINER[node.status] || STATUS_EXPLAINER.active
  const isSelected = selected?.id === node.id
  return (
    <button onClick={()=>onSelect(node)}
      className={`w-full text-left p-3.5 rounded-xl border-2 transition-all mb-2 ${isSelected ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30' : 'border-slate-100 dark:border-slate-800 hover:border-indigo-200 dark:hover:border-indigo-800 bg-white dark:bg-slate-900'}`}>
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 text-base font-black" style={{background:s.bg,color:s.color}}>
          {s.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold text-slate-900 dark:text-white truncate">{node.name}</span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-lg" style={{background:s.bg,color:s.color}}>{s.label}</span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            {node.responsible
              ? <span className="text-emerald-600 font-medium">👤 {node.responsible}</span>
              : <span className="text-rose-500 font-bold">⚠ No one in charge</span>}
            <span className="mx-2 text-slate-200 dark:text-slate-700">|</span>
            <span>{node.members} members</span>
            <span className="mx-2 text-slate-200 dark:text-slate-700">|</span>
            <span>{node.tasks} tasks</span>
            {node.issues > 0 && <><span className="mx-2 text-slate-200 dark:text-slate-700">|</span><span className="text-rose-500">{node.issues} issues</span></>}
          </div>
        </div>
      </div>
    </button>
  )
}

function HierarchyPage({ accent }) {
  const [sel, setSel] = useState(null)
  const [searchQ, setSearchQ] = useState('')
  const [expandHelp, setExpandHelp] = useState(false)

  // Flatten tree for search
  const flatten = (node, depth=0, result=[]) => {
    result.push({...node, depth})
    if (node.children) node.children.forEach(c=>flatten(c, depth+1, result))
    return result
  }
  const allNodes = flatten(ORG_TREE)
  const filtered = searchQ ? allNodes.filter(n=>n.name.toLowerCase().includes(searchQ.toLowerCase())||n.responsible?.toLowerCase().includes(searchQ.toLowerCase())) : null

  const s = sel ? (STATUS_EXPLAINER[sel.status]||STATUS_EXPLAINER.active) : null
  const LEVEL_NAMES = ['State HQ','District','Zone']

  return (
    <div className="space-y-4 page">

      {/* Plain-English explainer */}
      <div className="rounded-2xl border-2 border-indigo-100 dark:border-indigo-900 overflow-hidden">
        <button onClick={()=>setExpandHelp(h=>!h)}
          className="w-full flex items-center gap-3 px-5 py-4 bg-indigo-50 dark:bg-indigo-950/30 text-left">
          <div className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <Info size={16} className="text-white"/>
          </div>
          <div>
            <div className="text-sm font-black text-indigo-900 dark:text-indigo-200">How does this organisation tree work?</div>
            <div className="text-xs text-indigo-600 dark:text-indigo-400">Click to {expandHelp?'hide':'read'} a plain-English explanation</div>
          </div>
          {expandHelp ? <ChevronUp size={16} className="ml-auto text-indigo-500"/> : <ChevronDown size={16} className="ml-auto text-indigo-500"/>}
        </button>
        {expandHelp && (
          <div className="px-5 pb-5 pt-3 bg-indigo-50/50 dark:bg-indigo-950/20 grid grid-cols-3 gap-4">
            {[
              { icon:'🏛', title:'What is this?', body:'This shows your entire organisation as a tree — like a family tree, but for offices. The top is State HQ. Below that are Districts. Below Districts are Zones and Booths.' },
              { icon:'👤', title:'Person in charge', body:'Every office must have exactly one person responsible for it. If no one is assigned, the office is "orphaned" — all its work automatically gets sent to the nearest office above it that has a leader.' },
              { icon:'🔕', title:'Dark units', body:'If an office stops sending reports for 7+ days, it is marked as "gone silent". This is just a signal — not an accusation. It could mean connectivity issues, workload, or that something needs attention.' },
            ].map(({icon,title,body})=>(
              <div key={title} className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-indigo-100 dark:border-indigo-900">
                <div className="text-2xl mb-2">{icon}</div>
                <div className="text-xs font-black text-slate-800 dark:text-white mb-1">{title}</div>
                <div className="text-xs text-slate-500 leading-relaxed">{body}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex gap-3 flex-wrap">
        {Object.entries(STATUS_EXPLAINER).map(([key,{label,color,bg,icon}])=>(
          <div key={key} className="flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-bold" style={{background:bg,borderColor:color+'33',color}}>
            <span className="text-base">{icon === '✓' ? '✅' : icon === '!' ? '🚨' : '⚠️'}</span>
            {label}
          </div>
        ))}
      </div>

      <div className="grid gap-4" style={{gridTemplateColumns:'1fr 320px'}}>
        {/* Tree panel */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <SectionHeader title="Organisation tree" icon={GitBranch} accent={accent}/>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs text-slate-400">
              <Search size={12}/>
              <input value={searchQ} onChange={e=>setSearchQ(e.target.value)}
                className="bg-transparent outline-none w-32 text-slate-700 dark:text-slate-300"
                placeholder="Search office or person…"/>
            </div>
          </div>

          {/* Search results */}
          {searchQ && filtered && (
            <div className="mb-4 space-y-1">
              <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">{filtered.length} results</div>
              {filtered.map(n=><NodeCard key={n.id} node={n} onSelect={setSel} selected={sel}/>)}
            </div>
          )}

          {/* Full visual tree */}
          {!searchQ && (
            <div>
              {/* Root */}
              <div className="relative">
                <NodeCard node={ORG_TREE} onSelect={setSel} selected={sel}/>
                {/* Children */}
                <div className="ml-6 pl-4 border-l-2 border-slate-100 dark:border-slate-800">
                  {ORG_TREE.children.map(district=>(
                    <div key={district.id}>
                      <NodeCard node={district} onSelect={setSel} selected={sel}/>
                      {/* Zone children */}
                      {district.children.length > 0 && (
                        <div className="ml-6 pl-4 border-l-2 border-slate-100 dark:border-slate-800 mb-2">
                          {district.children.map(zone=>(
                            <NodeCard key={zone.id} node={zone} onSelect={setSel} selected={sel}/>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className="card p-5">
          {sel ? (
            <div className="space-y-4">
              {/* Status banner */}
              <div className="p-4 rounded-xl border-2 text-center" style={{background:s.bg,borderColor:s.color+'44'}}>
                <div className="text-3xl mb-2">{s.icon==='✓'?'✅':s.icon==='!'?'🚨':'⚠️'}</div>
                <div className="text-sm font-black" style={{color:s.color}}>{s.label}</div>
                <div className="text-xs text-slate-500 mt-1 leading-relaxed">{s.desc}</div>
              </div>

              <div>
                <div className="text-base font-black text-slate-900 dark:text-white">{sel.name}</div>
                <div className="text-xs text-slate-400 mt-0.5">{LEVEL_NAMES[sel.level] || 'Office'} level</div>
              </div>

              {/* Stats — plain language */}
              <div className="space-y-2">
                {[
                  { icon:'👤', label:'Person in charge', value:sel.responsible||'Nobody assigned yet', warn:!sel.responsible },
                  { icon:'👥', label:'Total members', value:`${sel.members} people in this office` },
                  { icon:'📋', label:'Active tasks', value:`${sel.tasks} tasks currently assigned` },
                  { icon:'🏠', label:'Citizen issues', value:sel.issues>0?`${sel.issues} open complaints`:'No open complaints', good:sel.issues===0 },
                ].map(({icon,label,value,warn,good})=>(
                  <div key={label} className={`flex items-start gap-3 p-3 rounded-xl ${warn?'bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-800':good?'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800':'bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800'}`}>
                    <span className="text-base flex-shrink-0">{icon}</span>
                    <div>
                      <div className="text-[10px] text-slate-400 mb-0.5">{label}</div>
                      <div className={`text-xs font-bold ${warn?'text-rose-600':good?'text-emerald-600':'text-slate-700 dark:text-slate-300'}`}>{value}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Contextual tips */}
              {sel.status==='orphaned' && (
                <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-900/20 border-2 border-rose-200 dark:border-rose-800">
                  <div className="text-xs font-black text-rose-700 dark:text-rose-400 mb-1">🚨 Action needed</div>
                  <p className="text-xs text-rose-600 dark:text-rose-400">This office has no leader. Until someone is assigned, all messages and tasks coming to this office are automatically forwarded to the office above it. Please assign a responsible person as soon as possible.</p>
                </div>
              )}
              {sel.status==='dark' && (
                <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-200 dark:border-amber-800">
                  <div className="text-xs font-black text-amber-700 dark:text-amber-400 mb-1">⚠️ No recent activity</div>
                  <p className="text-xs text-amber-600 dark:text-amber-400">This office has not sent any field reports in 7+ days. This doesn't mean something is wrong — but it is worth checking in. The AI Dark Radar can give you more details.</p>
                </div>
              )}
              {sel.status==='active' && (
                <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border-2 border-emerald-200 dark:border-emerald-800">
                  <div className="text-xs font-black text-emerald-700 dark:text-emerald-400 mb-1">✅ Healthy office</div>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400">This office has a person in charge and is actively reporting. Everything looks normal here.</p>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center gap-3 py-12">
              <div className="w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center">
                <GitBranch size={28} className="text-indigo-400"/>
              </div>
              <div className="text-sm font-bold text-slate-600 dark:text-slate-400">Select an office</div>
              <p className="text-xs text-slate-400 max-w-48">Click on any office in the tree to see its details, status, and who is in charge.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// MESSAGES PAGE
// ══════════════════════════════════════════════════════════════════════════
function MessagesPage({ accent }) {
  const [filter, setFilter] = useState('All')
  const [compose, setCompose] = useState(false)
  const [msgType, setMsgType] = useState('Announcement')
  const [target, setTarget] = useState('Entire organisation')
  const [showPreview, setShowPreview] = useState(false)
  const [selected, setSelected] = useState(null)
  const filtered = filter==='All' ? MESSAGES : MESSAGES.filter(m=>m.type===filter)
  const MSG_TYPES = ['Announcement','Instruction','Emergency','Information','Meeting','Document','Survey','Task-linked','Issue-linked']
  const TARGETS = ['Entire organisation','North District','South District','East District','Zone A','Zone B','Zone C','Zone D']
  const RESPONSE_MODES = ['None','Acknowledge only','Reply to parent','Reply up chain','Aggregated replies','Escalation']

  return (
    <div className="space-y-4 page">
      <div className="flex items-center justify-between">
        <FilterPills options={['All','Emergency','Instruction','Announcement','Survey','Information']} active={filter} onChange={setFilter}/>
        <button onClick={()=>setCompose(o=>!o)} className="btn-primary btn-sm"><PlusCircle size={13}/>Compose</button>
      </div>

      {compose && (
        <div className="card p-5 border-2 border-primary-200 dark:border-primary-800">
          <div className="text-sm font-bold text-slate-900 dark:text-white mb-4">New message</div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div><label className="label">Message type</label>
              <select className="select" value={msgType} onChange={e=>setMsgType(e.target.value)}>
                {MSG_TYPES.map(t=><option key={t}>{t}</option>)}
              </select>
            </div>
            <div><label className="label">Target</label>
              <select className="select" value={target} onChange={e=>setTarget(e.target.value)}>
                {TARGETS.map(t=><option key={t}>{t}</option>)}
              </select>
            </div>
            <div><label className="label">Response mode</label>
              <select className="select">{RESPONSE_MODES.map(m=><option key={m}>{m}</option>)}</select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div><label className="label">Forward allowed</label><select className="select"><option>No</option><option>Yes</option></select></div>
            <div><label className="label">Download allowed</label><select className="select"><option>No</option><option>Yes</option></select></div>
            <div><label className="label">Expiry</label><input className="input-sm" type="datetime-local"/></div>
          </div>
          <input className="input mb-3" placeholder="Subject…"/>
          <textarea className="textarea mb-3" rows={4} placeholder="Message body…"/>
          {msgType==='Emergency'&&<Alert type="danger" className="mb-3">Emergency messages bypass quiet hours, require acknowledgement from all recipients, and are separately audited.</Alert>}
          <div className="flex items-center justify-between">
            <p className="text-[10px] text-slate-400">Blast-radius preview required before sending to ≥500 recipients</p>
            <div className="flex gap-2">
              <button onClick={()=>setCompose(false)} className="btn-secondary btn-sm">Cancel</button>
              <button onClick={()=>setShowPreview(true)} className="btn-primary btn-sm"><Eye size={13}/>Preview blast radius</button>
            </div>
          </div>
        </div>
      )}

      <Modal open={showPreview} onClose={()=>setShowPreview(false)} title="Blast-radius preview" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowPreview(false)}>Cancel</button><button className="btn-primary btn-sm">Send message</button></>}>
        <div className="space-y-4">
          <Alert type="warning">This preview is computed by actually evaluating the targeting query — not an estimate.</Alert>
          <div className="grid grid-cols-2 gap-3">
            <KpiCard label="Total recipients" value="12,400" deltaPos icon={Users} accent="#4f46e5"/>
            <KpiCard label="Unreachable" value="23" deltaPos={false} icon={AlertTriangle} accent="#f43f5e" sub="Orphaned / suspended nodes"/>
          </div>
          <div className="space-y-2">
            {[['North District','4,200 recipients'],['South District','3,800 recipients'],['East District','4,400 recipients']].map(([n,c])=>(
              <div key={n} className="flex justify-between text-xs px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800">
                <span className="font-medium text-slate-700 dark:text-slate-300">{n}</span>
                <span className="text-slate-500">{c}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between text-xs p-3 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800">
            <span className="text-amber-700 dark:text-amber-400 font-semibold">Estimated SMS cost (fallback)</span>
            <span className="font-bold text-amber-700 dark:text-amber-400">₹ 1,240</span>
          </div>
          <Alert type="info">Sends above 10,000 recipients require two-person approval (TPI-01). A second approver will be notified.</Alert>
        </div>
      </Modal>

      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Type</th><th>Subject</th><th>From</th><th>Recipients</th><th>Time</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{filtered.map(m=>(
          <tr key={m.id} className="cursor-pointer" onClick={()=>setSelected(m)}>
            <td><MsgBadge type={m.type}/></td>
            <td className="font-semibold text-slate-800 dark:text-slate-200 max-w-xs truncate">{m.subject}</td>
            <td className="text-slate-500">{m.from}</td>
            <td>{m.recipients.toLocaleString()}</td>
            <td className="text-slate-400">{m.time}</td>
            <td><StatusBadge status={m.status}/></td>
            <td><button className="btn-xs btn-outline" onClick={e=>{e.stopPropagation();setSelected(m)}}>View</button></td>
          </tr>
        ))}</tbody>
        </table>
      </div>

      <Modal open={!!selected} onClose={()=>setSelected(null)} title={selected?.subject||''} size="md">
        {selected&&<div className="space-y-3">
          <div className="flex gap-2 flex-wrap"><MsgBadge type={selected.type}/><StatusBadge status={selected.status}/>{selected.ack&&<span className="badge badge-warning">Requires acknowledgement</span>}</div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div><span className="text-slate-400">From:</span> <span className="font-semibold">{selected.from}</span></div>
            <div><span className="text-slate-400">Recipients:</span> <span className="font-semibold">{selected.recipients.toLocaleString()}</span></div>
            <div><span className="text-slate-400">Sent:</span> <span className="font-semibold">{selected.time}</span></div>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-300">{selected.body}</div>
        </div>}
      </Modal>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// TASKS — rich create form with step-by-step UX
// ══════════════════════════════════════════════════════════════════════════
const PRIORITY_META = {
  High:   { color:'#f43f5e', bg:'#fff1f2', label:'🔴 High priority',   desc:'Needs immediate attention' },
  Medium: { color:'#f59e0b', bg:'#fffbeb', label:'🟡 Medium priority', desc:'Important but not urgent' },
  Low:    { color:'#10b981', bg:'#ecfdf5', label:'🟢 Low priority',    desc:'Can wait a few days' },
}
const EVIDENCE_META = {
  'Photo evidence':     { icon:'📷', desc:'Assignee must take a photo as proof of completion' },
  'Voice report':       { icon:'🎙', desc:'Assignee must record a voice note explaining what they did' },
  'Text report only':   { icon:'✍️', desc:'Assignee writes a short text update' },
  'None':               { icon:'✓', desc:'No evidence needed — just mark as done' },
}

function TasksPage({ accent }) {
  const [filter, setFilter] = useState('All')
  const [showCreate, setShowCreate] = useState(false)
  const [selected, setSelected] = useState(null)
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({
    title:'', desc:'', assignee:'Arjun Patel — Field Worker',
    node:'Zone A — Booth 12', priority:'High', due:'',
    escalation:'Escalate to me after 24h', evidence:'Photo evidence',
  })
  const set = (k,v) => setForm(f=>({...f,[k]:v}))
  const filtered = filter==='All' ? TASKS : TASKS.filter(t=>t.status===filter)

  const STEPS = ['What is the task?','Who does it?','How urgent is it?','Review & create']

  const openCreate = () => { setStep(1); setForm({title:'',desc:'',assignee:'Arjun Patel — Field Worker',node:'Zone A — Booth 12',priority:'High',due:'',escalation:'Escalate to me after 24h',evidence:'Photo evidence'}); setShowCreate(true) }

  return (
    <div className="space-y-4 page">
      <div className="flex items-center justify-between">
        <FilterPills options={['All','In Progress','Assigned','Blocked','Completed','Overdue']} active={filter} onChange={setFilter}/>
        <button onClick={openCreate} className="btn-primary btn-sm"><PlusCircle size={13}/>New task</button>
      </div>

      <div className="card overflow-hidden">
        <table className="tbl">
          <thead><tr><th>Task ID</th><th>Title</th><th>Assignee</th><th>Node</th><th>Due</th><th>Priority</th><th>Status</th><th>Evidence</th></tr></thead>
          <tbody>{filtered.map(t=>(
            <tr key={t.id} className="cursor-pointer" onClick={()=>setSelected(t)}>
              <td className="font-black text-primary-600 dark:text-primary-400 font-mono">{t.id}</td>
              <td className="font-semibold text-slate-800 dark:text-slate-200 max-w-xs truncate">{t.title}</td>
              <td><div className="flex items-center gap-2"><Avatar initials={t.assignee.split(' ').map(n=>n[0]).join('')} size="xs" color={accent}/>{t.assignee}</div></td>
              <td className="text-slate-400 text-[10px]">{t.node}</td>
              <td className={`font-semibold ${t.due==='Today'?'text-rose-600 dark:text-rose-400':t.due==='Tomorrow'?'text-amber-600':'text-slate-500'}`}>{t.due}</td>
              <td><StatusBadge status={t.priority}/></td>
              <td><StatusBadge status={t.status}/></td>
              <td><StatusBadge status={t.evidence}/></td>
            </tr>
          ))}</tbody>
        </table>
      </div>

      <Alert type="info">Evidence mix: <strong>72% attested</strong>, 20% unattested, 8% flagged. Flags are for human review — never automatic penalties.</Alert>

      {/* STEP-BY-STEP TASK CREATE MODAL */}
      <Modal open={showCreate} onClose={()=>setShowCreate(false)} title="Create new task" size="lg"
        footer={
          <div className="flex items-center justify-between w-full">
            <div className="flex gap-1">
              {STEPS.map((s,i)=>(
                <div key={s} className={`h-2 rounded-full transition-all ${i<step?'bg-indigo-600':'bg-slate-200 dark:bg-slate-700'} ${i===step-1?'w-8':'w-2'}`}/>
              ))}
            </div>
            <div className="flex gap-2">
              {step > 1 && <button onClick={()=>setStep(s=>s-1)} className="btn-secondary btn-sm">← Back</button>}
              {step < 4
                ? <button onClick={()=>setStep(s=>s+1)} disabled={step===1&&!form.title} className="btn-primary btn-sm">Next →</button>
                : <button onClick={()=>setShowCreate(false)} className="btn-primary btn-sm"><CheckCircle2 size={13}/>Create task</button>
              }
            </div>
          </div>
        }>

        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-6 pb-4 border-b border-slate-100 dark:border-slate-800">
          {STEPS.map((s,i)=>(
            <div key={s} className="flex items-center gap-2">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-black transition-all ${i<step-1?'bg-emerald-500 text-white':i===step-1?'bg-indigo-600 text-white':'bg-slate-100 dark:bg-slate-800 text-slate-400'}`}>
                {i<step-1?'✓':i+1}
              </div>
              <span className={`text-[11px] font-bold ${i===step-1?'text-indigo-600':'text-slate-400'}`}>{s}</span>
              {i<3 && <ChevronRight size={12} className="text-slate-300 mx-1"/>}
            </div>
          ))}
        </div>

        {/* Step 1: What */}
        {step===1 && (
          <div className="space-y-4">
            <div className="text-center mb-4">
              <div className="text-2xl mb-1">📋</div>
              <div className="text-base font-black text-slate-900 dark:text-white">What needs to be done?</div>
              <div className="text-xs text-slate-400">Give the task a clear name and explain what's expected</div>
            </div>
            <div>
              <label className="label">Task name <span className="text-rose-500">*</span></label>
              <input className="input" placeholder="e.g. Inspect water pipes in Zone A sector 3"
                value={form.title} onChange={e=>set('title',e.target.value)}/>
              <div className="text-[10px] text-slate-400 mt-1">Be specific — the field worker needs to know exactly what to do</div>
            </div>
            <div>
              <label className="label">Detailed instructions</label>
              <textarea className="textarea" rows={4}
                placeholder="e.g. Check all 12 pipe junctions marked on the attached map. Take a photo of each. Note any leaks, cracks, or blockages."
                value={form.desc} onChange={e=>set('desc',e.target.value)}/>
            </div>
            <div>
              <label className="label">What proof of completion is needed?</label>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(EVIDENCE_META).map(([key,{icon,desc}])=>(
                  <button key={key} onClick={()=>set('evidence',key)}
                    className={`p-3 rounded-xl border-2 text-left transition-all ${form.evidence===key?'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30':'border-slate-100 dark:border-slate-800 hover:border-indigo-200'}`}>
                    <div className="text-xl mb-1">{icon}</div>
                    <div className="text-xs font-bold text-slate-800 dark:text-slate-200">{key}</div>
                    <div className="text-[10px] text-slate-400">{desc}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Who */}
        {step===2 && (
          <div className="space-y-4">
            <div className="text-center mb-4">
              <div className="text-2xl mb-1">👤</div>
              <div className="text-base font-black text-slate-900 dark:text-white">Who should do this?</div>
              <div className="text-xs text-slate-400">You can only assign to people within your team</div>
            </div>
            <div>
              <label className="label">Assign to</label>
              <select className="select" value={form.assignee} onChange={e=>set('assignee',e.target.value)}>
                <option>Arjun Patel — Field Worker (Zone A)</option>
                <option>Sita Devi — Coordinator (North District)</option>
                <option>Venkat Rao — Field Worker (Zone C)</option>
                <option>Priya Das — Coordinator (Zone D)</option>
              </select>
            </div>
            <div>
              <label className="label">Which office (zone) is this for?</label>
              <select className="select" value={form.node} onChange={e=>set('node',e.target.value)}>
                <option>Zone A — Booth 12</option>
                <option>Zone B — Booth 19</option>
                <option>Zone C — Booth 31</option>
                <option>Zone D — Booth 44</option>
                <option>North District</option>
              </select>
              <div className="text-[10px] text-slate-400 mt-1">You can only assign to offices within your authorised area</div>
            </div>
            <div>
              <label className="label">If the task gets stuck, who should be notified?</label>
              <select className="select" value={form.escalation} onChange={e=>set('escalation',e.target.value)}>
                <option>Escalate to me after 24h</option>
                <option>Escalate to district leader after 48h</option>
                <option>Escalate to State HQ after 72h</option>
                <option>No escalation</option>
              </select>
            </div>
          </div>
        )}

        {/* Step 3: How urgent */}
        {step===3 && (
          <div className="space-y-4">
            <div className="text-center mb-4">
              <div className="text-2xl mb-1">⏰</div>
              <div className="text-base font-black text-slate-900 dark:text-white">How urgent is this?</div>
              <div className="text-xs text-slate-400">Set the priority and deadline so the assignee knows what to focus on</div>
            </div>
            <div>
              <label className="label">Priority level</label>
              <div className="grid grid-cols-3 gap-3">
                {Object.entries(PRIORITY_META).map(([key,{color,bg,label,desc}])=>(
                  <button key={key} onClick={()=>set('priority',key)}
                    className={`p-4 rounded-xl border-2 text-left transition-all ${form.priority===key?'border-current':'border-slate-100 dark:border-slate-800 hover:border-current/30'}`}
                    style={form.priority===key?{borderColor:color,background:bg}:{}}>
                    <div className="text-lg mb-1">{label.split(' ')[0]}</div>
                    <div className="text-xs font-bold text-slate-800 dark:text-slate-200">{label.slice(3)}</div>
                    <div className="text-[10px] text-slate-400">{desc}</div>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="label">Deadline</label>
              <input type="date" className="input" value={form.due} onChange={e=>set('due',e.target.value)}/>
              <div className="text-[10px] text-slate-400 mt-1">If the deadline passes without completion, the task is automatically marked Overdue and the escalation rule fires</div>
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {step===4 && (
          <div className="space-y-4">
            <div className="text-center mb-4">
              <div className="text-2xl mb-1">✅</div>
              <div className="text-base font-black text-slate-900 dark:text-white">Review before creating</div>
              <div className="text-xs text-slate-400">Make sure everything looks right</div>
            </div>
            <div className="space-y-2">
              {[
                ['📋 Task', form.title || '(not set)'],
                ['👤 Assigned to', form.assignee],
                ['📍 Office', form.node],
                ['🔴 Priority', form.priority],
                ['📅 Due', form.due || 'No deadline set'],
                ['📷 Proof needed', form.evidence],
                ['⏫ If stuck', form.escalation],
              ].map(([label, value])=>(
                <div key={label} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800 text-sm">
                  <span className="text-base w-6 flex-shrink-0">{label.split(' ')[0]}</span>
                  <span className="text-slate-400 text-xs w-24 flex-shrink-0">{label.slice(2)}</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-300">{value}</span>
                </div>
              ))}
            </div>
            {form.priority==='High' && <Alert type="danger">High-priority task — the assignee will be notified immediately.</Alert>}
          </div>
        )}
      </Modal>

      {/* Task detail modal */}
      <Modal open={!!selected} onClose={()=>setSelected(null)} title={selected?.id||''} size="md">
        {selected&&<div className="space-y-3">
          <div className="flex gap-2 flex-wrap"><StatusBadge status={selected.status}/><StatusBadge status={selected.priority}/><StatusBadge status={selected.evidence}/></div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white">{selected.title}</h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">{selected.desc}</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[['Assignee',selected.assignee],['Node',selected.node],['Due',selected.due],['Escalation',selected.escalation]].map(([k,v])=>(
              <div key={k} className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800"><span className="text-slate-400 block mb-0.5">{k}</span><span className="font-semibold text-slate-700 dark:text-slate-300">{v}</span></div>
            ))}
          </div>
          {selected.status==='Blocked'&&<Alert type="danger">This task is blocked. The assignee must provide a reason and notify the assigning level within 5 minutes.</Alert>}
        </div>}
      </Modal>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════
// OTHER PAGES (unchanged)
// ══════════════════════════════════════════════════════════════════════════
function CitizenPage({ accent }) {
  const [filter, setFilter] = useState('All')
  const [sel, setSel] = useState(null)
  const filtered = filter==='All' ? CITIZEN_ISSUES : CITIZEN_ISSUES.filter(c=>c.status===filter||c.priority===filter)
  return (
    <div className="space-y-4 page">
      <FilterPills options={['All','In Progress','Escalated','Assigned','Resolved-Confirmed','Disputed-Reopened']} active={filter} onChange={setFilter}/>
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Open issues" value="22" delta="3 new today" deltaPos={false} icon={Building2} accent={accent}/>
        <KpiCard label="Escalated" value="1" delta="Needs attention" deltaPos={false} icon={AlertTriangle} accent="#f43f5e"/>
        <KpiCard label="Resolved confirmed" value="1" delta="Citizen-verified" deltaPos icon={CheckCircle2} accent="#10b981"/>
        <KpiCard label="Disputed" value="1" delta="Reopened" deltaPos={false} icon={XCircle} accent="#f43f5e"/>
      </div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>ID</th><th>Title</th><th>Citizen</th><th>Category</th><th>Location</th><th>Corroborations</th><th>Status</th><th>Priority</th></tr></thead>
        <tbody>{filtered.map(c=>(
          <tr key={c.id} className="cursor-pointer" onClick={()=>setSel(c)}>
            <td className="font-black text-primary-600 dark:text-primary-400 font-mono">{c.id}</td>
            <td className="font-semibold text-slate-800 dark:text-slate-200 max-w-xs truncate">{c.title}</td>
            <td className="text-slate-500">{c.citizen}</td>
            <td><span className="badge badge-neutral">{c.category}</span></td>
            <td className="text-slate-400">{c.location}</td>
            <td><span className="font-bold text-primary-600">{c.corroborations}</span><span className="text-slate-400 text-[10px] ml-1">citizens</span></td>
            <td><StatusBadge status={c.status}/></td>
            <td><StatusBadge status={c.priority}/></td>
          </tr>
        ))}</tbody>
        </table>
      </div>
      <Modal open={!!sel} onClose={()=>setSel(null)} title={sel?.id||''} size="md">
        {sel&&<div className="space-y-3">
          <div className="flex gap-2"><StatusBadge status={sel.status}/><StatusBadge status={sel.priority}/></div>
          <h3 className="font-bold text-slate-900 dark:text-white">{sel.title}</h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">{sel.desc}</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[['Citizen',sel.citizen],['Phone',sel.phone],['Category',sel.category],['Location',sel.location],['Submitted',sel.submitted],['Corroborations',sel.corroborations+' distinct citizens']].map(([k,v])=>(
              <div key={k} className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800"><span className="text-slate-400 block">{k}</span><span className="font-semibold">{v}</span></div>
            ))}
          </div>
          {sel.resolution&&<div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800 text-xs text-emerald-700 dark:text-emerald-400"><CheckCircle2 size={13} className="inline mr-1.5"/>{sel.resolution}</div>}
          {sel.status==='Disputed-Reopened'&&<Alert type="danger">Citizen disputed the resolution. Issue has been reopened with a shorter SLA clock.</Alert>}
        </div>}
      </Modal>
    </div>
  )
}

function AnalyticsPage({ accent }) {
  const [range, setRange] = useState('All')
  const s = { '1M':1,'3M':3,'6M':6,'All':8 }[range]||8
  return (
    <div className="space-y-4 page">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-700 dark:text-slate-300">Ground intelligence analytics</h2>
        <div className="flex gap-2">
          <DateRangePicker onApply={()=>{}}/>
          <FilterPills options={['1M','3M','6M','All']} active={range} onChange={setRange}/>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="card p-5"><SectionHeader title="Task completion trend" icon={ClipboardCheck} accent={accent}/><ChartLegend items={[[C.indigo,'Completed'],[C.rose,'Overdue'],[C.amber,'Blocked']]}/><TaskBarChart data={TASK_CHART.slice(-s)} height={190}/></div>
        <div className="card p-5"><SectionHeader title="Message delivery" icon={Send} accent={C.emerald}/><ChartLegend items={[[C.indigo,'Sent'],[C.emerald,'Delivered'],['#8b5cf6','Read']]}/><MsgAreaChart data={MSG_CHART.slice(-s)} height={190}/></div>
      </div>
      <div className="card p-5">
        <SectionHeader title="Citizen issues by category" icon={Building2} accent={C.amber}/>
        <ChartLegend items={[[C.indigo,'Open'],[C.emerald,'Resolved'],[C.rose,'Escalated']]}/>
        <CitizenBarChart data={CITIZEN_CHART} height={220}/>
      </div>
      <div className="card p-5">
        <SectionHeader title="Dark unit radar" icon={Moon} accent={C.amber}/>
        <Alert type="warning" className="mb-4">3 units flagged for silence. Metrics measure engagement absence only — never loyalty.</Alert>
        <div className="space-y-3">
          {[{node:'Zone C — Booth 31',issue:'No field reports for 7 days',severity:'high'},{node:'South District',issue:'Leader account inactive for 5 days',severity:'high'},{node:'Zone B — Booth 19',issue:'Below baseline issue intake',severity:'medium'}].map((d,i)=>(
            <div key={i} className={`p-3.5 rounded-xl border ${d.severity==='high'?'border-rose-100 bg-rose-50 dark:bg-rose-900/10 dark:border-rose-900':'border-amber-100 bg-amber-50 dark:bg-amber-900/10 dark:border-amber-900'}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">{d.node}</span>
                <StatusBadge status={d.severity==='high'?'High':'Medium'}/>
              </div>
              <p className="text-xs text-slate-500">{d.issue}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function DelegationPage({ accent }) {
  const [showCreate, setShowCreate] = useState(false)
  const [confirmRevoke, setConfirmRevoke] = useState(null)
  return (
    <div className="space-y-4 page">
      <div className="flex items-center justify-between">
        <Alert type="info" className="flex-1 mr-4">Delegation is the only supported mechanism for temporary hand-over. No credential sharing is permitted.</Alert>
        <button onClick={()=>setShowCreate(true)} className="btn-primary btn-sm flex-shrink-0"><PlusCircle size={13}/>New delegation</button>
      </div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>ID</th><th>Delegator</th><th>Delegatee</th><th>Scope</th><th>From</th><th>To</th><th>Reason</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{DELEGATIONS.map(d=>(
          <tr key={d.id}>
            <td className="font-mono font-bold text-primary-600 dark:text-primary-400">{d.id}</td>
            <td className="font-semibold">{d.delegator}</td>
            <td>{d.delegatee}</td>
            <td className="text-slate-500 max-w-xs truncate">{d.scope}</td>
            <td className="text-slate-400">{d.from}</td>
            <td className="text-slate-400">{d.to}</td>
            <td className="text-slate-500">{d.reason}</td>
            <td><StatusBadge status={d.status}/></td>
            <td>{d.status==='active'&&<button onClick={()=>setConfirmRevoke(d)} className="btn-xs btn-danger">Revoke</button>}</td>
          </tr>
        ))}</tbody>
        </table>
      </div>
      <Alert type="warning">All actions performed under delegation are permanently attributed as "X acting for Y" in all records and audit events.</Alert>
      <Modal open={showCreate} onClose={()=>setShowCreate(false)} title="Create delegation" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowCreate(false)}>Cancel</button><button className="btn-primary btn-sm">Create delegation</button></>}>
        <div className="space-y-4">
          <div><label className="label">Delegate to</label><select className="select"><option>Sita Devi — Coordinator</option><option>Kiran Rao — Leader</option><option>Anil Shah — Leader</option></select></div>
          <div><label className="label">Scope (subset of your authority)</label><select className="select"><option>North District tasks and messaging</option><option>Zone A field reports only</option><option>Full district authority</option></select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">From</label><input className="input" type="date"/></div>
            <div><label className="label">To (auto-expires)</label><input className="input" type="date"/></div>
          </div>
          <div><label className="label">Reason</label><input className="input" placeholder="Annual leave / Training / etc."/></div>
          <Alert type="warning">Re-delegation beyond depth 1 is rejected. The delegatee cannot delegate further.</Alert>
        </div>
      </Modal>
      <Confirm open={!!confirmRevoke} onClose={()=>setConfirmRevoke(null)} onConfirm={()=>setConfirmRevoke(null)} title="Revoke delegation" message={`Revoke delegation ${confirmRevoke?.id} from ${confirmRevoke?.delegatee}? Effect within 60 seconds.`} danger/>
    </div>
  )
}

export default function Leader({ page, accent, user }) {
  const pages = {
    0:<Dashboard accent={accent}/>,
    1:<HierarchyPage accent={accent}/>,
    2:<MessageAdvanced accent={accent}/>,
    3:<TasksPage accent={accent}/>,
    4:<CitizenPage accent={accent}/>,
    5:<AnalyticsPage accent={accent}/>,
    6:<DelegationPage accent={accent}/>,
    7:<AIModule user={user}/>,
    8:<GeographicView accent={accent}/>,
    9:<ServiceDebtIndex accent={accent}/>,
  }
  return pages[page] || <Dashboard accent={accent}/>
}
