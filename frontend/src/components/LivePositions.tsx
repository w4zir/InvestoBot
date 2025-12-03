import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getAccountStatus, AccountStatus, PortfolioPosition } from '@/api/backend'
import { RefreshCw } from 'lucide-react'

export default function LivePositions() {
  const [accountStatus, setAccountStatus] = useState<AccountStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const fetchAccountStatus = async () => {
    try {
      setError(null)
      const status = await getAccountStatus()
      setAccountStatus(status)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch account status'
      setError(errorMessage)
      console.error('Error fetching account status:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAccountStatus()
  }, [])

  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      fetchAccountStatus()
    }, 10000) // Refresh every 10 seconds

    return () => clearInterval(interval)
  }, [autoRefresh])

  if (loading && !accountStatus) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center py-8">
            <p className="text-muted-foreground">Loading account status...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error && !accountStatus) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Account Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
            <p className="text-sm text-destructive">{error}</p>
          </div>
          <Button onClick={fetchAccountStatus} className="mt-4">
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (!accountStatus) {
    return null
  }

  const { account, portfolio } = accountStatus
  const accountEquity = parseFloat(account.equity || account.cash || '0')
  const accountCash = parseFloat(account.cash || '0')
  const buyingPower = parseFloat(account.buying_power || account.cash || '0')
  const portfolioValue = portfolio.cash + portfolio.positions.reduce((sum, pos) => {
    // Estimate current value (we don't have current price, so use avg entry price as approximation)
    // In a real implementation, you'd fetch current market prices
    return sum + (pos.quantity * pos.average_price)
  }, 0)

  // Calculate total P&L for all positions
  // Note: This is an approximation since we don't have current market prices
  // In production, you'd fetch current prices from market data
  const totalPnL = portfolio.positions.reduce((sum, pos) => {
    // Using avg entry price as current price approximation
    const currentValue = pos.quantity * pos.average_price
    const costBasis = pos.quantity * pos.average_price
    return sum + (currentValue - costBasis) // Will be 0 with this approximation
  }, 0)

  return (
    <div className="space-y-6">
      {/* Account Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Account Equity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">${accountEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Cash</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">${accountCash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Buying Power</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">${buyingPower.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          </CardContent>
        </Card>
      </div>

      {/* Positions */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Positions</CardTitle>
              <CardDescription>
                {portfolio.positions.length} open position{portfolio.positions.length !== 1 ? 's' : ''}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="h-4 w-4"
                />
                Auto-refresh
              </label>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchAccountStatus}
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {portfolio.positions.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground">No open positions</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Symbol</th>
                    <th className="text-right p-2">Quantity</th>
                    <th className="text-right p-2">Avg Entry Price</th>
                    <th className="text-right p-2">Current Price</th>
                    <th className="text-right p-2">Market Value</th>
                    <th className="text-right p-2">P&L</th>
                    <th className="text-right p-2">P&L %</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.positions.map((pos, idx) => {
                    // Note: In production, you'd fetch current market price
                    // For now, we'll use avg entry price as approximation
                    const currentPrice = pos.average_price
                    const marketValue = pos.quantity * currentPrice
                    const costBasis = pos.quantity * pos.average_price
                    const pnl = marketValue - costBasis
                    const pnlPercent = costBasis > 0 ? (pnl / costBasis) * 100 : 0
                    const pnlColor = pnl >= 0 ? 'text-green-600' : 'text-red-600'

                    return (
                      <tr key={idx} className="border-b hover:bg-muted/50">
                        <td className="p-2 font-semibold">{pos.symbol}</td>
                        <td className="p-2 text-right">{pos.quantity.toFixed(2)}</td>
                        <td className="p-2 text-right">${pos.average_price.toFixed(2)}</td>
                        <td className="p-2 text-right">${currentPrice.toFixed(2)}</td>
                        <td className="p-2 text-right">${marketValue.toFixed(2)}</td>
                        <td className={`p-2 text-right font-semibold ${pnlColor}`}>
                          {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                        </td>
                        <td className={`p-2 text-right font-semibold ${pnlColor}`}>
                          {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
                {portfolio.positions.length > 0 && (
                  <tfoot>
                    <tr className="border-t font-semibold">
                      <td className="p-2">Total</td>
                      <td className="p-2 text-right">
                        {portfolio.positions.reduce((sum, pos) => sum + pos.quantity, 0).toFixed(2)}
                      </td>
                      <td className="p-2"></td>
                      <td className="p-2"></td>
                      <td className="p-2 text-right">
                        ${portfolio.positions.reduce((sum, pos) => sum + (pos.quantity * pos.average_price), 0).toFixed(2)}
                      </td>
                      <td className={`p-2 text-right ${totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
                      </td>
                      <td className="p-2"></td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Additional Account Info */}
      <Card>
        <CardHeader>
          <CardTitle>Account Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Account Number</p>
              <p className="font-semibold">{account.account_number || 'N/A'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Status</p>
              <Badge variant={account.status === 'ACTIVE' ? 'default' : 'secondary'}>
                {account.status || 'N/A'}
              </Badge>
            </div>
            <div>
              <p className="text-muted-foreground">Pattern Day Trader</p>
              <p className="font-semibold">{account.pattern_day_trader ? 'Yes' : 'No'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Trading Blocked</p>
              <p className="font-semibold">{account.trading_blocked ? 'Yes' : 'No'}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

