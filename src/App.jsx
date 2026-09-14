import { useState } from 'react'
import { Shield, LayoutDashboard, GitBranch, Send, ClipboardList, Users, FileText,
  Lock, Moon, Sun, PanelLeftClose, PanelLeftOpen, LogOut, Search, Terminal, BarChart2,
  Building2, Eye, Zap, Activity, Key, Settings, Globe, Server, Clock, AlertTriangle,
  CheckCircle2, Link2, Map, Bell, Wifi, MessageSquare } from 'lucide-react'
import Auth from './pages/Auth'
import { ROLE_META } from './data'
import { NotifBell, Avatar, Toast, GlobalSearch } from './components/UI'
import Leader from './pages/roles/Leader'
import { Coordinator, FieldWorker, Citizen, OrgAdmin, Compliance, SecurityAdmin,
  PlatformOperator, IntegrationClient } from './pages/roles/AllRoles'

// ── Icon map ────────────────────────────────────────────────────────────────
const NAV_ICONS = {
  'AI Copilot': MessageSquare, 'Geographic View': Map, 'Service Debt': BarChart2,
  'Messages (Advanced)': Send, 'Notifications': Bell, 'Language': Globe,
  'TPI Approvals': Shield, 'Offline Sync': Wifi, 'Evidence Integrity': Eye, 'Evidence': Eye,
  'Dashboard': LayoutDashboard, 'Hierarchy': GitBranch, 'Org tree': GitBranch, 'Messages': Send,
  'Tasks': ClipboardList, 'Task Board': LayoutDashboard, 'Citizen Issues': Building2,
  'Analytics': BarChart2, 'Delegation': Link2, 'My Team': Users,
  'Reports': FileText, 'My Tasks': ClipboardList, 'Submit Report': FileText,
  'Offline Queue': Clock, 'Report Issue': Building2, 'Track Issue': Search, 'My Issues': FileText,
  'Overview': LayoutDashboard, 'Members': Users, 'Bulk Import': Users, 'Roles & Policies': Lock,
  'Audit Log': FileText, 'Consent Ledger': FileText, 'Erasure Queue': AlertTriangle,
  'Prohibited Alerts': Shield, 'Retention': Clock, 'Compliance Mode': CheckCircle2,
  'Active Sessions': Activity, 'Auth Events': Shield, 'TPI Queue': Key,
  'Devices': Settings, 'Anomalies': AlertTriangle, 'Tenants': Building2,
  'Support Elevation': Shield, 'Infrastructure': Server, 'Audit': FileText,
  'API Console': Terminal, 'Credentials': Lock, 'Webhooks': Globe,
  'Rate Limits': Zap, 'API Logs': FileText,
}

// ── One-liner descriptions for every tab ────────────────────────────────────
const TAB_DESC = {
  // Leader
  'Dashboard':           'Your command centre — KPIs, alerts and charts for your entire territory',
  'Hierarchy':           'View and understand your organisation structure — who manages which office',
  'Messages (Advanced)': 'Send, schedule, recall messages and see exactly who read them',
  'Tasks':               'Assign work to your team, track progress and handle escalations',
  'Citizen Issues':      'Monitor and act on problems reported by citizens in your area',
  'Analytics':           'Trends, patterns and ground intelligence across all nodes',
  'Delegation':          'Temporarily hand over your authority when you are unavailable',
  'AI Copilot':          'Ask questions about your data in plain English and get cited answers',
  'Geographic View':     'See issue hotspots and unit performance on a live district map',
  'Service Debt':        'Measure how much unresolved backlog each unit carries over time',
  // Coordinator
  'Task Board':          'All tasks assigned in your zone — drag, filter and update in one place',
  'My Team':             'See every field worker under you — status, activity and assignments',
  'Reports':             'Field reports and evidence submitted by your workers',
  'Evidence':            'Check attestation status and integrity of submitted photo/voice evidence',
  // Field Worker
  'My Tasks':            'All tasks assigned to you — accept, start, submit evidence and complete',
  'Submit Report':       'File a field report with photo, voice or text evidence for any task',
  'Offline Sync':        'View your sync queue — what is pending and what has been accepted',
  // Citizen
  'Report Issue':        'Tell us about a problem in your area — voice recording is enough',
  'Track Issue':         'Check the current status of your submitted complaint by reference number',
  'My Issues':           'See all issues you have reported and confirm or dispute their resolution',
  // Org Admin
  'Overview':            'High-level health of your organisation — members, nodes, pending actions',
  'Members':             'Add, suspend or remove people and manage their roles',
  'Bulk Import':         'Import many members at once from an Excel or CSV file with dry-run preview',
  'Roles & Policies':    'Configure what each role can see and do within your organisation',
  'Audit Log':           'Tamper-evident record of every action taken — searchable and exportable',
  'Notifications':       'Set your channel preferences and quiet hours for each notification type',
  'Language':            'Choose display language — English, Hindi, Kannada and more',
  // Compliance
  'Consent Ledger':      'Records of every citizen consent — purpose, version and timestamp',
  'Erasure Queue':       'Process personal data deletion requests and generate certificates',
  'Prohibited Alerts':   'Blocked attempts to collect caste, religion or political attributes',
  'Retention':           'Configure how long each data class is kept before automatic deletion',
  'Compliance Mode':     'Activate named compliance profiles (e.g. MCC election period) tenant-wide',
  'Evidence Integrity':  'Audit the attestation chain for every piece of field evidence',
  // Security Admin
  'Active Sessions':     'See every live session — device, location and idle time — and revoke any',
  'Auth Events':         'Login history, failed attempts and suspicious access events',
  'TPI Approvals':       'Approve high-impact actions that require a second authorised person',
  'Devices':             'Registered devices — trust status, attestation and revocation',
  'Anomalies':           'Automated alerts for unusual patterns — repeated failures, new devices',
  // Platform Operator
  'Tenants':             'All customer organisations — health, usage and support elevation history',
  'Support Elevation':   'Request time-boxed access to a customer org with their explicit approval',
  'Infrastructure':      'System uptime, queue depth, AI cost and key operational metrics',
  'Audit':               'Cross-tenant audit trail for platform-level actions and elevations',
  // Integration Client
  'API Console':         'Make live API calls, inspect responses and test your integration',
  'Credentials':         'Manage API keys, scopes and rate limits for your client',
  'Webhooks':            'Configure signed webhook endpoints for real-time event delivery',
  'Rate Limits':         'View your current usage versus your allowed limits per scope',
  'API Logs':            'Every API call your client made — status, latency and error detail',
  // TPI Queue (old label)
  'TPI Queue':           'Actions needing a second approver — review, approve or reject with MFA',
}

const ROLE_COMPONENT = {
  leader: Leader, coordinator: Coordinator, field_worker: FieldWorker, citizen: Citizen,
  org_admin: OrgAdmin, compliance: Compliance, security_admin: SecurityAdmin,
  platform_operator: PlatformOperator, integration_client: IntegrationClient,
}
const ACCENT_MAP = {
  leader:'#4f46e5', coordinator:'#d97706', field_worker:'#0284c7', citizen:'#16a34a',
  org_admin:'#0891b2', compliance:'#059669', security_admin:'#dc2626',
  platform_operator:'#7c3aed', integration_client:'#9333ea',
}

export default function App() {
  const [user, setUser] = useState(null)
  const [dark, setDark] = useState(false)
  const [page, setPage] = useState(0)
  const [collapsed, setCollapsed] = useState(false)
  const [toasts, setToasts] = useState([])

  const addToast = (msg, type='success') => setToasts(t=>[...t,{id:Date.now(),message:msg,type}])
  const rmToast  = id => setToasts(t=>t.filter(x=>x.id!==id))

  const toggleDark = () => {
    setDark(d=>{ document.documentElement.classList.toggle('dark',!d); return !d })
  }
  const signOut = () => {
    addToast('Signed out','info')
    setTimeout(()=>setUser(null),300)
    setPage(0)
  }
  const handleLogin = u => {
    setUser(u); setPage(0)
    addToast(`Welcome, ${u.name}! Signed in as ${ROLE_META[u.role].label}.`)
  }

  if (!user) return (
    <>
      <Auth onSuccess={handleLogin}/>
      {toasts.map(t=><Toast key={t.id} message={t.message} type={t.type} onClose={()=>rmToast(t.id)}/>)}
    </>
  )

  const meta      = ROLE_META[user.role]
  const accent    = ACCENT_MAP[user.role] || '#4f46e5'
  const nav       = meta.nav || []
  const RolePage  = ROLE_COMPONENT[user.role] || Leader
  const curLabel  = nav[page] || nav[0]
  const curDesc   = TAB_DESC[curLabel] || ''
  const isMobile  = user.role==='field_worker' || user.role==='citizen'

  return (
    <div className={dark?'dark':''}>
      <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">

        {/* ── Sidebar ─────────────────────────────────────────────────── */}
        <aside className={`relative flex-shrink-0 flex flex-col bg-white dark:bg-slate-900 border-r border-slate-100 dark:border-slate-800 transition-all duration-200 ${collapsed?'w-[60px]':'w-[230px]'}`}>

          {/* Logo */}
          <div className="flex items-center gap-3 px-3.5 h-14 border-b border-slate-100 dark:border-slate-800 flex-shrink-0">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md" style={{background:`linear-gradient(135deg,${accent},${accent}bb)`}}>
              <Shield size={16} className="text-white"/>
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <div className="font-black text-slate-900 dark:text-white text-sm leading-tight">GroundConnect</div>
                <div className="text-[10px] font-bold" style={{color:accent}}>AI Platform</div>
              </div>
            )}
          </div>

          {/* Role badge */}
          {!collapsed ? (
            <div className="mx-2.5 mt-3 mb-2 flex-shrink-0">
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl border" style={{background:meta.bg,borderColor:accent+'30',color:accent}}>
                <span className="text-base flex-shrink-0">{meta.icon}</span>
                <div className="min-w-0">
                  <div className="text-xs font-black truncate">{meta.label}</div>
                  <div className="text-[10px] font-medium opacity-60 truncate">{user.region}</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex justify-center mt-3 mb-2 flex-shrink-0">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center text-base border" style={{background:meta.bg,borderColor:accent+'30'}}>{meta.icon}</div>
            </div>
          )}

          {/* Nav */}
          <nav className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
            {nav.map((label,i)=>{
              const Icon = NAV_ICONS[label]||LayoutDashboard
              const isActive = page===i
              const desc = TAB_DESC[label]||''
              return (
                <button key={i} onClick={()=>setPage(i)} title={collapsed?label:undefined}
                  className={`nav-item ${isActive?'active':''} ${collapsed?'justify-center px-2':''}`}
                  style={isActive?{color:accent,backgroundColor:accent+'12',borderColor:accent+'25'}:{}}>
                  <Icon size={15} className="flex-shrink-0"/>
                  {!collapsed && (
                    <div className="min-w-0 text-left">
                      <div className="text-[13px] font-semibold truncate">{label}</div>
                      {desc && <div className="text-[9px] leading-tight text-slate-400 truncate mt-0.5" style={isActive?{color:accent+'99'}:{}}>{desc}</div>}
                    </div>
                  )}
                </button>
              )
            })}
          </nav>

          {/* Bottom */}
          <div className="px-2 pb-2 pt-1 border-t border-slate-100 dark:border-slate-800 space-y-0.5 flex-shrink-0">
            <button onClick={toggleDark} className={`nav-item ${collapsed?'justify-center px-2':''}`}>
              {dark?<Sun size={15} className="flex-shrink-0"/>:<Moon size={15} className="flex-shrink-0"/>}
              {!collapsed&&<span className="text-[13px]">{dark?'Light mode':'Dark mode'}</span>}
            </button>
            <button onClick={()=>setCollapsed(c=>!c)} className={`nav-item ${collapsed?'justify-center px-2':''}`}>
              {collapsed?<PanelLeftOpen size={15} className="flex-shrink-0"/>:<PanelLeftClose size={15} className="flex-shrink-0"/>}
              {!collapsed&&<span className="text-[13px]">Collapse sidebar</span>}
            </button>
            <button onClick={signOut} className={`nav-item text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20 hover:text-rose-600 ${collapsed?'justify-center px-2':''}`}>
              <LogOut size={15} className="flex-shrink-0"/>
              {!collapsed&&<span className="text-[13px]">Sign out</span>}
            </button>
          </div>
        </aside>

        {/* ── Main area ───────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">

          {/* Topbar */}
          <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between px-6 gap-4 flex-shrink-0">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <div className="text-base font-black text-slate-900 dark:text-white leading-tight truncate">{curLabel}</div>
                {/* Accent dot */}
                <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{background:accent}}/>
              </div>
              {curDesc && (
                <div className="text-[11px] text-slate-400 truncate mt-0.5 max-w-xl">{curDesc}</div>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <GlobalSearch/>
              <NotifBell accent={accent}/>
              <div className="flex items-center gap-2.5 pl-3 border-l border-slate-100 dark:border-slate-800">
                <Avatar initials={user.avatar} size="sm" color={accent}/>
                <div className="hidden sm:block min-w-0">
                  <div className="text-xs font-black text-slate-900 dark:text-white leading-tight truncate max-w-[120px]">{user.name}</div>
                  <div className="text-[10px] font-semibold truncate" style={{color:accent}}>{meta.label}</div>
                </div>
              </div>
            </div>
          </header>

          {/* Page */}
          <main className={`flex-1 overflow-auto ${isMobile?'p-4':'p-6'}`}>
            <RolePage page={page} accent={accent} user={user}/>
          </main>
        </div>
      </div>

      {toasts.map(t=><Toast key={t.id} message={t.message} type={t.type} onClose={()=>rmToast(t.id)}/>)}
    </div>
  )
}
