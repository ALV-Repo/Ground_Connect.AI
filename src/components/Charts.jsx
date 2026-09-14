import { BarChart,Bar,AreaChart,Area,LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer,PieChart,Pie,Cell,RadialBarChart,RadialBar } from 'recharts'
import { ChartTip } from './UI'

const ax = { fontSize:10, fill:'#94a3b8' }
const grid = { strokeDasharray:'3 3', stroke:'rgba(0,0,0,0.04)', vertical:false }
const gridH = { strokeDasharray:'3 3', stroke:'rgba(0,0,0,0.04)', horizontal:false }
const axStyle = { axisLine:false, tickLine:false }

export function TaskBarChart({ data, height=200 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} barCategoryGap="35%" barGap={2}>
        <CartesianGrid {...grid}/>
        <XAxis dataKey="month" tick={ax} {...axStyle}/>
        <YAxis tick={ax} {...axStyle}/>
        <Tooltip content={<ChartTip/>}/>
        <Bar dataKey="completed" name="Completed" fill="#4f46e5" radius={[3,3,0,0]} maxBarSize={22}/>
        <Bar dataKey="overdue"   name="Overdue"   fill="#f43f5e" radius={[3,3,0,0]} maxBarSize={22}/>
        <Bar dataKey="blocked"   name="Blocked"   fill="#f59e0b" radius={[3,3,0,0]} maxBarSize={22}/>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function MsgAreaChart({ data, height=200 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="gSent" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.15}/>
            <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid {...grid}/>
        <XAxis dataKey="month" tick={ax} {...axStyle}/>
        <YAxis tick={ax} {...axStyle}/>
        <Tooltip content={<ChartTip/>}/>
        <Area type="monotone" dataKey="sent"      name="Sent"      stroke="#4f46e5" strokeWidth={2} fill="url(#gSent)" dot={false}/>
        <Area type="monotone" dataKey="delivered" name="Delivered" stroke="#10b981" strokeWidth={2} fill="none" dot={false}/>
        <Area type="monotone" dataKey="read"      name="Read"      stroke="#8b5cf6" strokeWidth={2} fill="none" dot={false}/>
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function CitizenBarChart({ data, height=190 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" barCategoryGap="28%" barGap={2}>
        <CartesianGrid {...gridH}/>
        <XAxis type="number" tick={ax} {...axStyle}/>
        <YAxis dataKey="category" type="category" tick={ax} {...axStyle} width={85}/>
        <Tooltip content={<ChartTip/>}/>
        <Bar dataKey="open"      name="Open"      fill="#4f46e5" radius={[0,3,3,0]} maxBarSize={12}/>
        <Bar dataKey="resolved"  name="Resolved"  fill="#10b981" radius={[0,3,3,0]} maxBarSize={12}/>
        <Bar dataKey="escalated" name="Escalated" fill="#f43f5e" radius={[0,3,3,0]} maxBarSize={12}/>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function EvidenceDonut({ data, height=145 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={42} outerRadius={60} dataKey="value" paddingAngle={3}>
          {data.map((e,i)=><Cell key={`chart-item-${i}`} fill={e.color}/>)}
        </Pie>
        <Tooltip formatter={v=>`${v}%`}/>
      </PieChart>
    </ResponsiveContainer>
  )
}

export function LineMetricChart({ data, lines, height=190 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid {...grid}/>
        <XAxis dataKey="month" tick={ax} {...axStyle}/>
        <YAxis tick={ax} {...axStyle}/>
        <Tooltip content={<ChartTip/>}/>
        {lines.map(l=><Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={2} dot={false}/>)}
      </LineChart>
    </ResponsiveContainer>
  )
}

export function ChartLegend({ items }) {
  return (
    <div className="flex gap-4 flex-wrap mb-3">
      {items.map(([color,label])=>(
        <span key={label} className="flex items-center gap-1.5 text-[11px] text-slate-500">
          <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{background:color}}/>{label}
        </span>
      ))}
    </div>
  )
}

export function RadialProgress({ value, max=100, color='#4f46e5', size=120, label, sublabel }) {
  const data = [{ value, fill: color }, { value: max-value, fill: '#f1f5f9' }]
  return (
    <div className="flex flex-col items-center">
      <div style={{width:size,height:size,position:'relative'}}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={data} startAngle={90} endAngle={-270}>
            <RadialBar dataKey="value" cornerRadius={4}/>
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-xl font-black" style={{color}}>{value}%</div>
          {sublabel && <div className="text-[10px] text-slate-400">{sublabel}</div>}
        </div>
      </div>
      {label && <div className="text-xs text-slate-500 mt-1 text-center">{label}</div>}
    </div>
  )
}
