
// ── Named constants (replace magic numbers in components) ───────────────
export const ORG_TOTAL_MEMBERS  = 8234
export const ORG_TOTAL_RECIPIENTS = 12400
export const DEV_PORT           = 5173
export const DEMO_MOBILE_PREFIX = '+91 98765 0000'

// Feature flag: set VITE_USE_MOCK=false in .env to use real backend API
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

// ── Role definitions ──────────────────────────────────────────────────────
export const ROLES = {
  LEADER:'leader', COORD:'coordinator', FIELD:'field_worker', CITIZEN:'citizen',
  ORG_ADMIN:'org_admin', COMPLIANCE:'compliance', SECURITY:'security_admin',
  PLATFORM:'platform_operator', INTEGRATION:'integration_client'
}

export const ROLE_META = {
  leader:             { label:'Leader',             icon:'👑', accent:'#4f46e5', bg:'#eef2ff', nav:['Dashboard','Hierarchy','Messages (Advanced)','Tasks','Citizen Issues','Analytics','Delegation','AI Copilot','Geographic View','Service Debt'] },
  coordinator:        { label:'Coordinator',         icon:'📋', accent:'#d97706', bg:'#fffbeb', nav:['Task Board','My Team','Messages','Citizen Issues','Reports','AI Copilot','Evidence'] },
  field_worker:       { label:'Field Worker',        icon:'🦺', accent:'#0284c7', bg:'#f0f9ff', nav:['My Tasks','Submit Report','Messages','Offline Sync','AI Copilot'] },
  citizen:            { label:'Citizen',             icon:'🏠', accent:'#16a34a', bg:'#f0fdf4', nav:['Report Issue','Track Issue','My Issues'] },
  org_admin:          { label:'Org Administrator',   icon:'🏛️', accent:'#0891b2', bg:'#ecfeff', nav:['Overview','Hierarchy','Members','Bulk Import','Roles & Policies','Audit Log','Notifications','Language','AI Copilot'] },
  compliance:         { label:'Compliance Officer',  icon:'⚖️', accent:'#059669', bg:'#ecfdf5', nav:['Overview','Consent Ledger','Erasure Queue','Prohibited Alerts','Retention','Compliance Mode','Evidence Integrity'] },
  security_admin:     { label:'Security Admin',      icon:'🔐', accent:'#dc2626', bg:'#fef2f2', nav:['Overview','Active Sessions','Auth Events','TPI Approvals','Devices','Anomalies'] },
  platform_operator:  { label:'Platform Operator',   icon:'🛠️', accent:'#7c3aed', bg:'#f5f3ff', nav:['Overview','Tenants','Support Elevation','Infrastructure','Audit'] },
  integration_client: { label:'Integration Client',  icon:'🔌', accent:'#9333ea', bg:'#faf5ff', nav:['API Console','Credentials','Webhooks','Rate Limits','API Logs'] },
}

export const DEMO_USERS = [
  { mobile:'+91 98765 00005', password:'demo1234', role:'leader',             name:'Ravi Kumar',   avatar:'RK', region:'State HQ' },
  { mobile:'+91 98765 00006', password:'demo1234', role:'coordinator',        name:'Sita Devi',    avatar:'SD', region:'North District' },
  { mobile:'+91 98765 00007', password:'demo1234', role:'field_worker',       name:'Arjun Patel',  avatar:'AP', region:'Zone A' },
  { mobile:'+91 98765 00008', password:'demo1234', role:'citizen',            name:'Meena Sharma', avatar:'MS', region:'Booth 12' },
  { mobile:'+91 98765 00002', password:'demo1234', role:'org_admin',          name:'Priya Menon',  avatar:'PM', region:'All Regions' },
  { mobile:'+91 98765 00003', password:'demo1234', role:'compliance',         name:'Ananya Roy',   avatar:'AR', region:'All Regions' },
  { mobile:'+91 98765 00004', password:'demo1234', role:'security_admin',     name:'Rahul Das',    avatar:'RD', region:'All Regions' },
  { mobile:'+91 98765 00001', password:'demo1234', role:'platform_operator',  name:'Vikram Nair',  avatar:'VN', region:'Global' },
  { mobile:'+91 98765 00009', password:'demo1234', role:'integration_client', name:'API Service',  avatar:'AS', region:'API' },
]

// ── Org tree ──────────────────────────────────────────────────────────────
export const ORG_TREE = {
  id:1, name:'State HQ', role:'leader', responsible:'Ravi Kumar', level:0,
  members:12, tasks:8, issues:4, status:'active',
  children:[
    { id:2, name:'North District', role:'leader', responsible:'Kiran Rao', level:1,
      members:45, tasks:23, issues:11, status:'active',
      children:[
        { id:4, name:'Zone A — Booth 12', role:'coordinator', responsible:'Sita Devi',  level:2, members:8, tasks:5, issues:2, status:'active', children:[] },
        { id:5, name:'Zone B — Booth 19', role:'coordinator', responsible:'Raj Kumar',  level:2, members:6, tasks:3, issues:1, status:'active', children:[] },
      ]
    },
    { id:3, name:'South District', role:'leader', responsible:null, level:1,
      members:38, tasks:17, issues:9, status:'orphaned',
      children:[
        { id:6, name:'Zone C — Booth 31', role:'coordinator', responsible:'Dev Patel', level:2, members:5, tasks:7, issues:3, status:'dark', children:[] },
      ]
    },
    { id:7, name:'East District', role:'leader', responsible:'Anil Shah', level:1,
      members:31, tasks:14, issues:6, status:'active',
      children:[
        { id:8, name:'Zone D — Booth 44', role:'coordinator', responsible:'Priya Das', level:2, members:7, tasks:4, issues:0, status:'active', children:[] },
      ]
    },
  ]
}

// ── Charts ────────────────────────────────────────────────────────────────
export const TASK_CHART = [
  {month:'Jan',completed:142,overdue:18,blocked:7},{month:'Feb',completed:189,overdue:12,blocked:4},
  {month:'Mar',completed:165,overdue:21,blocked:9},{month:'Apr',completed:210,overdue:8,blocked:3},
  {month:'May',completed:198,overdue:15,blocked:6},{month:'Jun',completed:234,overdue:6,blocked:2},
  {month:'Jul',completed:221,overdue:11,blocked:5},{month:'Aug',completed:256,overdue:4,blocked:1},
]
export const MSG_CHART = [
  {month:'Jan',sent:3200,delivered:3050,read:2800},{month:'Feb',sent:4100,delivered:3980,read:3650},
  {month:'Mar',sent:3750,delivered:3620,read:3100},{month:'Apr',sent:4800,delivered:4700,read:4200},
  {month:'May',sent:5100,delivered:4950,read:4500},{month:'Jun',sent:4600,delivered:4500,read:4100},
  {month:'Jul',sent:5800,delivered:5680,read:5200},{month:'Aug',sent:6200,delivered:6100,read:5700},
]
export const CITIZEN_CHART = [
  {category:'Infrastructure',open:45,resolved:120,escalated:8},
  {category:'Public Safety',open:28,resolved:89,escalated:12},
  {category:'Utilities',open:62,resolved:145,escalated:5},
  {category:'Sanitation',open:33,resolved:98,escalated:3},
  {category:'Transport',open:19,resolved:67,escalated:6},
]
export const EVIDENCE_PIE = [
  {name:'Attested',value:72,color:'#4f46e5'},{name:'Unattested',value:20,color:'#f59e0b'},{name:'Flagged',value:8,color:'#f43f5e'},
]
export const UPTIME_CHART = [
  {month:'Jan',uptime:99.9,latency:45},{month:'Feb',uptime:99.8,latency:48},{month:'Mar',uptime:99.9,latency:42},
  {month:'Apr',uptime:100,latency:40},{month:'May',uptime:99.7,latency:52},{month:'Jun',uptime:99.9,latency:44},
  {month:'Jul',uptime:99.9,latency:41},{month:'Aug',uptime:100,latency:38},
]

// ── Tasks ─────────────────────────────────────────────────────────────────
export const TASKS = [
  {id:'TSK-001',title:'Booth infrastructure audit',assignee:'Arjun Patel',node:'Zone A',due:'Today',priority:'High',status:'In Progress',evidence:'attested',desc:'Full audit of all booths in Zone A. Submit photo evidence for each booth.',escalation:'Escalate to district leader if not completed by EOD.'},
  {id:'TSK-002',title:'Voter list verification — Zone A',assignee:'Meena Sharma',node:'Zone A',due:'Tomorrow',priority:'High',status:'Assigned',evidence:'none',desc:'Cross-verify voter database entries with physical booth records.',escalation:'Notify coordinator if discrepancy > 5%.'},
  {id:'TSK-003',title:'Field worker onboarding — batch 3',assignee:'Arjun Patel',node:'Zone B',due:'Aug 15',priority:'Medium',status:'Blocked',evidence:'unattested',desc:'Onboard 12 new field workers. Blocked: pending ID verification.',escalation:'Auto-escalate after 48h.'},
  {id:'TSK-004',title:'District report submission',assignee:'Sita Devi',node:'North District',due:'Aug 12',priority:'Low',status:'Completed',evidence:'attested',desc:'Monthly performance report for North District HQ.',escalation:'None.'},
  {id:'TSK-005',title:'Emergency response drill',assignee:'Venkat Rao',node:'Zone C',due:'Aug 18',priority:'High',status:'Overdue',evidence:'flagged',desc:'Conduct emergency mobilisation drill across all zones.',escalation:'Already escalated to State HQ.'},
  {id:'TSK-006',title:'Booth register update — Q3',assignee:'Priya Das',node:'Zone D',due:'Aug 20',priority:'Medium',status:'In Progress',evidence:'attested',desc:'Update all Q3 registrations in the booth management system.',escalation:'Notify if not completed by Aug 19.'},
]

// ── Messages ──────────────────────────────────────────────────────────────
export const MESSAGES = [
  {id:1,type:'Emergency',subject:'Mobilisation order — all districts',from:'State HQ',recipients:12400,time:'09:14',status:'delivered',body:'Immediate mobilisation required across all 7 districts. Report to designated assembly points by 11:00 AM.',priority:'high',ack:true},
  {id:2,type:'Instruction',subject:'Booth setup checklist due Friday',from:'North District',recipients:890,time:'Yesterday',status:'read',body:'All booth coordinators must submit the Q3 setup checklist by EOD Friday. Template attached.',priority:'medium',ack:false},
  {id:3,type:'Announcement',subject:'Monthly performance review scheduled',from:'South District',recipients:340,time:'Mon',status:'pending',body:'Performance review meeting is scheduled for Aug 20 at 10 AM at District HQ.',priority:'low',ack:false},
  {id:4,type:'Survey',subject:'Field worker satisfaction survey',from:'State HQ',recipients:6700,time:'Sun',status:'delivered',body:'Please complete the quarterly satisfaction survey. Your feedback is important.',priority:'low',ack:false},
  {id:5,type:'Information',subject:'Weather alert: heavy rain in Zone C',from:'East District',recipients:230,time:'Sat',status:'read',body:'Heavy rainfall predicted Aug 14-16. All outdoor activities to be rescheduled.',priority:'medium',ack:false},
]

// ── Citizens ──────────────────────────────────────────────────────────────
export const CITIZEN_ISSUES = [
  {id:'CIT-001',category:'Infrastructure',title:'Broken street light near Booth 12',citizen:'Meena Sharma',phone:'+91 98765 00008',submitted:'Aug 10',status:'In Progress',priority:'High',location:'Zone A',resolution:null,corroborations:4,desc:'Street light has been broken for 2 weeks causing safety issues at night.'},
  {id:'CIT-002',category:'Utilities',title:'Water supply disruption — 3 days',citizen:'Raj Patel',phone:'+91 98765 11111',submitted:'Aug 9',status:'Escalated',priority:'High',location:'Zone B',resolution:null,corroborations:12,desc:'No water supply for 3 consecutive days in Sector 4.'},
  {id:'CIT-003',category:'Sanitation',title:'Garbage not collected for 5 days',citizen:'Anita Kumar',phone:'+91 98765 22222',submitted:'Aug 8',status:'Resolved-Confirmed',priority:'Medium',location:'Zone A',resolution:'Sanitation team visited Aug 9. Issue resolved.',corroborations:3,desc:'Municipal garbage vehicle has not visited the area for 5 days.'},
  {id:'CIT-004',category:'Transport',title:'No bus service since Monday',citizen:'Dev Singh',phone:'+91 98765 33333',submitted:'Aug 7',status:'Assigned',priority:'Medium',location:'Zone C',resolution:null,corroborations:8,desc:'Bus route 47 has been suspended without prior notice.'},
  {id:'CIT-005',category:'Public Safety',title:'Broken footpath causing accidents',citizen:'Sita Menon',phone:'+91 98765 44444',submitted:'Aug 6',status:'Disputed-Reopened',priority:'High',location:'Zone D',resolution:'Marked as resolved by team — not actually fixed.',corroborations:6,desc:'Large crack in footpath near school has already caused 2 minor injuries.'},
]

// ── Auth log ──────────────────────────────────────────────────────────────
export const AUTH_LOG = [
  {id:1,time:'09:42',user:'admin@statehq.in',action:'Login',device:'Registered',result:'success',ip:'192.168.1.10',mfa:'totp'},
  {id:2,time:'09:38',user:'district.north@gc.in',action:'Bulk export',device:'Registered',result:'success',ip:'192.168.1.22',mfa:'sms'},
  {id:3,time:'09:21',user:'unknown@attempt.com',action:'Login',device:'Unregistered',result:'denied',ip:'103.45.67.89',mfa:'—'},
  {id:4,time:'08:55',user:'coord.zoneb@gc.in',action:'Bulk transfer',device:'Registered',result:'pending-tpi',ip:'192.168.2.5',mfa:'totp'},
  {id:5,time:'08:30',user:'field.1204@gc.in',action:'Evidence upload',device:'Registered',result:'success',ip:'10.0.0.44',mfa:'otp'},
  {id:6,time:'08:12',user:'api.service@gc.in',action:'API call',device:'Registered',result:'success',ip:'172.16.0.3',mfa:'api-key'},
]

// ── Consent ───────────────────────────────────────────────────────────────
export const CONSENT_LOG = [
  {id:'CON-001',citizen:'Meena Sharma',purpose:'Issue tracking',version:'v2.1',date:'Aug 10',mechanism:'OTP-verified',status:'active',retained:['name','phone','location']},
  {id:'CON-002',citizen:'Raj Patel',purpose:'Service delivery',version:'v2.1',date:'Aug 9',mechanism:'OTP-verified',status:'active',retained:['name','phone']},
  {id:'CON-003',citizen:'Anita Kumar',purpose:'Grievance resolution',version:'v2.0',date:'Jul 28',mechanism:'OTP-verified',status:'active',retained:['name','phone','issue']},
  {id:'CON-004',citizen:'Dev Singh',purpose:'Issue tracking',version:'v2.1',date:'Aug 7',mechanism:'OTP-verified',status:'erasure-requested',retained:['name','phone']},
]

// ── Members ───────────────────────────────────────────────────────────────
export const MEMBERS = [
  {id:1,name:'Ravi Kumar',role:'leader',node:'State HQ',mobile:'+91 98765 00005',status:'active',lastActive:'2m ago',mfa:'enabled'},
  {id:2,name:'Sita Devi',role:'coordinator',node:'North District',mobile:'+91 98765 00006',status:'active',lastActive:'15m ago',mfa:'enabled'},
  {id:3,name:'Arjun Patel',role:'field_worker',node:'Zone A',mobile:'+91 98765 00007',status:'active',lastActive:'1h ago',mfa:'enabled'},
  {id:4,name:'Dev Patel',role:'coordinator',node:'Zone C',mobile:'+91 98765 55555',status:'active',lastActive:'3d ago',mfa:'disabled'},
  {id:5,name:'Priya Das',role:'coordinator',node:'Zone D',mobile:'+91 98765 66666',status:'suspended',lastActive:'1w ago',mfa:'enabled'},
  {id:6,name:'Venkat Rao',role:'field_worker',node:'Zone C',mobile:'+91 98765 77777',status:'active',lastActive:'30m ago',mfa:'enabled'},
  {id:7,name:'Kiran Rao',role:'leader',node:'North District',mobile:'+91 98765 88888',status:'active',lastActive:'4h ago',mfa:'enabled'},
  {id:8,name:'Anil Shah',role:'leader',node:'East District',mobile:'+91 98765 99999',status:'active',lastActive:'6h ago',mfa:'enabled'},
]

// ── Delegations ───────────────────────────────────────────────────────────
export const DELEGATIONS = [
  {id:'DEL-001',delegator:'Ravi Kumar',delegatee:'Sita Devi',scope:'North District tasks and messaging',from:'Aug 10',to:'Aug 17',status:'active',reason:'Annual leave'},
  {id:'DEL-002',delegator:'Kiran Rao',delegatee:'Arjun Patel',scope:'Zone A field reports only',from:'Aug 5',to:'Aug 12',status:'expired',reason:'Training program'},
]

// ── TPI Queue ─────────────────────────────────────────────────────────────
export const TPI_QUEUE = [
  {id:'TPI-001',action:'Mass messaging above threshold',requester:'Ravi Kumar',threshold:'12,400 recipients',requested:'09:10',expires:'13:10',status:'pending'},
  {id:'TPI-002',action:'Bulk hierarchy reassignment',requester:'Priya Menon',threshold:'500+ nodes',requested:'08:55',expires:'12:55',status:'pending'},
  {id:'TPI-003',action:'AI provider config change',requester:'Vikram Nair',threshold:'Security control',requested:'Aug 9',expires:'Expired',status:'approved'},
]

// ── API Log ───────────────────────────────────────────────────────────────
export const API_LOG = [
  {time:'09:44',endpoint:'/api/v1/members',method:'GET',status:200,latency:'45ms',scope:'members:read',tokens:1},
  {time:'09:43',endpoint:'/api/v1/issues',method:'POST',status:201,latency:'120ms',scope:'issues:write',tokens:1},
  {time:'09:41',endpoint:'/api/v1/hierarchy/nodes',method:'GET',status:200,latency:'38ms',scope:'hierarchy:read',tokens:1},
  {time:'09:38',endpoint:'/api/v1/messages',method:'POST',status:403,latency:'12ms',scope:'messages:write — DENIED',tokens:0},
  {time:'09:35',endpoint:'/api/v1/tasks',method:'GET',status:200,latency:'67ms',scope:'tasks:read',tokens:1},
  {time:'09:30',endpoint:'/api/v1/audit',method:'GET',status:403,latency:'8ms',scope:'audit:read — DENIED',tokens:0},
]

// ── Offline queue ─────────────────────────────────────────────────────────
export const OFFLINE_QUEUE = [
  {id:'Q-001',type:'Field report',task:'TSK-001',size:'2.4 MB',status:'pending',captured:'10:23'},
  {id:'Q-002',type:'Photo evidence',task:'TSK-001',size:'1.1 MB',status:'uploading',captured:'10:24'},
  {id:'Q-003',type:'Voice note',task:'TSK-003',size:'0.3 MB',status:'accepted',captured:'10:12'},
]

// ── Prohibited alerts ─────────────────────────────────────────────────────
export const PROHIBITED_ALERTS = [
  {id:'PA-001',field:'custom_field_3',tenant:'State Org A',match:'community',blocked:true,time:'Aug 10 09:21',reported:false},
  {id:'PA-002',field:'notes_field',tenant:'State Org A',match:'caste',blocked:true,time:'Aug 8 14:05',reported:true},
  {id:'PA-003',field:'description',tenant:'State Org A',match:'religion',blocked:true,time:'Aug 7 11:30',reported:true},
]

// ── Tenants (Platform Op) ─────────────────────────────────────────────────
export const TENANTS = [
  {id:1,name:'State Organization A',nodes:8234,users:12400,health:98.2,plan:'Enterprise',lastElevation:'2h ago',db:'shared',region:'India — Mumbai'},
  {id:2,name:'NGO Federation B',nodes:1240,users:3400,health:99.8,plan:'Pro',lastElevation:'1d ago',db:'shared',region:'India — Delhi'},
  {id:3,name:'Cooperative Union C',nodes:445,users:890,health:97.1,plan:'Standard',lastElevation:'3d ago',db:'shared',region:'India — Bengaluru'},
]
