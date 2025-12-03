import { useState, useEffect } from 'react'
import { supabase } from '../api/supabase'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import StrategyRunForm from '@/components/StrategyRunForm'
import BacktestVisualization from '@/components/BacktestVisualization'
import LivePositions from '@/components/LivePositions'
import ControlPanel from '@/components/ControlPanel'
import { StrategyRunResponse, CandidateResult } from '@/api/backend'

export default function Dashboard() {
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [strategyRunResponse, setStrategyRunResponse] = useState<StrategyRunResponse | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateResult | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null)
      setLoading(false)
    })

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    return () => { sub.subscription.unsubscribe() }
  }, [])

  const handleStrategyRunSuccess = (response: StrategyRunResponse) => {
    setStrategyRunResponse(response)
    // Auto-select first candidate if available
    if (response.candidates.length > 0) {
      setSelectedCandidate(response.candidates[0])
    }
  }

  const handleStrategyRunError = (error: Error) => {
    console.error('Strategy run error:', error)
    // Error is already handled in StrategyRunForm
  }

  if (loading) {
    return (
      <main className="max-w-7xl mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </main>
    )
  }

  return (
    <main className="max-w-7xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Trading Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome, {user?.email ?? 'User'}
        </p>
      </div>

      <Tabs defaultValue="strategy" className="space-y-6">
        <TabsList>
          <TabsTrigger value="strategy">Strategy Runner</TabsTrigger>
          <TabsTrigger value="results">Backtest Results</TabsTrigger>
          <TabsTrigger value="positions">Live Positions</TabsTrigger>
          <TabsTrigger value="control">Control Panel</TabsTrigger>
        </TabsList>

        <TabsContent value="strategy" className="space-y-6">
          <StrategyRunForm
            onSuccess={handleStrategyRunSuccess}
            onError={handleStrategyRunError}
          />
        </TabsContent>

        <TabsContent value="results" className="space-y-6">
          {!strategyRunResponse ? (
            <Card>
              <CardContent className="p-6">
                <div className="text-center py-8">
                  <p className="text-muted-foreground">
                    No strategy run results yet. Run a strategy from the Strategy Runner tab.
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              {/* Strategy Run Summary */}
              <Card>
                <CardHeader>
                  <CardTitle>Strategy Run: {strategyRunResponse.run_id}</CardTitle>
                  <CardDescription>
                    Mission: {strategyRunResponse.mission}
                  </CardDescription>
                  <CardDescription>
                    {strategyRunResponse.candidates.length} candidate{strategyRunResponse.candidates.length !== 1 ? 's' : ''} generated
                    {' • '}
                    {new Date(strategyRunResponse.created_at).toLocaleString()}
                  </CardDescription>
                </CardHeader>
              </Card>

              {/* Candidate Selector */}
              {strategyRunResponse.candidates.length > 1 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Select Candidate</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {strategyRunResponse.candidates.map((candidate, idx) => (
                        <button
                          key={idx}
                          onClick={() => setSelectedCandidate(candidate)}
                          className={`px-4 py-2 rounded-md border transition-colors ${
                            selectedCandidate === candidate
                              ? 'bg-primary text-primary-foreground border-primary'
                              : 'bg-background hover:bg-accent border-input'
                          }`}
                        >
                          {candidate.strategy.name || candidate.strategy.strategy_id}
                        </button>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Backtest Visualization */}
              {selectedCandidate ? (
                <BacktestVisualization candidate={selectedCandidate} />
              ) : strategyRunResponse.candidates.length > 0 ? (
                <BacktestVisualization candidate={strategyRunResponse.candidates[0]} />
              ) : (
                <Card>
                  <CardContent className="p-6">
                    <div className="text-center py-8">
                      <p className="text-muted-foreground">No candidates generated</p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="positions" className="space-y-6">
          <LivePositions />
        </TabsContent>

        <TabsContent value="control" className="space-y-6">
          <ControlPanel />
        </TabsContent>
      </Tabs>
    </main>
  )
}
