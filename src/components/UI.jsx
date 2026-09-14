import { useState, useRef, useEffect, forwardRef } from 'react'
import { X, CheckCircle2, XCircle, AlertTriangle, Info, Bell, Search, ChevronDown, ChevronRight, ChevronLeft } from 'lucide-react'
import { ROLE_META } from '../data'

// ── Status Badge ──────────────────────────────────────────────────────────
export function StatusBadge({ status, size = 'sm' }) {
  const map = {
    active:'success', success:'success', delivered:'success', read:'primary', completed:'success',
    Completed:'success', attested:'success', 'Resolved-Confirmed':'success', 'In Progress':'primary',
    Assigned:'primary', 'pending-tpi':'warning', pending:'warning', unattested:'warning',
    dark:'warning', Blocked:'danger', Overdue:'danger', denied:'danger', flagged:'danger',
    'Disputed-Reopened':'danger', Escalated:'danger', orphaned:'danger', 'erasure-requested':'warning',
    suspended:'warning', disabled:'neutral', none:'neutral', expired:'neutral', Low:'neutral',
    Medium:'warning', High:'danger', uploading:'primary', accepted:'success',
  }
  const cls = `badge-${map[status] || 'neutral'}`
  return <span className={`badge ${cls} ${size === 'xs' ? 'text-[10px] px-2 py-0' : ''}`}>{status}</span>
}

export function MsgBadge({ type }) {
  const colors = {
    Emergency:'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
    Instruction:'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
    Announcement:'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    Survey:'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
    Information:'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
    'Task-linked':'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    'Issue-linked':'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  }
  return <span className={`badge ${colors[type] || 'badge-neutral'}`}>{type}</span>
}

// ── Avatar ────────────────────────────────────────────────────────────────
export function Avatar({ initials, size = 'md', color = '#4f46e5' }) {
  const s = { xs:'w-6 h-6 text-[9px]', sm:'w-8 h-8 text-[10px]', md:'w-10 h-10 text-sm', lg:'w-12 h-12 text-base', xl:'w-16 h-16 text-xl' }
  return (
    <div className={`${s[size]} rounded-full flex items-center justify-center font-black text-white flex-shrink-0`} style={{ background: color }}>
      {initials}
    </div>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, size = 'md', footer }) {
  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose() }
    if (open) { document.addEventListener('keydown', fn); document.body.style.overflow = 'hidden' }
    return () => { document.removeEventListener('keydown', fn); document.body.style.overflow = '' }
  }, [open, onClose])
  if (!open) return null
  const sizes = { sm:'max-w-md', md:'max-w-lg', lg:'max-w-2xl', xl:'max-w-4xl', full:'max-w-6xl' }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm animate-fade-in" />
      <div className={`relative w-full ${sizes[size]} card shadow-float animate-slide-up max-h-[90vh] flex flex-col`} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex-shrink-0">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">{title}</h2>
          <button onClick={onClose} className="btn-ghost btn-icon"><X size={15} /></button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">{children}</div>
        {footer && <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 flex-shrink-0 flex items-center justify-end gap-3">{footer}</div>}
      </div>
    </div>
  )
}

// ── Toast ─────────────────────────────────────────────────────────────────
export function Toast({ message, type = 'success', onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 4000); return () => clearTimeout(t) }, [])
  const icons = { success:<CheckCircle2 size={16} className="text-emerald-500" />, error:<XCircle size={16} className="text-rose-500" />, warning:<AlertTriangle size={16} className="text-amber-500" />, info:<Info size={16} className="text-primary-500" /> }
  return (
    <div className="fixed bottom-6 right-6 z-[100] flex items-center gap-3 px-4 py-3 rounded-xl bg-white dark:bg-slate-800 shadow-float border border-slate-100 dark:border-slate-700 animate-slide-up min-w-64 max-w-sm">
      <div className="flex-shrink-0">{icons[type]}</div>
      <span className="text-sm text-slate-700 dark:text-slate-300 flex-1">{message}</span>
      <button onClick={onClose} className="text-slate-300 hover:text-slate-500 flex-shrink-0"><X size={14} /></button>
    </div>
  )
}

// ── Section Header ────────────────────────────────────────────────────────
export function SectionHeader({ title, icon: Icon, accent, children }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-1 h-5 rounded-full flex-shrink-0" style={{ background: accent || '#4f46e5' }} />
        {Icon && <Icon size={15} className="flex-shrink-0" style={{ color: accent || '#4f46e5' }} />}
        <h3 className="section-title truncate">{title}</h3>
      </div>
      {children && <div className="flex items-center gap-2 flex-shrink-0">{children}</div>}
    </div>
  )
}

export function KpiCard({ label, value, delta, deltaPos = true, icon: Icon, accent = '#4f46e5', sub, onClick }) {
  return (
    <div onClick={onClick} className={`card p-4 flex flex-col gap-1 ${onClick ? 'cursor-pointer hover:shadow-card transition-shadow' : ''}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">{label}</span>
        {Icon && <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{background:accent+'18'}}><Icon size={14} style={{color:accent}}/></div>}
      </div>
      <div className="text-2xl font-black text-slate-900 dark:text-white leading-none">{value}</div>
      {delta && <div className={`text-[11px] font-semibold flex items-center gap-1 ${deltaPos ? 'text-emerald-600' : 'text-rose-500'}`}>{deltaPos ? '↑' : '↓'} {delta}</div>}
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export function FilterPills({ options, active, onChange }) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {options.map(o => <button key={o} onClick={() => onChange(o)} className={`pill ${active === o ? 'active' : ''}`}>{o}</button>)}
    </div>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, desc, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
        <Icon size={24} className="text-slate-400" />
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-600 dark:text-slate-400">{title}</p>
        {desc && <p className="text-xs text-slate-400 mt-1">{desc}</p>}
      </div>
      {action}
    </div>
  )
}

// ── Alert Banner ──────────────────────────────────────────────────────────
export function Alert({ type = 'info', children, onClose }) {
  const styles = {
    info:'bg-primary-50 border-primary-100 text-primary-800 dark:bg-primary-950/30 dark:border-primary-900 dark:text-primary-300',
    warning:'bg-amber-50 border-amber-100 text-amber-800 dark:bg-amber-950/30 dark:border-amber-900 dark:text-amber-300',
    danger:'bg-rose-50 border-rose-100 text-rose-800 dark:bg-rose-950/30 dark:border-rose-900 dark:text-rose-300',
    success:'bg-emerald-50 border-emerald-100 text-emerald-800 dark:bg-emerald-950/30 dark:border-emerald-900 dark:text-emerald-300',
  }
  const icons = { info:<Info size={14}/>, warning:<AlertTriangle size={14}/>, danger:<XCircle size={14}/>, success:<CheckCircle2 size={14}/> }
  return (
    <div className={`flex items-start gap-2.5 px-4 py-3 rounded-xl border text-xs font-medium ${styles[type]}`}>
      <span className="flex-shrink-0 mt-0.5">{icons[type]}</span>
      <span className="flex-1">{children}</span>
      {onClose && <button onClick={onClose} className="flex-shrink-0 opacity-60 hover:opacity-100"><X size={13}/></button>}
    </div>
  )
}

// ── Notification Bell ─────────────────────────────────────────────────────
export function NotifBell({ accent }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const fn = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', fn)
    return () => document.removeEventListener('mousedown', fn)
  }, [])
  const notes = [
    { text:'South District has an orphaned node', time:'2m ago', type:'danger' },
    { text:'Zone C flagged as dark unit', time:'15m ago', type:'warning' },
    { text:'Emergency message sent to 12,400', time:'1h ago', type:'info' },
    { text:'TPI approval pending for bulk transfer', time:'2h ago', type:'warning' },
  ]
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} className="btn-ghost btn-icon relative">
        <Bell size={16} />
        <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-rose-500 text-white text-[9px] font-black rounded-full flex items-center justify-center">4</span>
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-2 w-72 card shadow-float z-50 animate-slide-up overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Notifications</span>
            <span className="badge badge-danger">4 new</span>
          </div>
          {notes.map((n, i) => (
            <div key={i} className="flex gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer border-b border-slate-50 dark:border-slate-800/50 last:border-0">
              <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${n.type==='danger'?'bg-rose-500':n.type==='warning'?'bg-amber-400':'bg-primary-500'}`} />
              <div><p className="text-xs text-slate-700 dark:text-slate-300">{n.text}</p><p className="text-[10px] text-slate-400 mt-0.5">{n.time}</p></div>
            </div>
          ))}
          <div className="px-4 py-2 text-center"><button className="text-xs text-primary-600 font-semibold hover:underline">View all notifications</button></div>
        </div>
      )}
    </div>
  )
}

// ── Global Search ─────────────────────────────────────────────────────────
export function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const ref = useRef(null)
  useEffect(() => {
    const fn = e => { if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setOpen(true) } }
    document.addEventListener('keydown', fn)
    return () => document.removeEventListener('keydown', fn)
  }, [])
  const results = q.length > 1 ? [
    { type:'Task', label:`TSK-001 · Booth infrastructure audit`, sub:'Zone A · In Progress' },
    { type:'Member', label:`Arjun Patel`, sub:'Field Worker · Zone A' },
    { type:'Issue', label:`CIT-001 · Broken street light`, sub:'Zone A · High priority' },
    { type:'Message', label:`Mobilisation order`, sub:'State HQ · Emergency' },
  ].filter(r => r.label.toLowerCase().includes(q.toLowerCase())) : []
  return (
    <>
      <button onClick={() => setOpen(true)} className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-400 hover:border-primary-300 transition-colors">
        <Search size={13} /><span>Search…</span><kbd className="text-[9px] font-mono bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded px-1.5 py-0.5">⌘K</kbd>
      </button>
      {open && (
        <div className="fixed inset-0 z-[200] flex items-start justify-center pt-24 px-4" onClick={() => { setOpen(false); setQ('') }}>
          <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" />
          <div className="relative w-full max-w-xl card shadow-float animate-slide-up" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-800">
              <Search size={16} className="text-slate-400 flex-shrink-0" />
              <input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="Search tasks, members, issues, messages…" className="flex-1 bg-transparent outline-none text-sm text-slate-900 dark:text-white placeholder:text-slate-400" />
              <button onClick={() => { setOpen(false); setQ('') }}><X size={15} className="text-slate-400" /></button>
            </div>
            {results.length > 0 ? (
              <div className="py-2 max-h-72 overflow-y-auto">
                {results.map((r, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer">
                    <span className="badge-primary badge text-[10px]">{r.type}</span>
                    <div><p className="text-sm font-medium text-slate-800 dark:text-slate-200">{r.label}</p><p className="text-xs text-slate-400">{r.sub}</p></div>
                  </div>
                ))}
              </div>
            ) : q.length > 1 ? (
              <div className="px-4 py-8 text-center text-sm text-slate-400">No results for "{q}"</div>
            ) : (
              <div className="px-4 py-3 text-xs text-slate-400">Type to search across all permitted records</div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

// ── Date Range Picker ─────────────────────────────────────────────────────
const MONTHS_FULL = ['January','February','March','April','May','June','July','August','September','October','November','December']
const DAYS_SHORT = ['Su','Mo','Tu','We','Th','Fr','Sa']

function Cal({ state, onNav, rs, re, onPick }) {
  const { year, month } = state
  const first = new Date(year, month, 1).getDay()
  const days = new Date(year, month + 1, 0).getDate()
  const today = new Date()
  return (
    <div className="w-52">
      <div className="flex items-center justify-between mb-3">
        <button onClick={() => onNav(-1)} className="btn-ghost btn-icon w-7 h-7 rounded-lg"><ChevronLeft size={13} /></button>
        <span className="text-xs font-bold text-slate-700 dark:text-slate-300">{MONTHS_FULL[month]} {year}</span>
        <button onClick={() => onNav(1)} className="btn-ghost btn-icon w-7 h-7 rounded-lg"><ChevronRight size={13} /></button>
      </div>
      <div className="grid grid-cols-7 gap-0.5">
        {DAYS_SHORT.map(d => <div key={d} className="text-[9px] font-black text-center text-slate-300 dark:text-slate-600 py-1 uppercase">{d}</div>)}
        {Array.from({length:first},(_,i)=><div key={`e${i}`}/>)}
        {Array.from({length:days},(_,i)=>{
          const d=i+1, date=new Date(year,month,d)
          const isToday=date.toDateString()===today.toDateString()
          const isStart=rs&&date.toDateString()===rs.toDateString()
          const isEnd=re&&date.toDateString()===re.toDateString()
          const inRange=rs&&re&&date>rs&&date<re
          return (
            <button key={d} onClick={()=>onPick(date)}
              className={`text-[11px] font-medium rounded py-1 transition-all ${isStart||isEnd?'bg-primary-600 text-white':inRange?'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 rounded-none':isToday?'text-primary-600 font-bold':'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}>
              {d}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function DateRangePicker({ label, onApply }) {
  const [open,setOpen]=useState(false)
  const [preset,setPreset]=useState('all')
  const [dispLabel,setDispLabel]=useState('All time')
  const [rs,setRs]=useState(null),[re,setRe]=useState(null)
  const [lc,setLc]=useState({year:2026,month:6}),[rc,setRc]=useState({year:2026,month:7})
  const ref=useRef(null)
  useEffect(()=>{
    const fn=e=>{if(ref.current&&!ref.current.contains(e.target))setOpen(false)}
    document.addEventListener('mousedown',fn); return()=>document.removeEventListener('mousedown',fn)
  },[])
  const navCal=(side,dir)=>{
    const update=s=>{let{year,month}=s;month+=dir;if(month<0){month=11;year--}if(month>11){month=0;year++}return{year,month}}
    side==='left'?setLc(c=>update(c)):setRc(c=>update(c))
  }
  const pick=date=>{
    if(!rs||re){setRs(date);setRe(null)}else if(date<rs){setRe(rs);setRs(date)}else setRe(date)
    setPreset('')
  }
  const PRESETS=[{id:'7d',label:'Last 7 days'},{id:'1m',label:'Last month'},{id:'3m',label:'Last 3 months'},{id:'6m',label:'Last 6 months'},{id:'all',label:'All time'}]
  const applyPreset=p=>{setPreset(p);setRs(null);setRe(null);const found=PRESETS.find(x=>x.id===p);setDispLabel(found?.label||'All time');onApply&&onApply(p);setOpen(false)}
  const apply=()=>{
    if(rs&&re){const fmt=d=>`${d.getDate()} ${MONTHS_FULL[d.getMonth()].slice(0,3)}`;setDispLabel(`${fmt(rs)} – ${fmt(re)}`)};onApply&&onApply({rs,re});setOpen(false)
  }
  return (
    <div className="relative" ref={ref}>
      <button onClick={()=>setOpen(o=>!o)} className="btn-outline text-xs gap-2">
        <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
        {dispLabel}
        <ChevronDown size={11} className={`transition-transform ${open?'rotate-180':''}`}/>
      </button>
      {open&&(
        <div className="absolute top-full left-0 mt-2 z-50 card shadow-float p-4 animate-slide-up" style={{minWidth:520}}>
          <div className="flex gap-1.5 flex-wrap mb-4">
            {PRESETS.map(p=><button key={p.id} onClick={()=>applyPreset(p.id)} className={`pill ${preset===p.id?'active':''}`}>{p.label}</button>)}
          </div>
          <div className="flex gap-5 mb-4">
            <Cal state={lc} onNav={d=>navCal('left',d)} rs={rs} re={re} onPick={pick}/>
            <div className="w-px bg-slate-100 dark:bg-slate-800"/>
            <Cal state={rc} onNav={d=>navCal('right',d)} rs={rs} re={re} onPick={pick}/>
          </div>
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
            <span className="text-xs text-slate-400">{rs&&!re?'Select end date':rs&&re?'Range selected':'Select start date'}</span>
            <button onClick={apply} disabled={!rs||!re} className="btn-primary btn-sm">Apply range</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Chart Tooltip ─────────────────────────────────────────────────────────
export function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-xl p-3 shadow-float text-xs">
      <p className="font-black text-slate-700 dark:text-slate-300 mb-2">{label}</p>
      {payload.map((p,i)=>(
        <div key={i} className="flex justify-between gap-5 text-slate-500">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm" style={{background:p.color}}/>{p.name}</span>
          <span className="font-bold text-slate-700 dark:text-slate-200">{p.value?.toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

// ── Confirm Dialog ────────────────────────────────────────────────────────
export function Confirm({ open, onClose, onConfirm, title, message, danger }) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm"
      footer={<>
        <button className="btn-secondary btn-sm" onClick={onClose}>Cancel</button>
        <button className={`btn-sm ${danger?'btn-danger':'btn-primary'}`} onClick={()=>{onConfirm();onClose()}}>{danger?'Delete':'Confirm'}</button>
      </>}>
      <p className="text-sm text-slate-600 dark:text-slate-400">{message}</p>
    </Modal>
  )
}
