import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { runStrategy, StrategyRunRequest, StrategyRunResponse } from '@/api/backend'

interface StrategyRunFormProps {
  onSuccess?: (response: StrategyRunResponse) => void
  onError?: (error: Error) => void
}

export default function StrategyRunForm({ onSuccess, onError }: StrategyRunFormProps) {
  const [mission, setMission] = useState('')
  const [universe, setUniverse] = useState('AAPL,MSFT,GOOGL')
  const [dataRange, setDataRange] = useState('')
  const [execute, setExecute] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const context: Record<string, any> = {}
      
      if (universe.trim()) {
        context.universe = universe.split(',').map(s => s.trim()).filter(s => s.length > 0)
      }
      
      if (dataRange.trim()) {
        context.data_range = dataRange.trim()
      }
      
      if (execute) {
        context.execute = true
      }

      const request: StrategyRunRequest = {
        mission: mission.trim(),
        context,
      }

      const response = await runStrategy(request)
      onSuccess?.(response)
      
      // Reset form on success
      setMission('')
      setUniverse('AAPL,MSFT,GOOGL')
      setDataRange('')
      setExecute(false)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to run strategy'
      setError(errorMessage)
      onError?.(err instanceof Error ? err : new Error(errorMessage))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Run Strategy</CardTitle>
        <CardDescription>
          Define a mission and context to generate and backtest trading strategies
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="mission">Mission</Label>
            <textarea
              id="mission"
              value={mission}
              onChange={(e) => setMission(e.target.value)}
              placeholder="e.g., Find momentum strategies for tech stocks"
              required
              className="w-full min-h-[100px] px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="universe">Universe (comma-separated symbols)</Label>
            <Input
              id="universe"
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              placeholder="AAPL,MSFT,GOOGL"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="dataRange">Data Range (optional, format: YYYY-MM-DD:YYYY-MM-DD)</Label>
            <Input
              id="dataRange"
              value={dataRange}
              onChange={(e) => setDataRange(e.target.value)}
              placeholder="2024-01-01:2024-12-31"
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to use default lookback period
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="execute"
              checked={execute}
              onChange={(e) => setExecute(e.target.checked)}
              disabled={loading}
              className="h-4 w-4"
            />
            <Label htmlFor="execute" className="cursor-pointer">
              Execute trades (paper trading)
            </Label>
          </div>

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <Button type="submit" disabled={loading || !mission.trim()}>
            {loading ? 'Running...' : 'Run Strategy'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

