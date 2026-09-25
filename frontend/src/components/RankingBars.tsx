interface RankingBreakdown {
  ki_relevanz: number
  dringlichkeit: number
  profil_uebereinstimmung: number
  aktualitaet: number
}

const labels: { key: keyof RankingBreakdown; label: string }[] = [
  { key: 'ki_relevanz', label: 'KI-Relevanz' },
  { key: 'dringlichkeit', label: 'Dringlichkeit' },
  { key: 'profil_uebereinstimmung', label: 'Profil-Übereinstimmung' },
  { key: 'aktualitaet', label: 'Aktualität' },
]

export function RankingBars({ breakdown }: { breakdown: RankingBreakdown }) {
  return (
    <div className="flex flex-col gap-2.5">
      {labels.map(({ key, label }) => {
        const value = Math.max(0, Math.min(1, breakdown[key]))
        return (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between text-xs text-ink-muted">
              <span>{label}</span>
              <span className="tabular-nums">{(value * 100).toFixed(0)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
              <div className="h-full rounded-full bg-brand" style={{ width: `${value * 100}%` }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
