import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { BacktestResult, RiskAssessment, CandidateResult } from '@/api/backend'

interface BacktestVisualizationProps {
  candidate: CandidateResult
}

export default function BacktestVisualization({ candidate }: BacktestVisualizationProps) {
  const { backtest, risk } = candidate

  // Format equity curve data for recharts
  const equityData = useMemo(() => {
    if (!backtest.equity_curve || backtest.equity_curve.length === 0) {
      return []
    }
    return backtest.equity_curve.map(point => ({
      timestamp: new Date(point.timestamp).toLocaleDateString(),
      value: point.value,
      date: new Date(point.timestamp),
    })).sort((a, b) => a.date.getTime() - b.date.getTime())
  }, [backtest.equity_curve])

  // Format metrics
  const metrics = backtest.metrics
  const totalReturn = metrics.total_return ?? 0
  const returnColor = totalReturn >= 0 ? 'text-green-600' : 'text-red-600'

  return (
    <div className="space-y-6">
      {/* Strategy Info */}
      <Card>
        <CardHeader>
          <CardTitle>{backtest.strategy.name || backtest.strategy.strategy_id}</CardTitle>
          <CardDescription>{backtest.strategy.description || 'No description'}</CardDescription>
        </CardHeader>
      </Card>

      {/* Equity Curve Chart */}
      {equityData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Equity Curve</CardTitle>
            <CardDescription>Portfolio value over time</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={equityData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="timestamp" 
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis 
                  label={{ value: 'Portfolio Value ($)', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip 
                  formatter={(value: number) => [`$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, 'Value']}
                />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#8884d8" 
                  strokeWidth={2}
                  dot={false}
                  name="Portfolio Value"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Sharpe Ratio</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{metrics.sharpe.toFixed(2)}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Max Drawdown</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-red-600">
              {(metrics.max_drawdown * 100).toFixed(2)}%
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Total Return</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${returnColor}`}>
              {(totalReturn * 100).toFixed(2)}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Risk Violations */}
      {risk && risk.violations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Risk Violations</CardTitle>
            <CardDescription>Risk checks that failed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {risk.violations.map((violation, idx) => (
                <div key={idx} className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                  <p className="text-sm text-destructive">{violation}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Approved Trades */}
      {risk && risk.approved_trades.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Approved Trades</CardTitle>
            <CardDescription>{risk.approved_trades.length} trades passed risk checks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {risk.approved_trades.map((trade, idx) => (
                <div key={idx} className="p-3 bg-green-50 border border-green-200 rounded-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <Badge variant={trade.side === 'buy' ? 'default' : 'secondary'}>
                        {trade.side.toUpperCase()}
                      </Badge>
                      <span className="ml-2 font-semibold">{trade.symbol}</span>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {trade.quantity.toFixed(2)} @ {trade.type}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Trade Log */}
      {backtest.trade_log.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Trade Log</CardTitle>
            <CardDescription>{backtest.trade_log.length} trades executed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Timestamp</th>
                    <th className="text-left p-2">Symbol</th>
                    <th className="text-left p-2">Side</th>
                    <th className="text-right p-2">Quantity</th>
                    <th className="text-right p-2">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.trade_log.map((trade, idx) => (
                    <tr key={idx} className="border-b">
                      <td className="p-2">
                        {new Date(trade.timestamp).toLocaleString()}
                      </td>
                      <td className="p-2 font-semibold">{trade.symbol}</td>
                      <td className="p-2">
                        <Badge variant={trade.side === 'buy' ? 'default' : 'secondary'}>
                          {trade.side.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="p-2 text-right">{trade.quantity.toFixed(2)}</td>
                      <td className="p-2 text-right">${trade.price.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Execution Info */}
      {candidate.execution_fills.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Execution Fills</CardTitle>
            <CardDescription>{candidate.execution_fills.length} orders filled</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {candidate.execution_fills.map((fill, idx) => (
                <div key={idx} className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <Badge variant={fill.side === 'buy' ? 'default' : 'secondary'}>
                        {fill.side.toUpperCase()}
                      </Badge>
                      <span className="ml-2 font-semibold">{fill.symbol}</span>
                    </div>
                    <div className="text-sm">
                      {fill.quantity.toFixed(2)} @ ${fill.price.toFixed(2)}
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {new Date(fill.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {candidate.execution_error && (
        <Card>
          <CardHeader>
            <CardTitle>Execution Error</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm text-destructive">{candidate.execution_error}</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

