import { useState } from 'react'
import { ChevronRight, ChevronDown, Users, ClipboardList, AlertTriangle } from 'lucide-react'
import { StatusBadge } from './UI'

const STATUS_BG = { active:'bg-emerald-500', orphaned:'bg-rose-500 animate-pulse', dark:'bg-amber-400' }

function Node({ node, depth=0, selected, onSelect, showActions, onAdd }) {
  const [exp, setExp] = useState(depth < 2)
  const hasKids = node.children?.length > 0
  const indent = depth * 20
  return (
    <div>
      <div
        style={{ marginLeft: indent }}
        onClick={() => { hasKids && setExp(e=>!e); onSelect && onSelect(node) }}
        className={`flex items-center gap-2 p-2.5 rounded-xl mb-1 transition-all cursor-pointer border ${
          selected?.id === node.id
            ? 'border-primary-300 dark:border-primary-700 bg-primary-50 dark:bg-primary-950/40'
            : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:border-slate-100 dark:hover:border-slate-800'
        }`}>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {hasKids
            ? (exp ? <ChevronDown size={13} className="text-slate-400"/> : <ChevronRight size={13} className="text-slate-400"/>)
            : <div className="w-3.5"/>}
          <div className={`w-2.5 h-2.5 rounded-full ${STATUS_BG[node.status] || 'bg-slate-300'}`}/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">{node.name}</span>
            {node.status !== 'active' && <StatusBadge status={node.status} size="xs"/>}
          </div>
          <div className="text-[10px] text-slate-400 truncate mt-0.5">
            {node.responsible || <span className="text-rose-500 font-semibold flex items-center gap-1"><AlertTriangle size={9}/>No responsible person</span>}
          </div>
        </div>
        <div className="flex gap-3 text-[10px] text-slate-400 flex-shrink-0">
          <span className="flex items-center gap-0.5"><Users size={9}/>{node.members}</span>
          <span className="flex items-center gap-0.5"><ClipboardList size={9}/>{node.tasks}</span>
        </div>
      </div>
      {exp && hasKids && (
        <div className={`ml-${indent > 0 ? 4 : 0} pl-4 border-l border-slate-100 dark:border-slate-800`} style={{marginLeft: indent + 8, paddingLeft: 12, borderLeft:'2px solid', borderColor: 'rgba(148,163,184,0.15)'}}>
          {node.children.map(c => <Node key={c.id} node={c} depth={depth+1} selected={selected} onSelect={onSelect} showActions={showActions} onAdd={onAdd}/>)}
        </div>
      )}
    </div>
  )
}

export default function OrgTree({ tree, selected, onSelect, showActions, onAdd }) {
  return <Node node={tree} depth={0} selected={selected} onSelect={onSelect} showActions={showActions} onAdd={onAdd}/>
}
