// Page entry point for #/live: pipeline board plus the claim-vs-truth "Result so far" panel.
import { useState } from 'react'
import { ClaimTruth } from '../screens/ClaimTruth'
import { GateBoard } from '../screens/GateBoard'
import type { ScreenProps } from '../types'
import { PageHeader } from '../ui'

export default function Live(p: ScreenProps) {
  const [done, setDone] = useState(0)
  return (
    <>
      <PageHeader title="Live run" subtitle="Stages and gates light up as the pipeline works, streamed from the API." />
      <div className="lv-page">
        <GateBoard {...p} onDone={() => setDone((d) => d + 1)} />
        {p.runId && <ClaimTruth {...p} refreshKey={done} />}
      </div>
    </>
  )
}
