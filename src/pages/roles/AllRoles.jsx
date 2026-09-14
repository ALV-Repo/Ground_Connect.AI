import AIModule from '../../components/AIModule'
import { NotificationSettings, LanguageSettings, TPIApprovalFlow, OfflineSyncDashboard, EvidenceIntegrityView, ServiceDebtIndex } from '../Supplements'
import { useState, useCallback, useMemo } from 'react'
import { ClipboardCheck, AlertTriangle, Users, Moon, Send, Eye, GitBranch, Building2, Shield, Lock, Key, Activity, Zap, FileText, Terminal, Globe, Server, CheckCircle2, XCircle, Camera, Mic, Upload, Search, Clock, PlusCircle, Download, RefreshCw, Smartphone, UserCheck, Settings, Filter, Map } from 'lucide-react'
import { TASKS, MESSAGES, CITIZEN_ISSUES, AUTH_LOG, CONSENT_LOG, PROHIBITED_ALERTS, MEMBERS, TPI_QUEUE, API_LOG, OFFLINE_QUEUE, TENANTS, ORG_TREE, TASK_CHART, MSG_CHART, UPTIME_CHART, EVIDENCE_PIE } from '../../data'
import { useTheme } from '../../context/ThemeContext'
import { KpiCard, SectionHeader, FilterPills, StatusBadge, MsgBadge, Modal, Alert, Avatar, EmptyState, Confirm, DateRangePicker } from '../../components/UI'
import { TaskBarChart, MsgAreaChart, EvidenceDonut, LineMetricChart, ChartLegend } from '../../components/Charts'
import OrgTree from '../../components/OrgTree'

// ── Coordinator ───────────────────────────────────────────────────────────
function CoordTaskBoard({ accent }) {
  const [filter, setFilter] = useState('All')
  const [showCreate, setShowCreate] = useState(false)
  const filtered = filter === 'All' ? TASKS : TASKS.filter(t => t.status === filter)
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Tasks in subtree" value="6" delta="2 overdue" deltaPos={false} icon={ClipboardCheck} accent={accent}/>
        <KpiCard label="Team members" value="14" delta="All active" deltaPos icon={Users} accent="#10b981"/>
        <KpiCard label="Completion rate" value="78%" delta="↑ 5% this week" deltaPos icon={CheckCircle2} accent={accent}/>
        <KpiCard label="Evidence quality" value="72%" delta="Attested tasks" deltaPos icon={Eye} accent={accent}/>
      </div>
      <div className="flex items-center justify-between">
        <FilterPills options={['All','In Progress','Assigned','Blocked','Completed','Overdue']} active={filter} onChange={setFilter}/>
        <button onClick={()=>setShowCreate(true)} className="btn-primary btn-sm"><PlusCircle size={13}/>New task</button>
      </div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Task ID</th><th>Title</th><th>Assignee</th><th>Due</th><th>Priority</th><th>Status</th><th>Evidence</th><th>Actions</th></tr></thead>
        <tbody>{filtered.map(t=>(
          <tr key={t.id}>
            <td className="font-mono font-black text-amber-600 dark:text-amber-400">{t.id}</td>
            <td className="font-semibold text-slate-800 dark:text-slate-200 max-w-xs truncate">{t.title}</td>
            <td><div className="flex items-center gap-2"><Avatar initials={t.assignee.split(' ').map(n=>n[0]).join('')} size="xs" color={accent}/>{t.assignee}</div></td>
            <td className={`font-semibold ${t.due==='Today'?'text-rose-600':t.due==='Tomorrow'?'text-amber-600':'text-slate-500'}`}>{t.due}</td>
            <td><StatusBadge status={t.priority}/></td>
            <td><StatusBadge status={t.status}/></td>
            <td><StatusBadge status={t.evidence}/></td>
            <td><div className="flex gap-1"><button className="btn-xs btn-outline">View</button>{t.status==='Completed'&&<button className="btn-xs btn-success">Accept</button>}</div></td>
          </tr>
        ))}</tbody>
        </table>
      </div>
      <Modal open={showCreate} onClose={()=>setShowCreate(false)} title="Create task" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowCreate(false)}>Cancel</button><button className="btn-primary btn-sm">Create task</button></>}>
        <div className="space-y-4">
          <Alert type="warning">Task delegation flows only downward within your subtree. Reassignment outside your subtree is technically impossible.</Alert>
          <div><label className="label">Title</label><input className="input" placeholder="Task title…"/></div>
          <div><label className="label">Assign to (subtree only)</label><select className="select"><option>Arjun Patel — Field Worker</option><option>Meena Sharma — Field Worker</option><option>Venkat Rao — Field Worker</option></select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Priority</label><select className="select"><option>High</option><option>Medium</option><option>Low</option></select></div>
            <div><label className="label">Due date</label><input className="input" type="date"/></div>
          </div>
          <div><label className="label">Description</label><textarea className="textarea" rows={3}/></div>
        </div>
      </Modal>
    </div>
  )
}

function CoordTeam({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-3 gap-3">
        <KpiCard label="Team size" value="14" delta="Subtree only" deltaPos icon={Users} accent={accent}/>
        <KpiCard label="Active now" value="9" delta="Online" deltaPos icon={Activity} accent="#10b981"/>
        <KpiCard label="MFA enabled" value="13/14" delta="1 missing" deltaPos={false} icon={Shield} accent="#f59e0b"/>
      </div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Member</th><th>Role</th><th>Node</th><th>Status</th><th>Last active</th><th>MFA</th><th>Open tasks</th></tr></thead>
        <tbody>{MEMBERS.filter(m=>m.role!=='leader'&&m.role!=='org_admin').map(m=>(
          <tr key={m.id}>
            <td><div className="flex items-center gap-2"><Avatar initials={m.name.split(' ').map(n=>n[0]).join('')} size="xs" color={accent}/><span className="font-semibold">{m.name}</span></div></td>
            <td><span className="text-[10px] font-bold" style={{color:accent}}>{m.role.replace('_',' ')}</span></td>
            <td className="text-slate-500">{m.node}</td>
            <td><StatusBadge status={m.status}/></td>
            <td className="text-slate-400">{m.lastActive}</td>
            <td><StatusBadge status={m.mfa==='enabled'?'active':'pending'}/></td>
            <td className="font-bold text-primary-600">{TASKS.filter(t=>t.assignee===m.name&&t.status!=='Completed').length}</td>
          </tr>
        ))}</tbody>
        </table>
      </div>
    </div>
  )
}

function CoordMessages({ accent }) {
  const [filter, setFilter] = useState('All')
  const filtered = filter==='All'?MESSAGES:MESSAGES.filter(m=>m.type===filter)
  return (
    <div className="space-y-4 page">
      <FilterPills options={['All','Emergency','Instruction','Announcement','Information']} active={filter} onChange={setFilter}/>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Type</th><th>Subject</th><th>From</th><th>Time</th><th>Status</th></tr></thead>
        <tbody>{filtered.map(m=><tr key={m.id}><td><MsgBadge type={m.type}/></td><td className="font-semibold">{m.subject}</td><td className="text-slate-500">{m.from}</td><td className="text-slate-400">{m.time}</td><td><StatusBadge status={m.status}/></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

function CoordCitizens({ accent }) {
  const [filter, setFilter] = useState('All')
  const filtered = filter==='All'?CITIZEN_ISSUES:CITIZEN_ISSUES.filter(c=>c.status===filter)
  return (
    <div className="space-y-4 page">
      <FilterPills options={['All','In Progress','Assigned','Escalated','Resolved-Confirmed']} active={filter} onChange={setFilter}/>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>ID</th><th>Title</th><th>Category</th><th>Location</th><th>Priority</th><th>Status</th></tr></thead>
        <tbody>{filtered.map(c=><tr key={c.id}><td className="font-mono font-black text-amber-600 dark:text-amber-400">{c.id}</td><td className="font-semibold max-w-xs truncate">{c.title}</td><td><span className="badge badge-neutral">{c.category}</span></td><td className="text-slate-400">{c.location}</td><td><StatusBadge status={c.priority}/></td><td><StatusBadge status={c.status}/></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

function CoordReports({ accent }) {
  const [showModal, setShowModal] = useState(false)
  return (
    <div className="space-y-4 page">
      <div className="flex justify-end"><button onClick={()=>setShowModal(true)} className="btn-primary btn-sm"><FileText size={13}/>Submit field report</button></div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Report ID</th><th>Task</th><th>Submitted by</th><th>Type</th><th>Evidence</th><th>Status</th></tr></thead>
        <tbody>{[{id:'RPT-001',task:'TSK-001',by:'Arjun Patel',type:'Photo',ev:'attested',status:'Verified'},{id:'RPT-002',task:'TSK-002',by:'Meena Sharma',type:'Text',ev:'none',status:'Pending review'},{id:'RPT-003',task:'TSK-004',by:'Sita Devi',type:'Voice',ev:'attested',status:'Verified'}].map(r=>(
          <tr key={r.id}><td className="font-mono font-black text-amber-600 dark:text-amber-400">{r.id}</td><td className="font-mono text-slate-500">{r.task}</td><td>{r.by}</td><td><span className="badge badge-neutral">{r.type}</span></td><td><StatusBadge status={r.ev}/></td><td><StatusBadge status={r.status==='Verified'?'active':'pending'}/></td></tr>
        ))}</tbody>
        </table>
      </div>
      <Modal open={showModal} onClose={()=>setShowModal(false)} title="Submit field report" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowModal(false)}>Cancel</button><button className="btn-success btn-sm">Submit report</button></>}>
        <div className="space-y-4">
          <div><label className="label">Related task</label><select className="select">{TASKS.map(t=><option key={t.id}>{t.id} — {t.title}</option>)}</select></div>
          <div><label className="label">Report text</label><textarea className="textarea" rows={4} placeholder="Describe your observations…"/></div>
          <div className="grid grid-cols-3 gap-3">
            {[{icon:Camera,label:'Capture photo'},{icon:Mic,label:'Voice note'},{icon:Upload,label:'Upload file'}].map(({icon:Icon,label})=>(
              <button key={label} className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-950/20 transition-all text-xs text-slate-500 cursor-pointer">
                <Icon size={20} className="text-slate-400"/>{label}
              </button>
            ))}
          </div>
          <Alert type="success">In-app capture receives device attestation automatically. Gallery uploads are stored as lower-trust class.</Alert>
        </div>
      </Modal>
    </div>
  )
}

export function Coordinator({ page, accent, user }) {
  const pages = { 0:<CoordTaskBoard accent={accent}/>, 1:<CoordTeam accent={accent}/>, 2:<CoordMessages accent={accent}/>, 3:<CoordCitizens accent={accent}/>, 4:<CoordReports accent={accent}/>, 5:<AIModule user={user}/>, 6:<EvidenceIntegrityView accent={accent}/> }
  return pages[page] || <CoordTaskBoard accent={accent}/>
}

// ── Field Worker ──────────────────────────────────────────────────────────
function FWTasks({ accent }) {
  const [showReport, setShowReport] = useState(false)
  const [selTask, setSelTask] = useState(null)
  const myTasks = TASKS.slice(0, 3)
  return (
    <div className="space-y-3 page max-w-lg mx-auto">
      <div className="grid grid-cols-3 gap-2">
        <div className="card p-3 text-center"><div className="text-2xl font-black" style={{color:accent}}>3</div><div className="section-title mt-0.5">My tasks</div></div>
        <div className="card p-3 text-center"><div className="text-2xl font-black text-amber-500">1</div><div className="section-title mt-0.5">Overdue</div></div>
        <div className="card p-3 text-center"><div className="text-2xl font-black text-emerald-500">4</div><div className="section-title mt-0.5">Submitted</div></div>
      </div>
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"/>Online — sync up to date · 0 items queued
      </div>
      {myTasks.map(t=>(
        <div key={t.id} className="card p-4">
          <div className="flex gap-2 mb-2"><StatusBadge status={t.status}/><StatusBadge status={t.priority}/></div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-1">{t.title}</h3>
          <p className="text-xs text-slate-500 mb-3">{t.desc}</p>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mb-3">
            <span className="flex items-center gap-1"><Clock size={10}/>Due: <strong className={t.due==='Today'?'text-rose-500 ml-0.5':'ml-0.5'}>{t.due}</strong></span>
            <span className="flex items-center gap-1"><Map size={10}/>{t.node}</span>
            <StatusBadge status={t.evidence} size="xs"/>
          </div>
          <div className="flex gap-2">
            <button onClick={()=>{setSelTask(t);setShowReport(true)}} className="btn-primary btn-sm flex-1"><Camera size={13}/>Capture evidence</button>
            <button className="btn-success btn-sm"><CheckCircle2 size={13}/></button>
            {t.status==='Blocked'&&<button className="btn-danger btn-sm"><AlertTriangle size={13}/></button>}
          </div>
        </div>
      ))}
      <Modal open={showReport} onClose={()=>setShowReport(false)} title={`Submit evidence — ${selTask?.id||''}`} size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowReport(false)}>Cancel</button><button className="btn-success btn-sm"><Upload size={13}/>Submit report</button></>}>
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-2">
            {[{icon:Camera,label:'Photo',sub:'In-app capture'},{icon:Mic,label:'Voice',sub:'Audio recording'},{icon:Upload,label:'Video',sub:'Screen record'}].map(({icon:Icon,label,sub})=>(
              <button key={label} className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-950/20 transition-all text-xs text-slate-500 cursor-pointer">
                <Icon size={22} className="text-slate-400"/><div className="font-semibold">{label}</div><div className="text-[10px] text-slate-400">{sub}</div>
              </button>
            ))}
          </div>
          <textarea className="textarea" rows={4} placeholder="Describe what you observed…"/>
          <div className="flex gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800 text-xs text-slate-500">
            <div><div className="font-semibold text-slate-700 dark:text-slate-300">Location</div><div>Captured automatically from device</div></div>
            <div><div className="font-semibold text-slate-700 dark:text-slate-300">Timestamp</div><div>{new Date().toLocaleTimeString()}</div></div>
          </div>
          <Alert type="success">In-app captures receive device attestation binding media hash, device key, timestamp, and coarse location.</Alert>
          <Alert type="warning">Gallery uploads are stored as lower-trust class and displayed with an unattested badge.</Alert>
        </div>
      </Modal>
    </div>
  )
}

function FWReport({ accent }) {
  const [showForm, setShowForm] = useState(false)
  return (
    <div className="space-y-3 page max-w-lg mx-auto">
      <button onClick={()=>setShowForm(true)} className="btn-primary w-full py-3"><PlusCircle size={15}/>Submit new field report</button>
      {[{id:'RPT-001',task:'TSK-004',title:'District report submission',submitted:'Aug 12',evidence:'attested'},{id:'RPT-002',task:'TSK-001',title:'Booth infrastructure audit',submitted:'Aug 10',evidence:'attested'}].map(r=>(
        <div key={r.id} className="card p-4">
          <div className="flex items-center justify-between mb-1"><span className="font-mono text-[10px] font-black text-primary-600">{r.task}</span><StatusBadge status={r.evidence}/></div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">{r.title}</h3>
          <p className="text-[10px] text-slate-400 mt-1">Submitted {r.submitted}</p>
        </div>
      ))}
      <Modal open={showForm} onClose={()=>setShowForm(false)} title="New field report" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowForm(false)}>Cancel</button><button className="btn-success btn-sm">Submit</button></>}>
        <div className="space-y-4">
          <div><label className="label">Related task</label><select className="select">{TASKS.map(t=><option key={t.id}>{t.id} — {t.title}</option>)}</select></div>
          <div><label className="label">Completion %</label><input className="input" type="range" min="0" max="100" defaultValue="70"/></div>
          <div><label className="label">Report text</label><textarea className="textarea" rows={4} placeholder="What did you observe?"/></div>
          <div className="grid grid-cols-3 gap-2">
            {[{icon:Camera,label:'Photo'},{icon:Mic,label:'Voice'},{icon:Upload,label:'Upload'}].map(({icon:Icon,label})=>(
              <button key={label} className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-dashed border-slate-200 dark:border-slate-700 hover:border-primary-400 transition-all text-xs text-slate-500 cursor-pointer"><Icon size={18} className="text-slate-400"/>{label}</button>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  )
}

function FWMessages({ accent }) {
  return (
    <div className="space-y-3 page max-w-lg mx-auto">
      {MESSAGES.map(m=>(
        <div key={m.id} className="card p-4">
          <div className="flex items-center gap-2 mb-1.5"><MsgBadge type={m.type}/><span className="text-[10px] text-slate-400">{m.time}</span></div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-1">{m.subject}</h3>
          <p className="text-xs text-slate-500">{m.body}</p>
          {m.ack&&<button className="btn-success btn-xs mt-3 w-full">Acknowledge</button>}
        </div>
      ))}
    </div>
  )
}

function FWOffline({ accent }) {
  return (
    <div className="space-y-3 page max-w-lg mx-auto">
      <Alert type="success">Online — device synced 2 minutes ago. All local data is encrypted.</Alert>
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800"><SectionHeader title="Sync queue" icon={Upload} accent={accent}/></div>
        <table className="tbl"><thead><tr><th>ID</th><th>Type</th><th>Task</th><th>Size</th><th>Captured</th><th>Status</th></tr></thead>
        <tbody>{OFFLINE_QUEUE.map(q=><tr key={q.id}><td className="font-mono text-[10px]">{q.id}</td><td>{q.type}</td><td className="font-mono text-[10px] text-primary-600">{q.task}</td><td className="text-slate-400">{q.size}</td><td className="text-slate-400">{q.captured}</td><td><StatusBadge status={q.status}/></td></tr>)}</tbody>
        </table>
      </div>
      <div className="card p-4">
        <SectionHeader title="Device info" icon={Smartphone} accent={accent}/>
        <div className="space-y-2 text-xs">
          {[['Device','Registered · Samsung Galaxy A54'],['OS','Android 13'],['App version','v1.4.2'],['Encryption','Keystore AES-256 active'],['Offline storage','Used 18 MB / 200 MB limit'],['Last sync','Today, 10:24 AM']].map(([k,v])=>(
            <div key={k} className="flex justify-between border-b border-slate-50 dark:border-slate-800/60 pb-2">
              <span className="text-slate-400">{k}</span><span className="font-semibold text-slate-700 dark:text-slate-300">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function FieldWorker({ page, accent, user }) {
  const pages = { 0:<FWTasks accent={accent}/>, 1:<FWReport accent={accent}/>, 2:<FWMessages accent={accent}/>, 3:<OfflineSyncDashboard accent={accent}/>, 4:<AIModule user={user}/> }
  return pages[page] || <FWTasks accent={accent}/>
}

// ── Citizen ───────────────────────────────────────────────────────────────
function CitizenSubmit({ accent }) {
  const [submitted, setSubmitted] = useState(false)
  const [selCat, setSelCat] = useState('')
  const CATS = ['Infrastructure','Utilities','Sanitation','Public Safety','Transport','Health','Education','Other']
  if (submitted) return (
    <div className="card p-8 text-center space-y-4 max-w-md mx-auto page">
      <div className="w-16 h-16 rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto text-3xl">✅</div>
      <div className="text-lg font-black text-slate-900 dark:text-white">Issue submitted!</div>
      <p className="text-sm text-slate-500">Your reference number is</p>
      <div className="font-mono text-3xl font-black text-emerald-600 dark:text-emerald-400">CIT-REF-7829</div>
      <p className="text-xs text-slate-400">Save this number + your OTP to track progress anytime. You will receive an OTP confirmation when a resolution is proposed.</p>
      <div className="flex gap-3">
        <button className="btn-success flex-1">Track this issue</button>
        <button className="btn-secondary flex-1" onClick={()=>setSubmitted(false)}>Submit another</button>
      </div>
    </div>
  )
  return (
    <div className="space-y-4 page max-w-lg mx-auto">
      <div className="card p-5 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/10 border-emerald-100 dark:border-emerald-900">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500 flex items-center justify-center text-white text-xl flex-shrink-0">🏠</div>
          <div><div className="font-black text-slate-900 dark:text-white text-base">Citizen Service Portal</div><div className="text-xs text-slate-500 mt-0.5">Report issues · Track progress · Confirm resolution</div></div>
        </div>
      </div>
      <div className="card p-5 space-y-4">
        <h2 className="font-black text-slate-900 dark:text-white">Report a local issue</h2>
        <div><label className="label">Category</label>
          <div className="grid grid-cols-4 gap-2">
            {CATS.map(c=><button key={c} onClick={()=>setSelCat(c)} className={`p-2 rounded-xl border text-[10px] font-semibold transition-all ${selCat===c?'border-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400':'border-slate-100 dark:border-slate-800 hover:border-slate-200 text-slate-600 dark:text-slate-400'}`}>{c}</button>)}
          </div>
        </div>
        <div><label className="label">Describe the issue</label><textarea className="textarea" rows={4} placeholder="Tell us what you observed — a voice recording alone is sufficient."/></div>
        <div className="grid grid-cols-2 gap-3">
          {[{icon:Camera,label:'Add photo'},{icon:Mic,label:'Voice recording'}].map(({icon:Icon,label})=>(
            <button key={label} className="flex items-center justify-center gap-2 p-3 rounded-xl border border-dashed border-slate-200 dark:border-slate-700 hover:border-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-all text-xs text-slate-500 cursor-pointer">
              <Icon size={16}/>{label}
            </button>
          ))}
        </div>
        <div className="flex items-start gap-2 px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 text-[10px] text-slate-400">
          <Shield size={11} className="mt-0.5 flex-shrink-0 text-emerald-500"/>
          <span>Your data is collected only for grievance resolution. No profiling. Consent recorded. DPDP v2.1 compliant.</span>
        </div>
        <button onClick={()=>setSubmitted(true)} className="btn-success w-full py-3 text-sm">Submit report</button>
      </div>
    </div>
  )
}

function CitizenTrack({ accent }) {
  const [ref, setRef] = useState('')
  const [tracked, setTracked] = useState(null)
  const [err, setErr] = useState('')
  const track = () => {
    if (!ref.trim()) { setErr('Enter a reference number.'); return }
    setErr('')
    setTracked({ status:'In Progress', category:'Infrastructure', submitted:'Aug 10', assigned:'Zone A Team', eta:'2–3 working days', updates:[{time:'Aug 10 09:00',msg:'Issue received and logged.'},{ time:'Aug 11 14:00',msg:'Assigned to Zone A maintenance team.'}] })
  }
  return (
    <div className="space-y-4 page max-w-lg mx-auto">
      <div className="card p-5 space-y-4">
        <h2 className="font-black text-slate-900 dark:text-white">Track your issue</h2>
        <div><label className="label">Reference number</label><input className="input" value={ref} onChange={e=>{setRef(e.target.value);setErr('')}} placeholder="CIT-REF-XXXX"/></div>
        <div><label className="label">Your OTP (sent to registered number)</label><input className="input" placeholder="6-digit code"/></div>
        {err&&<Alert type="danger">{err}</Alert>}
        <button onClick={track} className="btn-success w-full">Track status</button>
      </div>
      {tracked&&(
        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-2"><StatusBadge status={tracked.status}/><span className="text-xs text-slate-500">Your issue is being worked on</span></div>
          <div className="space-y-2">
            {[['Category',tracked.category],['Submitted',tracked.submitted],['Assigned to',tracked.assigned],['Estimated resolution',tracked.eta]].map(([k,v])=>(
              <div key={k} className="flex justify-between text-xs border-b border-slate-50 dark:border-slate-800/60 pb-2">
                <span className="text-slate-400">{k}</span><span className="font-bold text-slate-700 dark:text-slate-300">{v}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="section-title mb-2">Activity</div>
            {tracked.updates.map((u,i)=>(
              <div key={`ar-item-${i}`} className="flex gap-3 mb-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 flex-shrink-0"/><div><div className="text-[10px] text-slate-400">{u.time}</div><div className="text-xs text-slate-600 dark:text-slate-400">{u.msg}</div></div></div>
            ))}
          </div>
          <Alert type="info">When a resolution is proposed, you will receive an OTP confirmation request in your language. You can confirm or dispute it — you are never auto-closed.</Alert>
        </div>
      )}
    </div>
  )
}

function CitizenHistory({ accent }) {
  return (
    <div className="space-y-3 page max-w-lg mx-auto">
      {CITIZEN_ISSUES.slice(0,3).map(c=>(
        <div key={c.id} className="card p-4">
          <div className="flex items-center justify-between mb-1.5"><span className="font-mono text-[10px] font-black text-primary-600">{c.id}</span><StatusBadge status={c.status}/></div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-1">{c.title}</h3>
          <p className="text-[10px] text-slate-400">{c.category} · {c.location} · Submitted {c.submitted}</p>
          {c.resolution&&<div className="mt-2 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1"><CheckCircle2 size={11}/>{c.resolution}</div>}
          {c.status==='Resolved-Confirmed'&&(
            <div className="flex gap-2 mt-3">
              <button className="btn-success btn-xs flex-1">Confirm resolution</button>
              <button className="btn-danger btn-xs flex-1">Dispute</button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export function Citizen({ page, accent }) {
  const pages = { 0:<CitizenSubmit accent={accent}/>, 1:<CitizenTrack accent={accent}/>, 2:<CitizenHistory accent={accent}/> }
  return pages[page] || <CitizenSubmit accent={accent}/>
}

// ── Org Admin ─────────────────────────────────────────────────────────────
function OAOverview({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Total nodes" value="8" delta="3 levels deep" deltaPos icon={GitBranch} accent={accent}/>
        <KpiCard label="Active members" value="8,234" delta="↑ 5% this month" deltaPos icon={Users} accent="#10b981"/>
        <KpiCard label="Orphaned nodes" value="1" delta="Needs attention" deltaPos={false} icon={AlertTriangle} accent="#f43f5e"/>
        <KpiCard label="Pending TPI" value="2" delta="Awaiting approval" deltaPos={false} icon={Clock} accent="#f59e0b"/>
      </div>
      <div className="card p-5"><SectionHeader title="Task completion" icon={ClipboardCheck} accent={accent}/><ChartLegend items={[['#4f46e5','Completed'],['#f43f5e','Overdue'],['#f59e0b','Blocked']]}/><TaskBarChart data={TASK_CHART}/></div>
    </div>
  )
}

function OAHierarchy({ accent }) {
  const [sel, setSel] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  return (
    <div className="space-y-4 page">
      <div className="grid gap-4" style={{gridTemplateColumns:'1fr 300px'}}>
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4"><SectionHeader title="Hierarchy tree" icon={GitBranch} accent={accent}/>
            <button onClick={()=>setShowAdd(true)} className="btn-primary btn-sm"><PlusCircle size={13}/>Add node</button>
          </div>
          <OrgTree tree={ORG_TREE} selected={sel} onSelect={setSel} showActions/>
        </div>
        <div className="card p-5">
          {sel?(<>
            <div className="text-sm font-black mb-1 text-slate-900 dark:text-white">{sel.name}</div>
            <StatusBadge status={sel.status}/>
            <div className="space-y-3 mt-4">
              {[['Responsible',sel.responsible||'⚠ None'],['Members',sel.members],['Open tasks',sel.tasks],['Issues',sel.issues]].map(([k,v])=>(
                <div key={k} className="flex justify-between text-xs border-b border-slate-50 dark:border-slate-800/60 pb-2.5">
                  <span className="text-slate-400">{k}</span><span className={`font-bold ${k==='Responsible'&&!sel.responsible?'text-rose-500':''}`}>{v||'None'}</span>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-2 mt-4">
              <button className="btn-primary btn-sm w-full"><UserCheck size={13}/>Assign responsible person</button>
              <button onClick={()=>setShowEdit(true)} className="btn-outline btn-sm w-full"><Settings size={13}/>Edit node</button>
              {sel.status==='orphaned'&&<button className="btn-danger btn-sm w-full"><AlertTriangle size={13}/>Fix orphan</button>}
            </div>
          </>):<EmptyState icon={GitBranch} title="Select a node" desc="Click to inspect"/>}
        </div>
      </div>
      <Modal open={showAdd} onClose={()=>setShowAdd(false)} title="Add hierarchy node" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowAdd(false)}>Cancel</button><button className="btn-primary btn-sm">Create node</button></>}>
        <div className="space-y-4">
          <div><label className="label">Node name</label><input className="input" placeholder="e.g. Zone E — Booth 55"/></div>
          <div><label className="label">Parent node</label><select className="select"><option>North District</option><option>South District</option><option>East District</option><option>State HQ</option></select></div>
          <div><label className="label">Role at this node</label><select className="select"><option>Coordinator</option><option>Leader</option></select></div>
          <div><label className="label">Responsible person</label><select className="select"><option>— Assign later</option>{MEMBERS.map(m=><option key={m.id}>{m.name}</option>)}</select></div>
        </div>
      </Modal>
    </div>
  )
}

function OAMembers({ accent }) {
  const [filter, setFilter] = useState('All')
  const [showAdd, setShowAdd] = useState(false)
  const filtered = filter==='All'?MEMBERS:MEMBERS.filter(m=>m.status===filter||m.role.includes(filter.toLowerCase()))
  return (
    <div className="space-y-4 page">
      <div className="flex items-center justify-between">
        <FilterPills options={['All','active','suspended']} active={filter} onChange={setFilter}/>
        <div className="flex gap-2"><button className="btn-outline btn-sm"><Download size={13}/>Export</button><button onClick={()=>setShowAdd(true)} className="btn-primary btn-sm"><PlusCircle size={13}/>Add member</button></div>
      </div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Member</th><th>Role</th><th>Node</th><th>Mobile</th><th>Status</th><th>Last active</th><th>MFA</th><th>Actions</th></tr></thead>
        <tbody>{filtered.map(m=>(
          <tr key={m.id}>
            <td><div className="flex items-center gap-2"><Avatar initials={m.name.split(' ').map(n=>n[0]).join('')} size="xs" color={accent}/><span className="font-semibold">{m.name}</span></div></td>
            <td><span className="text-[10px] font-bold text-cyan-600">{m.role.replace(/_/g,' ')}</span></td>
            <td className="text-slate-500">{m.node}</td>
            <td className="font-mono text-[10px] text-slate-400">{m.mobile}</td>
            <td><StatusBadge status={m.status}/></td>
            <td className="text-slate-400">{m.lastActive}</td>
            <td><StatusBadge status={m.mfa==='enabled'?'active':'warning'}/></td>
            <td><div className="flex gap-1"><button className="btn-xs btn-outline">Edit</button><button className="btn-xs btn-secondary">{m.status==='active'?'Suspend':'Reactivate'}</button></div></td>
          </tr>
        ))}</tbody>
        </table>
      </div>
      <Modal open={showAdd} onClose={()=>setShowAdd(false)} title="Add member" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowAdd(false)}>Cancel</button><button className="btn-primary btn-sm">Create member</button></>}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Full name</label><input className="input"/></div>
            <div><label className="label">Mobile number</label><input className="input" placeholder="+91 98765 XXXXX"/></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Role</label><select className="select"><option>field_worker</option><option>coordinator</option><option>leader</option></select></div>
            <div><label className="label">Assign to node</label><select className="select"><option>Zone A</option><option>Zone B</option><option>North District</option></select></div>
          </div>
          <Alert type="info">Member will be sent an Invited status OTP to activate their account. MFA is mandatory for all coordinator and above roles.</Alert>
        </div>
      </Modal>
    </div>
  )
}

function OABulkImport({ accent }) {
  const [step, setStep] = useState('upload')
  const VALIDATION = [{row:1,name:'Vikram Das',mobile:'+91 98765 55555',role:'field_worker',node:'Zone A',status:'accepted',note:''},{row:2,name:'Anita Rao',mobile:'+91 98765 55556',role:'coordinator',node:'Zone B',status:'accepted',note:''},{row:3,name:'Raj Kumar',mobile:'+91 98765 55555',role:'field_worker',node:'Zone A',status:'rejected',note:'Duplicate mobile number'},{row:4,name:'',mobile:'+91 98765 55558',role:'unknown',node:'Zone X',status:'rejected',note:'Invalid role and unknown node'}]
  return (
    <div className="space-y-4 page">
      <Alert type="info">Bulk import accepts Excel (.xlsx) or CSV. A mandatory dry-run validation runs before any records are committed.</Alert>
      {step==='upload'&&(
        <div className="card p-8 text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center mx-auto"><Upload size={24} className="text-primary-600"/></div>
          <div><div className="font-bold text-slate-900 dark:text-white">Drop your file here</div><div className="text-sm text-slate-400 mt-1">Excel (.xlsx) or CSV — max 50MB</div></div>
          <button onClick={()=>setStep('validate')} className="btn-primary">Upload and validate</button>
          <div className="text-xs text-slate-400">Required columns: name, mobile, role, node · Optional: email, language</div>
        </div>
      )}
      {step==='validate'&&(
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <KpiCard label="Total rows" value="4" deltaPos icon={FileText} accent={accent}/>
            <KpiCard label="Accepted" value="2" deltaPos icon={CheckCircle2} accent="#10b981"/>
            <KpiCard label="Rejected" value="2" deltaPos={false} icon={XCircle} accent="#f43f5e"/>
          </div>
          <div className="card overflow-hidden">
            <table className="tbl"><thead><tr><th>Row</th><th>Name</th><th>Mobile</th><th>Role</th><th>Node</th><th>Result</th><th>Reason</th></tr></thead>
            <tbody>{VALIDATION.map(v=><tr key={v.row}><td className="font-mono">{v.row}</td><td className="font-medium">{v.name||'—'}</td><td className="font-mono text-[10px]">{v.mobile}</td><td>{v.role}</td><td>{v.node}</td><td><StatusBadge status={v.status==='accepted'?'active':'denied'}/></td><td className="text-rose-500 text-[10px]">{v.note}</td></tr>)}</tbody>
            </table>
          </div>
          <div className="flex gap-3">
            <button onClick={()=>setStep('upload')} className="btn-secondary btn-sm">Re-upload file</button>
            <button className="btn-primary btn-sm">Commit 2 accepted records</button>
          </div>
        </div>
      )}
    </div>
  )
}

function OARoles({ accent }) {
  return (
    <div className="space-y-4 page">
      <Alert type="warning">Role and permission grants at or above a configured level require two-person approval (TPI). The Organization Administrator cannot exceed their configured ceiling.</Alert>
      <div className="card p-5">
        <SectionHeader title="Role configuration" icon={Lock} accent={accent}/>
        <div className="space-y-3">
          {[{role:'leader',desc:'Directs within subtree, sends messages, views hierarchy',level:'State/District'},
            {role:'coordinator',desc:'Assigns tasks, verifies work, manages team within subtree',level:'Zone'},
            {role:'field_worker',desc:'Executes tasks, submits evidence, sees own data only',level:'Booth'},
          ].map(r=>(
            <div key={r.role} className="flex items-center justify-between p-3.5 rounded-xl border border-slate-100 dark:border-slate-800 hover:border-slate-200 dark:hover:border-slate-700 transition-colors">
              <div><div className="text-xs font-bold text-slate-800 dark:text-slate-200">{r.role.replace(/_/g,' ')}</div><div className="text-[10px] text-slate-400 mt-0.5">{r.desc}</div></div>
              <div className="flex items-center gap-3"><span className="badge badge-neutral">{r.level}</span><button aria-label="Action" className="btn-xs btn-outline"><Settings size=14 aria-hidden="true"/></button></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function OAAudit({ accent }) {
  return (
    <div className="space-y-4 page">
      <Alert type="info">Audit records are append-only and hash-chained. No role can delete audit records. Export is permission-controlled and itself audited.</Alert>
      <div className="flex items-center justify-between"><div/><button className="btn-outline btn-sm"><Download size={13}/>Export audit log</button></div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Time</th><th>User</th><th>Action</th><th>Device</th><th>Result</th><th>IP</th></tr></thead>
        <tbody>{AUTH_LOG.map(l=><tr key={l.id}><td className="font-mono text-slate-400">{l.time}</td><td className="font-medium">{l.user}</td><td>{l.action}</td><td><StatusBadge status={l.device==='Registered'?'active':'denied'}/></td><td><StatusBadge status={l.result}/></td><td className="font-mono text-[10px] text-slate-400">{l.ip}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

export function OrgAdmin({ page, accent, user }) {
  const pages = { 0:<OAOverview accent={accent}/>, 1:<OAHierarchy accent={accent}/>, 2:<OAMembers accent={accent}/>, 3:<OABulkImport accent={accent}/>, 4:<OARoles accent={accent}/>, 5:<OAAudit accent={accent}/>, 6:<NotificationSettings accent={accent}/>, 7:<LanguageSettings accent={accent}/>, 8:<AIModule user={user}/> }
  return pages[page] || <OAOverview accent={accent}/>
}

// ── Compliance ────────────────────────────────────────────────────────────
function CompOverview({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Consent records" value="4" delta="All verified" deltaPos icon={CheckCircle2} accent={accent}/>
        <KpiCard label="Erasure requests" value="1" delta="Pending action" deltaPos={false} icon={XCircle} accent="#f43f5e"/>
        <KpiCard label="Privacy notice" value="v2.1" delta="Current version" deltaPos icon={FileText} accent={accent}/>
        <KpiCard label="DPDP compliance" value="94%" delta="Target: 100%" deltaPos={false} icon={Shield} accent="#f59e0b"/>
      </div>
      <Alert type="warning">Compliance Officer cannot be removed or muted by the Org Admin acting alone. This role is protected.</Alert>
    </div>
  )
}

function CompConsent({ accent }) {
  const [sel, setSel] = useState(null)
  return (
    <div className="space-y-4 page">
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>ID</th><th>Citizen</th><th>Purpose</th><th>Notice version</th><th>Date</th><th>Mechanism</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{CONSENT_LOG.map(c=><tr key={c.id} className="cursor-pointer" onClick={()=>setSel(c)}><td className="font-mono font-black text-emerald-600 dark:text-emerald-400">{c.id}</td><td className="font-semibold">{c.citizen}</td><td>{c.purpose}</td><td><span className="badge badge-neutral">{c.version}</span></td><td className="text-slate-400">{c.date}</td><td className="text-slate-500">{c.mechanism}</td><td><StatusBadge status={c.status}/></td><td>{c.status==='erasure-requested'&&<button className="btn-xs btn-danger">Process erasure</button>}</td></tr>)}</tbody>
        </table>
      </div>
      <Modal open={!!sel} onClose={()=>setSel(null)} title={`Consent record ${sel?.id||''}`} size="md">
        {sel&&<div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 text-xs">
            {[['Citizen',sel.citizen],['Purpose',sel.purpose],['Notice version',sel.version],['Date',sel.date],['Mechanism',sel.mechanism],['Status',sel.status]].map(([k,v])=>(
              <div key={k} className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800"><span className="text-slate-400 block">{k}</span><span className="font-semibold">{v}</span></div>
            ))}
          </div>
          <div><div className="section-title mb-2">Retained data fields</div><div className="flex gap-2">{sel.retained?.map(f=><span key={f} className="badge badge-neutral">{f}</span>)}</div></div>
          {sel.status==='erasure-requested'&&<Alert type="danger">Erasure must cascade to all retrieval indices, AI caches, and derivative records. A certificate will be generated listing what was removed, retained, and why.</Alert>}
        </div>}
      </Modal>
    </div>
  )
}

function CompErasure({ accent }) {
  return (
    <div className="space-y-4 page">
      <Alert type="danger">1 verified erasure request pending. Process within the regulatory window.</Alert>
      <div className="card p-5">
        <SectionHeader title="Erasure request — CON-004" icon={XCircle} accent="#f43f5e"/>
        <div className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-3">
            {[['Citizen','Dev Singh'],['Request date','Aug 7, 2026'],['Lawful basis','Art. 12 DPDP 2023'],['Scope','All personal data']].map(([k,v])=>(
              <div key={k} className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800"><span className="text-slate-400 block">{k}</span><span className="font-semibold">{v}</span></div>
            ))}
          </div>
          <div className="section-title">Cascade plan</div>
          {['Primary records (name, phone, location)','Retrieval indices','AI conversation cache','Derived analytics (anonymised aggregates will be retained)'].map((i,idx)=>(
            <div key={idx} className="flex items-center gap-2 text-slate-600 dark:text-slate-400"><CheckCircle2 size={12} className="text-emerald-500 flex-shrink-0"/>{i}</div>
          ))}
          <div className="flex gap-3 mt-4"><button className="btn-danger btn-sm">Process erasure</button><button className="btn-secondary btn-sm">Request legal hold override</button></div>
        </div>
      </div>
    </div>
  )
}

function CompAlerts({ accent }) {
  return (
    <div className="space-y-4 page">
      <Alert type="warning">The prohibited-attribute firewall checks custom-field creation against a multilingual denylist. Disabling it requires two-person approval including the Compliance Officer.</Alert>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>ID</th><th>Field</th><th>Matched term</th><th>Blocked</th><th>Time</th><th>Reported</th><th>Actions</th></tr></thead>
        <tbody>{PROHIBITED_ALERTS.map(a=><tr key={a.id}><td className="font-mono font-black text-amber-600 dark:text-amber-400">{a.id}</td><td className="font-mono text-[10px]">{a.field}</td><td className="text-rose-600 font-bold">"{a.match}"</td><td><StatusBadge status={a.blocked?'active':'denied'}/></td><td className="text-slate-400">{a.time}</td><td><StatusBadge status={a.reported?'active':'pending'}/></td><td><div className="flex gap-1"><button className="btn-xs btn-outline">Review</button>{!a.reported&&<button className="btn-xs btn-danger">Report</button>}</div></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

function CompRetention({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="card p-5">
        <SectionHeader title="Retention schedules" icon={Clock} accent={accent}/>
        <div className="space-y-3">
          {[{cls:'Citizen PII',max:'2 years',rem:'18 months',auto:true},{cls:'Task evidence',max:'5 years',rem:'4y 2m',auto:true},{cls:'Auth event logs',max:'1 year',rem:'8 months',auto:true},{cls:'Message content',max:'6 months',rem:'3 months',auto:true},{cls:'AI conversation logs',max:'30 days',rem:'12 days',auto:true}].map(r=>(
            <div key={r.cls} className="flex items-center justify-between p-3 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
              <div><div className="font-semibold text-slate-800 dark:text-slate-200">{r.cls}</div><div className="text-slate-400 mt-0.5">Maximum retention: {r.max}</div></div>
              <div className="flex items-center gap-3"><div className="text-right"><div className="font-black text-emerald-600">{r.rem}</div><div className="text-slate-400 text-[10px]">remaining</div></div>{r.auto&&<span className="badge badge-success">Auto-enforced</span>}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function CompMode({ accent }) {
  const [active, setActive] = useState(false)
  return (
    <div className="space-y-4 page">
      <Alert type="warning">Activating a compliance mode profile changes feature availability, retention policies, mandatory disclaimers, and audit granularity tenant-wide in one audited action.</Alert>
      <div className="card p-5 space-y-4">
        <SectionHeader title="Compliance profiles" icon={Shield} accent={accent}/>
        {[{name:'MCC Profile',desc:'Model Code of Conduct — election period rules. Restricts outreach, adds mandatory disclaimers.',active:false},{name:'DPDP Full',desc:'Full DPDP 2023 compliance mode with maximum consent and erasure enforcement.',active:true},{name:'Audit-intensive',desc:'Maximum audit granularity for investigation periods.',active:false}].map(p=>(
          <div key={p.name} className={`p-4 rounded-xl border-2 transition-all ${p.active?'border-emerald-400 bg-emerald-50 dark:bg-emerald-900/10':'border-slate-100 dark:border-slate-800'}`}>
            <div className="flex items-center justify-between mb-1"><span className="text-sm font-bold text-slate-800 dark:text-slate-200">{p.name}</span><StatusBadge status={p.active?'active':'neutral'}/></div>
            <p className="text-xs text-slate-500 mb-3">{p.desc}</p>
            <div className="flex gap-2">{p.active?<button className="btn-danger btn-xs">Deactivate (requires TPI)</button>:<button className="btn-success btn-xs">Activate (requires TPI)</button>}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Compliance({ page, accent }) {
  const pages = { 0:<CompOverview accent={accent}/>, 1:<CompConsent accent={accent}/>, 2:<CompErasure accent={accent}/>, 3:<CompAlerts accent={accent}/>, 4:<CompRetention accent={accent}/>, 5:<CompMode accent={accent}/>, 6:<EvidenceIntegrityView accent={accent}/> }
  return pages[page] || <CompOverview accent={accent}/>
}

// ── Security Admin ────────────────────────────────────────────────────────
function SecOverview({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Active sessions" value="1,284" delta="3% today" deltaPos icon={Activity} accent={accent}/>
        <KpiCard label="Auth denials" value="17" delta="42% vs yesterday" deltaPos={false} icon={XCircle} accent="#f43f5e"/>
        <KpiCard label="TPI pending" value="2" delta="Awaiting approver" deltaPos={false} icon={Clock} accent="#f59e0b"/>
        <KpiCard label="Suspicious devices" value="3" delta="New today" deltaPos={false} icon={Smartphone} accent="#f43f5e"/>
      </div>
      <Alert type="warning">Security Administrator can restrict sessions and devices but cannot read message content.</Alert>
    </div>
  )
}

function SecSessions({ accent }) {
  const [confirmRevoke, setConfirmRevoke] = useState(null)
  const SESSIONS = [{user:'Ravi Kumar',role:'Leader',device:'Registered',since:'09:12',ip:'192.168.1.10',mfa:'totp'},{user:'Sita Devi',role:'Coordinator',device:'Registered',since:'08:45',ip:'192.168.2.5',mfa:'sms'},{user:'Arjun Patel',role:'Field Worker',device:'Registered',since:'07:30',ip:'10.0.0.44',mfa:'otp'},{user:'Dev Patel',role:'Coordinator',device:'Registered',since:'06:58',ip:'10.0.0.51',mfa:'totp'}]
  return (
    <div className="space-y-4 page">
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>User</th><th>Role</th><th>Device</th><th>Session start</th><th>IP</th><th>MFA</th><th>Actions</th></tr></thead>
        <tbody>{SESSIONS.map((s,i)=><tr key={`ar-item-${i}`}><td><div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-emerald-500"/><span className="font-semibold">{s.user}</span></div></td><td className="text-slate-500">{s.role}</td><td><StatusBadge status="active"/></td><td className="text-slate-400">{s.since}</td><td className="font-mono text-[10px] text-slate-400">{s.ip}</td><td><span className="badge badge-neutral">{s.mfa}</span></td><td><button onClick={()=>setConfirmRevoke(s)} className="btn-xs btn-danger">Revoke</button></td></tr>)}</tbody>
        </table>
      </div>
      <Confirm open={!!confirmRevoke} onClose={()=>setConfirmRevoke(null)} onConfirm={()=>setConfirmRevoke(null)} title="Revoke session" message={`Revoke session for ${confirmRevoke?.user}? Effect within 60 seconds including purge of offline data on next contact.`} danger/>
    </div>
  )
}

function SecEvents({ accent }) {
  const [filter, setFilter] = useState('All')
  const filtered = filter==='All'?AUTH_LOG:AUTH_LOG.filter(l=>l.result===filter||l.action.toLowerCase().includes(filter.toLowerCase()))
  return (
    <div className="space-y-4 page">
      <div className="flex items-center justify-between">
        <FilterPills options={['All','success','denied','pending-tpi']} active={filter} onChange={setFilter}/>
        <button className="btn-outline btn-sm"><Download size={13}/>Export log</button>
      </div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Time</th><th>User</th><th>Action</th><th>Device</th><th>MFA</th><th>Result</th><th>IP</th></tr></thead>
        <tbody>{filtered.map(l=><tr key={l.id}><td className="font-mono text-slate-400">{l.time}</td><td className="font-medium">{l.user}</td><td>{l.action}</td><td><StatusBadge status={l.device==='Registered'?'active':'denied'}/></td><td><span className="badge badge-neutral">{l.mfa}</span></td><td><StatusBadge status={l.result}/></td><td className="font-mono text-[10px] text-slate-400">{l.ip}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

function SecTPI({ accent }) {
  const [confirmApprove, setConfirmApprove] = useState(null)
  return (
    <div className="space-y-4 page">
      <Alert type="warning">Two-person integrity requires a second distinct human approver (not the requester, not an account the requester created) with MFA within the configured window.</Alert>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>ID</th><th>Action</th><th>Requester</th><th>Threshold</th><th>Requested</th><th>Expires</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{TPI_QUEUE.map(t=><tr key={t.id}><td className="font-mono font-black text-rose-600 dark:text-rose-400">{t.id}</td><td className="font-semibold max-w-xs truncate">{t.action}</td><td>{t.requester}</td><td className="text-slate-500">{t.threshold}</td><td className="text-slate-400">{t.requested}</td><td className={t.expires==='Expired'?'text-rose-500 font-bold':'text-slate-400'}>{t.expires}</td><td><StatusBadge status={t.status}/></td><td>{t.status==='pending'&&<div className="flex gap-1"><button onClick={()=>setConfirmApprove(t)} className="btn-xs btn-success">Approve</button><button aria-label="Reject request" className="btn-xs btn-danger">Reject</button></div>}</td></tr>)}</tbody>
        </table>
      </div>
      <Confirm open={!!confirmApprove} onClose={()=>setConfirmApprove(null)} onConfirm={()=>setConfirmApprove(null)} title="Approve TPI action" message={`Approve "${confirmApprove?.action}"? This will be logged permanently with your identity and MFA verification.`}/>
    </div>
  )
}

function SecDevices({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>User</th><th>Device</th><th>Registered</th><th>Last seen</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{[{user:'Ravi Kumar',device:'Samsung Galaxy S24',reg:'Aug 1',last:'Now',status:'trusted'},{user:'Sita Devi',device:'Realme C55',reg:'Aug 3',last:'10m ago',status:'trusted'},{user:'Arjun Patel',device:'Redmi Note 13',reg:'Aug 5',last:'1h ago',status:'trusted'},{user:'Unknown',device:'HUAWEI P40',reg:'Unregistered',last:'09:21',status:'denied'}].map((d,i)=><tr key={`ar-item-${i}`}><td className="font-semibold">{d.user}</td><td className="text-slate-500">{d.device}</td><td className="text-slate-400">{d.reg}</td><td className="text-slate-400">{d.last}</td><td><StatusBadge status={d.status==='trusted'?'active':'denied'}/></td><td><button className="btn-xs btn-danger">Revoke</button></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

function SecAnomalies({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="card p-5">
        <SectionHeader title="Detected anomalies" icon={AlertTriangle} accent="#f43f5e"/>
        <div className="space-y-3">
          {[{type:'Login from unregistered device',user:'unknown@attempt.com',time:'09:21',severity:'high'},{type:'Repeated failed OTPs',user:'field.99@gc.in',time:'08:10',severity:'medium'},{type:'Access from unusual IP',user:'coord.zoneb@gc.in',time:'08:55',severity:'low'}].map((a,i)=>(
            <div key={`ar-item-${i}`} className={`p-3.5 rounded-xl border ${a.severity==='high'?'border-rose-100 bg-rose-50 dark:bg-rose-900/10 dark:border-rose-900':a.severity==='medium'?'border-amber-100 bg-amber-50 dark:bg-amber-900/10 dark:border-amber-900':'border-slate-100 dark:border-slate-800'}`}>
              <div className="flex items-center justify-between mb-1"><span className="text-xs font-bold text-slate-800 dark:text-slate-200">{a.type}</span><StatusBadge status={a.severity==='high'?'High':'Medium'}/></div>
              <p className="text-xs text-slate-500">{a.user} · {a.time}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function SecurityAdmin({ page, accent }) {
  const pages = { 0:<SecOverview accent={accent}/>, 1:<SecSessions accent={accent}/>, 2:<SecEvents accent={accent}/>, 3:<TPIApprovalFlow accent={accent}/>, 4:<SecDevices accent={accent}/>, 5:<SecAnomalies accent={accent}/> }
  return pages[page] || <SecOverview accent={accent}/>
}

// ── Platform Operator ─────────────────────────────────────────────────────
function POOverview({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Active tenants" value="3" delta="1 added this month" deltaPos icon={Building2} accent={accent}/>
        <KpiCard label="Platform uptime" value="99.9%" delta="SLA: 99.9%" deltaPos icon={Activity} accent="#10b981"/>
        <KpiCard label="Support elevations" value="2" delta="Active right now" deltaPos={false} icon={Shield} accent="#f43f5e"/>
        <KpiCard label="API latency p95" value="38ms" delta="Target ≤500ms" deltaPos icon={Zap} accent="#06b6d4"/>
      </div>
      <div className="card p-5">
        <SectionHeader title="Platform metrics" icon={Activity} accent={accent}/>
        <ChartLegend items={[['#7c3aed','Uptime %'],['#06b6d4','Latency ms']]}/>
        <LineMetricChart data={UPTIME_CHART} lines={[{key:'uptime',name:'Uptime %',color:'#7c3aed'},{key:'latency',name:'Latency ms',color:'#06b6d4'}]} height={200}/>
      </div>
      <Alert type="info">Platform Operator has no standing access to organizational content. Any access requires customer-approved time-boxed support elevation.</Alert>
    </div>
  )
}

function POTenants({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Tenant</th><th>Nodes</th><th>Users</th><th>Health</th><th>Plan</th><th>DB</th><th>Region</th><th>Last elevation</th><th>Actions</th></tr></thead>
        <tbody>{TENANTS.map(t=><tr key={t.id}><td className="font-bold">{t.name}</td><td>{t.nodes.toLocaleString()}</td><td>{t.users.toLocaleString()}</td><td><span className={`font-black text-xs ${t.health>99?'text-emerald-600':'t.health>97'?'text-amber-600':'text-rose-600'}`}>{t.health}%</span></td><td><span className="badge badge-primary">{t.plan}</span></td><td><span className="badge badge-neutral">{t.db}</span></td><td className="text-slate-400">{t.region}</td><td className="text-slate-400">{t.lastElevation}</td><td><button className="btn-xs btn-outline">Request elevation</button></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

function POElevation({ accent }) {
  const [showReq, setShowReq] = useState(false)
  return (
    <div className="space-y-4 page">
      <Alert type="warning">Support elevation requires a stated reason, explicit customer approval, and a time-box (default 4h, max 24h). All actions during elevation are audited into a log the customer can read at any time.</Alert>
      <div className="flex justify-end"><button onClick={()=>setShowReq(true)} className="btn-primary btn-sm"><PlusCircle size={13}/>Request elevation</button></div>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Tenant</th><th>Reason</th><th>Duration</th><th>Approved by</th><th>Started</th><th>Status</th></tr></thead>
        <tbody>{[{tenant:'State Org A',reason:'DB performance tuning',duration:'4h',approver:'Priya Menon',started:'09:21',status:'active'},{tenant:'NGO Fed B',reason:'Auth config update',duration:'2h',approver:'Ananya Roy',started:'Yesterday',status:'expired'}].map((e,i)=><tr key={`ar-item-${i}`}><td className="font-bold">{e.tenant}</td><td>{e.reason}</td><td>{e.duration}</td><td>{e.approver}</td><td className="text-slate-400">{e.started}</td><td><StatusBadge status={e.status}/></td></tr>)}</tbody>
        </table>
      </div>
      <Modal open={showReq} onClose={()=>setShowReq(false)} title="Request support elevation" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowReq(false)}>Cancel</button><button className="btn-primary btn-sm">Submit request</button></>}>
        <div className="space-y-4">
          <div><label className="label">Tenant</label><select className="select">{TENANTS.map(t=><option key={t.id}>{t.name}</option>)}</select></div>
          <div><label className="label">Stated reason</label><textarea className="textarea" rows={3} placeholder="Describe the issue requiring access…"/></div>
          <div><label className="label">Duration requested</label><select className="select"><option>2 hours</option><option>4 hours (default)</option><option>8 hours</option><option>24 hours (maximum)</option></select></div>
          <Alert type="danger">Elevation is not self-approvable. Customer admin must approve. Not extendable without a fresh approval.</Alert>
        </div>
      </Modal>
    </div>
  )
}

function POInfra({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-3 gap-3">
        {[{label:'Kubernetes pods',value:'48/50',deltaPos:true},{label:'Database connections',value:'1,240/2,000',deltaPos:true},{label:'Message queue depth',value:'23',deltaPos:true}].map(k=>(
          <div key={k.label} className="kpi card p-4"><div className="section-title">{k.label}</div><div className="text-2xl font-black mt-2 text-slate-900 dark:text-white">{k.value}</div></div>
        ))}
      </div>
      <div className="card p-5">
        <SectionHeader title="Infrastructure health" icon={Server} accent={accent}/>
        <div className="space-y-2">
          {[{service:'API Gateway',status:'healthy',latency:'38ms'},{service:'PostgreSQL Primary',status:'healthy',latency:'2ms'},{service:'Redis Cache',status:'healthy',latency:'0.5ms'},{service:'RabbitMQ',status:'healthy',latency:'1ms'},{service:'OpenSearch',status:'healthy',latency:'45ms'},{service:'AI Gateway',status:'healthy',latency:'120ms'}].map(s=>(
            <div key={s.service} className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
              <span className="font-semibold text-slate-700 dark:text-slate-300">{s.service}</span>
              <div className="flex items-center gap-3"><span className="text-slate-400">{s.latency}</span><StatusBadge status="active"/></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function POAudit({ accent }) {
  return (
    <div className="space-y-4 page">
      <Alert type="info">Platform-level audit log covers all elevation events, tenant config changes, and infrastructure operations.</Alert>
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Time</th><th>Operator</th><th>Action</th><th>Tenant</th><th>Result</th></tr></thead>
        <tbody>{[{t:'09:21',op:'vikram.nair',a:'Support elevation granted',tn:'State Org A',r:'success'},{t:'08:00',op:'vikram.nair',a:'Tenant config viewed',tn:'NGO Fed B',r:'success'},{t:'Aug 9',op:'vikram.nair',a:'AI provider config change',tn:'State Org A',r:'success'}].map((l,i)=><tr key={`ar-item-${i}`}><td className="font-mono text-slate-400">{l.t}</td><td className="font-medium">{l.op}</td><td>{l.a}</td><td>{l.tn}</td><td><StatusBadge status={l.r}/></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

export function PlatformOperator({ page, accent }) {
  const pages = { 0:<POOverview accent={accent}/>, 1:<POTenants accent={accent}/>, 2:<POElevation accent={accent}/>, 3:<POInfra accent={accent}/>, 4:<POAudit accent={accent}/> }
  return pages[page] || <POOverview accent={accent}/>
}

// ── Integration Client ────────────────────────────────────────────────────
function ICConsole({ accent }) {
  const [query, setQuery] = useState('GET /api/v1/members?node=zone_a&limit=20')
  const [res, setRes] = useState(null)
  const SAMPLE = `{\n  "data": [\n    { "id": 7, "name": "Arjun Patel", "role": "field_worker", "node": "Zone A", "status": "active" }\n  ],\n  "meta": { "total": 8, "page": 1, "scope": "members:read" }\n}`
  return (
    <div className="space-y-4 page">
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="API calls today" value="8,241" delta="↑ 12%" deltaPos icon={Terminal} accent={accent}/>
        <KpiCard label="Success rate" value="99.2%" delta="Target: 99%" deltaPos icon={CheckCircle2} accent="#10b981"/>
        <KpiCard label="Avg latency" value="52ms" delta="Target ≤500ms" deltaPos icon={Zap} accent="#06b6d4"/>
        <KpiCard label="Rate limit" value="91%" delta="Per-scope quota" deltaPos icon={Server} accent={accent}/>
      </div>
      <div className="card p-5">
        <SectionHeader title="API console" icon={Terminal} accent={accent}/>
        <div className="flex gap-2 mb-3">
          <select className="select w-24 flex-shrink-0"><option>GET</option><option>POST</option><option>PUT</option><option>DELETE</option></select>
          <input className="input flex-1 font-mono text-xs" value={query} onChange={e=>setQuery(e.target.value)}/>
          <button onClick={()=>setRes(SAMPLE)} className="btn-primary btn-sm flex-shrink-0">Send</button>
        </div>
        {res&&<div className="p-4 rounded-xl bg-slate-950 text-emerald-400 font-mono text-xs whitespace-pre overflow-auto max-h-48">{res}</div>}
        <Alert type="info" className="mt-3">All API requests are executed under your scoped credentials. Requests for data outside your permitted scope return 403 AI_ACCESS_DENIED.</Alert>
      </div>
    </div>
  )
}

function ICCreds({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Scope</th><th>Status</th><th>Expires</th><th>Actions</th></tr></thead>
        <tbody>{[{scope:'hierarchy:read',status:'active',exp:'Dec 2026'},{scope:'tasks:read',status:'active',exp:'Dec 2026'},{scope:'issues:write',status:'active',exp:'Dec 2026'},{scope:'messages:write',status:'denied',exp:'—'},{scope:'audit:read',status:'denied',exp:'—'}].map((s,i)=><tr key={`ar-item-${i}`}><td className="font-mono font-bold text-slate-700 dark:text-slate-300">{s.scope}</td><td><StatusBadge status={s.status==='active'?'active':'denied'}/></td><td className="text-slate-400">{s.exp}</td><td>{s.status==='active'&&<button className="btn-xs btn-danger">Revoke</button>}</td></tr>)}</tbody>
        </table>
      </div>
      <Alert type="warning">Credential rotation requires two-person approval. Rate limits are per-scope. No interactive session is permitted for Integration Client.</Alert>
    </div>
  )
}

function ICWebhooks({ accent }) {
  const [showAdd, setShowAdd] = useState(false)
  return (
    <div className="space-y-4 page">
      <div className="flex justify-end"><button onClick={()=>setShowAdd(true)} className="btn-primary btn-sm"><PlusCircle size={13}/>Add webhook</button></div>
      <div className="card p-5 space-y-3">
        {[{url:'https://api.partner.com/gc/webhook',events:['task.completed','issue.escalated'],status:'active'},{url:'https://api.partner.com/gc/alerts',events:['auth.denied','tpi.required'],status:'active'}].map((w,i)=>(
          <div key={`ar-item-${i}`} className="p-3.5 rounded-xl border border-slate-100 dark:border-slate-800">
            <div className="flex items-center justify-between mb-2"><span className="font-mono text-xs text-slate-700 dark:text-slate-300 truncate">{w.url}</span><StatusBadge status={w.status}/></div>
            <div className="flex gap-1.5 flex-wrap">{w.events.map(e=><span key={e} className="badge badge-primary text-[10px]">{e}</span>)}</div>
          </div>
        ))}
      </div>
      <Modal open={showAdd} onClose={()=>setShowAdd(false)} title="Add webhook" size="md"
        footer={<><button className="btn-secondary btn-sm" onClick={()=>setShowAdd(false)}>Cancel</button><button className="btn-primary btn-sm">Add webhook</button></>}>
        <div className="space-y-4">
          <div><label className="label">Endpoint URL (HTTPS)</label><input className="input font-mono" placeholder="https://…"/></div>
          <div><label className="label">Events to subscribe</label>
            <div className="grid grid-cols-2 gap-2">{['task.completed','task.overdue','issue.escalated','issue.resolved','auth.denied','tpi.required','message.sent','member.status_change'].map(e=><label key={e} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 cursor-pointer"><input type="checkbox" className="rounded"/>{e}</label>)}</div>
          </div>
          <Alert type="info">Webhooks are signed with HMAC-SHA256. Include replay-protection by validating the X-GC-Timestamp header.</Alert>
        </div>
      </Modal>
    </div>
  )
}

function ICRateLimits({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="card p-5">
        <SectionHeader title="Rate limits by scope" icon={Zap} accent={accent}/>
        <div className="space-y-3">
          {[{scope:'hierarchy:read',limit:'1000/hour',used:124,pct:12},{scope:'tasks:read',limit:'500/hour',used:89,pct:18},{scope:'issues:write',limit:'200/hour',used:43,pct:22},{scope:'members:read',limit:'300/hour',used:12,pct:4}].map(r=>(
            <div key={r.scope} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
              <div className="flex items-center justify-between mb-2"><span className="font-mono font-bold text-slate-700 dark:text-slate-300">{r.scope}</span><span className="text-slate-400">{r.used} / {r.limit}</span></div>
              <div className="w-full h-1.5 rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-1.5 rounded-full bg-primary-600" style={{width:`${r.pct}%`}}/></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ICLogs({ accent }) {
  return (
    <div className="space-y-4 page">
      <div className="card overflow-hidden">
        <table className="tbl"><thead><tr><th>Time</th><th>Endpoint</th><th>Method</th><th>Status</th><th>Latency</th><th>Scope</th></tr></thead>
        <tbody>{API_LOG.map((l,i)=><tr key={`ar-item-${i}`}><td className="font-mono text-slate-400">{l.time}</td><td className="font-mono text-[11px] truncate max-w-48">{l.endpoint}</td><td><span className={`badge ${l.method==='GET'?'badge-primary':l.method==='POST'?'badge-success':'badge-neutral'}`}>{l.method}</span></td><td><StatusBadge status={l.status<300?'active':l.status===403?'denied':'warning'}/></td><td className="font-mono text-slate-400">{l.latency}</td><td className="font-mono text-[10px] text-slate-400 max-w-xs truncate">{l.scope}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}

export function IntegrationClient({ page, accent }) {
  const pages = { 0:<ICConsole accent={accent}/>, 1:<ICCreds accent={accent}/>, 2:<ICWebhooks accent={accent}/>, 3:<ICRateLimits accent={accent}/>, 4:<ICLogs accent={accent}/> }
  return pages[page] || <ICConsole accent={accent}/>
}

// ── Default export for React.lazy compatibility ─────────────────────────────
const ROLE_MAP = {
  coordinator: Coordinator,
  field_worker: FieldWorker,
  citizen: Citizen,
  org_admin: OrgAdmin,
  compliance: Compliance,
  security_admin: SecurityAdmin,
  platform_operator: PlatformOperator,
  integration_client: IntegrationClient,
}

export default function AllRoles({ role, page, user }) {
  const { accent } = useTheme()
  const RoleComponent = ROLE_MAP[role]
  if (!RoleComponent) return null
  return <RoleComponent page={page} accent={accent} user={user}/>
}
