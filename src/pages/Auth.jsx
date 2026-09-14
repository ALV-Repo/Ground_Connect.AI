import { useState, useRef, useEffect } from 'react'
import { Shield, Eye, EyeOff, ArrowRight, AlertCircle, RefreshCw, Smartphone, Mail, Key, CheckCircle2, Lock, Zap } from 'lucide-react'
import { DEMO_USERS, ROLE_META } from '../data'

const STEPS = ['Sign in', 'OTP', 'Choose MFA', 'MFA Code']

function StepBar({ current }) {
  return (
    <div className="flex items-start gap-0 mb-7">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-start flex-1 last:flex-none">
          <div className="flex flex-col items-center">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-black transition-all duration-300 ${i<current?'bg-emerald-500 text-white':i===current?'bg-primary-600 text-white shadow-glow':'bg-slate-100 dark:bg-slate-800 text-slate-400'}`}>
              {i < current ? '✓' : i + 1}
            </div>
            <span className={`text-[9px] font-bold mt-1 whitespace-nowrap ${i===current?'text-primary-600 dark:text-primary-400':'text-slate-400'}`}>{label}</span>
          </div>
          {i < STEPS.length - 1 && <div className={`flex-1 h-0.5 mt-3.5 mx-2 rounded-full transition-all duration-500 ${i<current?'bg-emerald-400':'bg-slate-100 dark:bg-slate-800'}`}/>}
        </div>
      ))}
    </div>
  )
}

function OtpBoxes({ length = 6, onComplete, resetKey }) {
  const [vals, setVals] = useState(Array(length).fill(''))
  const refs = useRef(Array.from({ length }, () => null))
  useEffect(() => { setVals(Array(length).fill('')); refs.current[0]?.focus() }, [resetKey])
  const change = (i, e) => {
    const v = e.target.value.replace(/\D/g, '').slice(-1)
    const next = [...vals]; next[i] = v; setVals(next)
    if (v && i < length - 1) refs.current[i + 1]?.focus()
    if (next.every(c => c)) onComplete(next.join(''))
  }
  const keydown = (i, e) => { if (e.key === 'Backspace' && !vals[i] && i > 0) refs.current[i - 1]?.focus() }
  const paste = e => {
    const t = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length)
    if (t.length === length) { setVals(t.split('')); refs.current[length-1]?.focus(); onComplete(t) }
    e.preventDefault()
  }
  return (
    <div className="flex gap-2 justify-center my-5">
      {vals.map((v, i) => (
        <input key={i} ref={el => refs.current[i] = el} type="text" inputMode="numeric" maxLength={1} value={v}
          onChange={e => change(i, e)} onKeyDown={e => keydown(i, e)} onPaste={paste}
          className={`otp-box ${v ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/40 text-primary-700 dark:text-primary-300' : ''}`} />
      ))}
    </div>
  )
}

function Timer({ onResend }) {
  const [secs, setSecs] = useState(298)
  useEffect(() => { const t = setInterval(() => setSecs(s => Math.max(0, s - 1)), 1000); return () => clearInterval(t) }, [])
  const m = Math.floor(secs / 60), s = secs % 60
  return (
    <p className="text-center text-xs text-slate-400 mt-1">
      {secs === 0
        ? <button onClick={onResend} className="text-primary-600 font-semibold hover:underline flex items-center gap-1 mx-auto"><RefreshCw size={11}/>Resend code</button>
        : <>Expires in <span className="text-primary-600 font-bold tabular-nums">{m}:{String(s).padStart(2,'0')}</span></>}
    </p>
  )
}

const MFA_METHODS = [
  { id:'totp', icon:Smartphone, label:'Authenticator app', sub:'Google / Microsoft Authenticator' },
  { id:'sms',  icon:Smartphone, label:'SMS code',          sub:'Sent to registered number' },
  { id:'email',icon:Mail,       label:'Email code',        sub:'Sent to work email' },
  { id:'backup',icon:Key,       label:'Backup code',       sub:'One of 10 recovery codes' },
]

export default function Auth({ onSuccess }) {
  const [step, setStep] = useState(0)
  const [mobile, setMobile] = useState('')
  const [pwd, setPwd] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [err, setErr] = useState('')
  const [mfa, setMfa] = useState('totp')
  const [otpReset, setOtpReset] = useState(0)
  const [mfaReset, setMfaReset] = useState(0)
  const [user, setUser] = useState(null)
  const [selDemo, setSelDemo] = useState(null)

  const s0 = () => {
    const u = DEMO_USERS.find(u => u.mobile === mobile && u.password === pwd)
    if (!u) { setErr('Mobile number or password is incorrect.'); return }
    setErr(''); setUser(u); setStep(1)
  }
  const otp = code => { if (code==='000000'){setErr('Incorrect OTP.');setOtpReset(r=>r+1);return}; setErr(''); setStep(2) }
  const mfaCode = code => { if (code==='000000'){setErr('Invalid code.');setMfaReset(r=>r+1);return}; setErr(''); onSuccess(user) }
  const fill = u => { setMobile(u.mobile); setPwd(u.password); setSelDemo(u.role); setErr('') }

  const meta = user ? ROLE_META[user.role] : null

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950">
      {/* Left panel */}
      <div className="hidden lg:flex w-96 flex-shrink-0 flex-col p-10 relative overflow-hidden" style={{background:'linear-gradient(160deg,#1e1b4b 0%,#312e81 50%,#0f172a 100%)'}}>
        <div className="absolute inset-0" style={{backgroundImage:'radial-gradient(circle at 30% 50%,rgba(99,102,241,0.25) 0%,transparent 60%),radial-gradient(circle at 80% 10%,rgba(6,182,212,0.15) 0%,transparent 50%)'}}/>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-12">
            <div className="w-10 h-10 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center"><Shield size={20} className="text-white"/></div>
            <div><div className="text-white font-black text-base">GroundConnect AI</div><div className="text-primary-300 text-xs">Secure Hierarchical Platform</div></div>
          </div>
          <h1 className="text-3xl font-black text-white leading-tight mb-4">The ground,<br/>made visible.</h1>
          <p className="text-primary-200 text-sm leading-relaxed mb-8">Enterprise-grade digital operating platform for large hierarchical field organizations, with citizen service management.</p>
          {[['🔐','MFA-protected for all 9 role types'],['📊','Real-time hierarchy tree visibility'],['🏛️','DPDP-compliant citizen portal'],['🛡️','Hash-chained immutable audit trail'],['⚡','Offline-first field worker app']].map(([e,t],i)=>(
            <div key={i} className="flex items-center gap-2.5 text-xs text-primary-200 mb-3"><span className="text-base">{e}</span>{t}</div>
          ))}
        </div>
        <div className="relative z-10 mt-auto">
          <p className="text-[10px] font-black uppercase tracking-widest text-primary-400 mb-3">Demo — sign in as any role</p>
          <div className="space-y-1">
            {DEMO_USERS.filter(u=>u.role!=='integration_client').map(u=>{const m=ROLE_META[u.role];return(
              <button key={u.role} onClick={()=>fill(u)} className={`flex items-center gap-2.5 w-full px-3 py-2 rounded-xl text-xs font-medium border transition-all ${selDemo===u.role?'bg-white/20 border-white/30 text-white':'border-transparent hover:bg-white/10 text-primary-200'}`}>
                <span className="text-sm">{m.icon}</span>
                <div className="flex-1 text-left"><div className="font-bold text-white/90">{m.label}</div><div className="text-primary-400 text-[10px]">{u.mobile}</div></div>
                {selDemo===u.role&&<CheckCircle2 size={12} className="text-emerald-400"/>}
              </button>
            )})}
          </div>
          <p className="text-[10px] text-primary-500 mt-3 text-center">Password: <span className="font-mono text-primary-300">demo1234</span> · OTP/MFA: any code ≠ 000000</p>
        </div>
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md animate-slide-up">
          <div className="flex lg:hidden items-center gap-3 mb-8 justify-center">
            <div className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center shadow-glow"><Shield size={20} className="text-white"/></div>
            <div><div className="font-black text-slate-900 dark:text-white text-base">GroundConnect AI</div><div className="text-xs text-slate-400">Secure Hierarchical Platform</div></div>
          </div>
          <div className="card p-8 shadow-float">
            {step > 0 && <StepBar current={step} />}
            {meta && step > 0 && (
              <div className="flex items-center gap-3 mb-5 p-3 rounded-xl border" style={{background:meta.bg+'80',borderColor:meta.accent+'40'}}>
                <span className="text-xl">{meta.icon}</span>
                <div><div className="text-xs font-black" style={{color:meta.accent}}>{meta.label}</div><div className="text-[10px] text-slate-500">{user.name} · {user.region}</div></div>
                <div className="ml-auto flex items-center gap-1 text-[10px] text-slate-400"><Lock size={10}/>Securing</div>
              </div>
            )}
            {err && <div className="flex items-center gap-2 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-800 text-rose-700 dark:text-rose-400 rounded-xl px-4 py-3 text-xs mb-5"><AlertCircle size={14} className="flex-shrink-0"/>{err}</div>}

            {step === 0 && (
              <div>
                <h1 className="text-2xl font-black text-slate-900 dark:text-white mb-1">Welcome back</h1>
                <p className="text-sm text-slate-500 mb-7">Sign in to your GroundConnect account.</p>
                <label className="label">Mobile number</label>
                <input className="input mb-4" value={mobile} onChange={e=>setMobile(e.target.value)} placeholder="+91 98765 00005"/>
                <label className="label">Password</label>
                <div className="relative mb-7">
                  <input className="input pr-11" type={showPwd?'text':'password'} value={pwd} onChange={e=>setPwd(e.target.value)} placeholder="Enter password" onKeyDown={e=>e.key==='Enter'&&s0()}/>
                  <button onClick={()=>setShowPwd(v=>!v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors">{showPwd?<EyeOff size={15}/>:<Eye size={15}/>}</button>
                </div>
                <button onClick={s0} className="btn-primary w-full py-3 text-sm">Continue <ArrowRight size={16}/></button>
                <div className="mt-5 pt-5 border-t border-slate-100 dark:border-slate-800">
                  <p className="text-[10px] text-slate-400 text-center mb-3">Quick demo — pick a role</p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {DEMO_USERS.slice(0,6).map(u=>{const m=ROLE_META[u.role];return(
                      <button key={u.role} onClick={()=>fill(u)} className={`flex items-center gap-2 p-2 rounded-lg text-[10px] border transition-all ${selDemo===u.role?'border-primary-400 bg-primary-50 dark:bg-primary-950/30 text-primary-700':'border-slate-100 dark:border-slate-800 hover:border-slate-200 text-slate-600 dark:text-slate-400'}`}>
                        <span>{m.icon}</span><span className="font-semibold truncate">{m.label}</span>
                      </button>
                    )})}
                  </div>
                </div>
              </div>
            )}

            {step === 1 && (
              <div>
                <h1 className="text-xl font-black text-slate-900 dark:text-white mb-1">Verify your identity</h1>
                <p className="text-sm text-slate-500 mb-4">OTP sent to <span className="font-bold text-slate-700 dark:text-slate-300">{mobile}</span></p>
                <div className="flex items-center gap-2 bg-primary-50 dark:bg-primary-950/40 border border-primary-100 dark:border-primary-900 rounded-xl px-4 py-2.5 text-xs text-primary-700 dark:text-primary-400 mb-2">
                  <Smartphone size={13}/>Enter the one-time code — expires in 5 minutes
                </div>
                <OtpBoxes length={6} onComplete={otp} resetKey={otpReset}/>
                <p className="text-[10px] text-center text-slate-400 mb-1">Any code except <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded font-mono">000000</code></p>
                <Timer onResend={()=>setOtpReset(r=>r+1)}/>
              </div>
            )}

            {step === 2 && (
              <div>
                <h1 className="text-xl font-black text-slate-900 dark:text-white mb-1">Two-factor authentication</h1>
                <p className="text-sm text-slate-500 mb-5">Required for your role. Choose a method.</p>
                <div className="grid grid-cols-2 gap-2.5 mb-5">
                  {MFA_METHODS.map(({id,icon:Icon,label,sub})=>(
                    <button key={id} onClick={()=>setMfa(id)} className={`p-3.5 rounded-xl border-2 text-left transition-all ${mfa===id?'border-primary-500 bg-primary-50 dark:bg-primary-950/30 shadow-glow':'border-slate-100 dark:border-slate-800 hover:border-slate-200 dark:hover:border-slate-700'}`}>
                      <Icon size={18} className={mfa===id?'text-primary-600 dark:text-primary-400':'text-slate-400'}/>
                      <div className={`text-xs font-bold mt-2 ${mfa===id?'text-primary-700 dark:text-primary-300':'text-slate-700 dark:text-slate-300'}`}>{label}</div>
                      <div className="text-[10px] text-slate-400 mt-0.5 leading-snug">{sub}</div>
                    </button>
                  ))}
                </div>
                <button onClick={()=>{setErr('');setStep(3)}} className="btn-primary w-full py-3 text-sm">Continue with {MFA_METHODS.find(m=>m.id===mfa)?.label} <ArrowRight size={16}/></button>
              </div>
            )}

            {step === 3 && (
              <div>
                <h1 className="text-xl font-black text-slate-900 dark:text-white mb-1">Enter MFA code</h1>
                <p className="text-sm text-slate-500 mb-5">{{totp:'Open your authenticator app.',sms:'Code sent to your phone.',email:'Code sent to your email.',backup:'Enter a backup recovery code.'}[mfa]}</p>
                <OtpBoxes length={6} onComplete={mfaCode} resetKey={mfaReset}/>
                <p className="text-[10px] text-center text-slate-400 mb-3">Any code except <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded font-mono">000000</code></p>
                <button onClick={()=>{setErr('');setStep(2)}} className="text-xs text-slate-400 hover:text-primary-600 flex items-center gap-1 mx-auto transition-colors">← Different method</button>
              </div>
            )}
          </div>
          <p className="text-center text-[11px] text-slate-400 mt-4 flex items-center justify-center gap-2">
            <Zap size={11} className="text-primary-500"/>End-to-end encrypted<span className="text-slate-300 dark:text-slate-700">·</span>DPDP compliant<span className="text-slate-300 dark:text-slate-700">·</span>Audit logged
          </p>
        </div>
      </div>
    </div>
  )
}
