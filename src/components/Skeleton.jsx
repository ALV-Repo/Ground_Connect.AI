export function SkeletonLine({ width = 'w-full', height = 'h-4' }) {
  return <div className={`${width} ${height} rounded-lg bg-slate-100 dark:bg-slate-800 animate-pulse`} />
}
export function SkeletonKpi() {
  return (
    <div className="card p-4 space-y-3">
      <div className="flex justify-between">
        <SkeletonLine width="w-24" height="h-3" />
        <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 animate-pulse" />
      </div>
      <SkeletonLine width="w-20" height="h-7" />
      <SkeletonLine width="w-32" height="h-2.5" />
    </div>
  )
}
export function SkeletonTable({ rows = 5, cols = 5 }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
        <SkeletonLine width="w-32" height="h-4" />
      </div>
      <div className="divide-y divide-slate-50 dark:divide-slate-800">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div key={`skel-row-${rowIdx}`} className="flex items-center gap-4 px-4 py-3">
            {Array.from({ length: cols }).map((_, colIdx) => (
              <SkeletonLine key={`skel-col-${colIdx}`} width={colIdx === 1 ? 'flex-1' : 'w-16'} height="h-3" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
export function SkeletonDashboard() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">{[...Array(4)].map((_,i) => <SkeletonKpi key={`kpi-${i}`}/>)}</div>
      <div className="grid grid-cols-2 gap-4">
        {[...Array(2)].map((_,i) => ( // key below
          <div key={`chart-${i}`} className="card p-5 h-48 flex flex-col gap-3">
            <SkeletonLine width="w-32" height="h-4"/>
            <div className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-xl animate-pulse"/>
          </div>
        ))}
      </div>
      <SkeletonTable rows={4} cols={6}/>
    </div>
  )
}
