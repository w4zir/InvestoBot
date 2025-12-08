import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { runStrategy, getStrategyTemplates, StrategyRunRequest, StrategyRunResponse, TemplateInfo } from '@/api/backend'

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
  const [templates, setTemplates] = useState<TemplateInfo[]>([])
  const [selectedTemplates, setSelectedTemplates] = useState<string[]>([])
  const [enableMultiSource, setEnableMultiSource] = useState(false)
  const [loadingTemplates, setLoadingTemplates] = useState(false)

  useEffect(() => {
    // Fetch templates on mount
    setLoadingTemplates(true)
    getStrategyTemplates()
      .then(setTemplates)
      .catch((err) => {
        console.error('Failed to load templates:', err)
        setError('Failed to load strategy templates')
      })
      .finally(() => setLoadingTemplates(false))
  }, [])

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

      // Validate: need either mission or templates
      if (!mission.trim() && selectedTemplates.length === 0) {
        setError('Please provide either a mission or select at least one predefined strategy')
        setLoading(false)
        return
      }

      const request: StrategyRunRequest = {
        mission: mission.trim() || 'Using predefined strategies',
        context,
        template_ids: selectedTemplates.length > 0 ? selectedTemplates : null,
        enable_multi_source_decision: enableMultiSource,
      }

      const response = await runStrategy(request)
      onSuccess?.(response)
      
      // Reset form on success
      setMission('')
      setUniverse('AAPL,MSFT,GOOGL')
      setDataRange('')
      setExecute(false)
      setSelectedTemplates([])
      setEnableMultiSource(false)
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
          {/* Predefined Strategies Section */}
          <div className="space-y-2">
            <Label>Predefined Strategies (optional)</Label>
            {loadingTemplates ? (
              <p className="text-sm text-muted-foreground">Loading templates...</p>
            ) : templates.length > 0 ? (
              <div className="space-y-2 max-h-48 overflow-y-auto border border-input rounded-md p-3">
                {templates.map((template) => (
                  <div key={template.template_id} className="flex items-start space-x-2">
                    <input
                      type="checkbox"
                      id={`template-${template.template_id}`}
                      checked={selectedTemplates.includes(template.template_id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedTemplates([...selectedTemplates, template.template_id])
                        } else {
                          setSelectedTemplates(selectedTemplates.filter(id => id !== template.template_id))
                        }
                      }}
                      disabled={loading}
                      className="h-4 w-4 mt-1"
                    />
                    <div className="flex-1">
                      <Label htmlFor={`template-${template.template_id}`} className="cursor-pointer font-medium">
                        {template.name}
                      </Label>
                      <p className="text-xs text-muted-foreground">{template.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No templates available</p>
            )}
            <p className="text-xs text-muted-foreground">
              Select one or more predefined strategies. If multiple are selected, they will be combined using AI.
            </p>
          </div>

          {/* Custom Strategy Section */}
          <div className="space-y-2">
            <Label htmlFor="mission">Custom Strategy Mission (optional)</Label>
            <textarea
              id="mission"
              value={mission}
              onChange={(e) => setMission(e.target.value)}
              placeholder="e.g., Find momentum strategies for tech stocks"
              className="w-full min-h-[100px] px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">
              Enter a custom mission to generate strategies using AI. Can be used together with predefined strategies.
            </p>
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

          {/* Advanced Options */}
          <div className="space-y-2 border-t pt-4">
            <Label className="text-sm font-semibold">Advanced Options</Label>
            
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="multiSource"
                checked={enableMultiSource}
                onChange={(e) => setEnableMultiSource(e.target.checked)}
                disabled={loading}
                className="h-4 w-4"
              />
              <Label htmlFor="multiSource" className="cursor-pointer">
                Enable multi-source decision (combine strategy metrics, news, and social media sentiment)
              </Label>
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
          </div>

          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <Button type="submit" disabled={loading || (!mission.trim() && selectedTemplates.length === 0)}>
            {loading ? 'Running...' : 'Run Strategy'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

