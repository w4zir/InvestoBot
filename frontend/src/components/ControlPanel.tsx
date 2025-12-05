import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  getKillSwitchStatus,
  enableKillSwitch,
  disableKillSwitch,
  cancelAllOrders,
  getOpenOrders,
  getSchedulerStatus,
  KillSwitchStatus,
  OpenOrdersResponse,
  SchedulerStatus,
} from '@/api/backend'
import { RefreshCw, AlertTriangle, CheckCircle2, XCircle, Power } from 'lucide-react'

export default function ControlPanel() {
  const [killSwitchStatus, setKillSwitchStatus] = useState<KillSwitchStatus | null>(null)
  const [openOrders, setOpenOrders] = useState<OpenOrdersResponse | null>(null)
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const fetchAllStatus = async () => {
    try {
      setError(null)
      // Use Promise.allSettled to handle partial failures gracefully
      const results = await Promise.allSettled([
        getKillSwitchStatus(),
        getOpenOrders(),
        getSchedulerStatus(),
      ])
      
      // Handle kill switch status
      if (results[0].status === 'fulfilled') {
        setKillSwitchStatus(results[0].value)
      } else {
        console.error('Failed to fetch kill switch status:', results[0].reason)
      }
      
      // Handle open orders (may fail if broker unavailable, but that's OK)
      if (results[1].status === 'fulfilled') {
        setOpenOrders(results[1].value)
      } else {
        console.error('Failed to fetch open orders:', results[1].reason)
        // Set empty orders if fetch fails
        setOpenOrders({ count: 0, orders: [], broker_available: false, message: 'Failed to fetch orders' })
      }
      
      // Handle scheduler status
      if (results[2].status === 'fulfilled') {
        setSchedulerStatus(results[2].value)
      } else {
        console.error('Failed to fetch scheduler status:', results[2].reason)
      }
      
      // Only show error if all requests failed
      const failedCount = results.filter(r => r.status === 'rejected').length
      if (failedCount === results.length) {
        setError('Failed to fetch control status. Please check backend connection.')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch control status'
      setError(errorMessage)
      console.error('Error fetching control status:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAllStatus()
  }, [])

  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      fetchAllStatus()
    }, 10000) // Refresh every 10 seconds

    return () => clearInterval(interval)
  }, [autoRefresh])

  const handleEnableKillSwitch = async () => {
    const reason = prompt('Enter reason for enabling kill switch (optional):') || 'Manual activation'
    setActionLoading('enable-kill-switch')
    try {
      await enableKillSwitch(reason)
      await fetchAllStatus()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to enable kill switch'
      setError(errorMessage)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDisableKillSwitch = async () => {
    setActionLoading('disable-kill-switch')
    try {
      await disableKillSwitch()
      await fetchAllStatus()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to disable kill switch'
      setError(errorMessage)
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelAllOrders = async () => {
    if (!confirm('Are you sure you want to cancel all open orders? This action cannot be undone.')) {
      return
    }
    setActionLoading('cancel-orders')
    try {
      const result = await cancelAllOrders()
      await fetchAllStatus()
      if (result.success === false || result.errors.length > 0) {
        // Show message from backend if broker is unavailable
        if (result.message && result.message.includes('Broker unavailable')) {
          setError(result.message)
        } else if (result.errors.length > 0) {
          setError(`Some orders failed to cancel: ${result.errors.join(', ')}`)
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to cancel orders'
      setError(errorMessage)
    } finally {
      setActionLoading(null)
    }
  }

  if (loading && !killSwitchStatus) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center py-8">
            <p className="text-muted-foreground">Loading control panel...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Kill Switch */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Power className="h-5 w-5" />
                Kill Switch
              </CardTitle>
              <CardDescription>
                Emergency stop for all strategy executions
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchAllStatus}
              disabled={loading || actionLoading !== null}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
            <div className="flex items-center gap-3">
              {killSwitchStatus?.enabled ? (
                <>
                  <XCircle className="h-6 w-6 text-destructive" />
                  <div>
                    <p className="font-semibold text-destructive">Kill Switch ENABLED</p>
                    <p className="text-sm text-muted-foreground">
                      All strategy executions are blocked
                    </p>
                    {killSwitchStatus.reason && (
                      <p className="text-sm text-muted-foreground mt-1">
                        Reason: {killSwitchStatus.reason}
                      </p>
                    )}
                    {killSwitchStatus.activated_at && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Activated: {new Date(killSwitchStatus.activated_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-6 w-6 text-green-600" />
                  <div>
                    <p className="font-semibold text-green-600">Kill Switch DISABLED</p>
                    <p className="text-sm text-muted-foreground">
                      Strategy executions are allowed
                    </p>
                  </div>
                </>
              )}
            </div>
            <div className="flex gap-2">
              {killSwitchStatus?.enabled ? (
                <Button
                  variant="default"
                  onClick={handleDisableKillSwitch}
                  disabled={actionLoading !== null}
                >
                  {actionLoading === 'disable-kill-switch' ? 'Disabling...' : 'Disable Kill Switch'}
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  onClick={handleEnableKillSwitch}
                  disabled={actionLoading !== null}
                >
                  {actionLoading === 'enable-kill-switch' ? 'Enabling...' : 'Enable Kill Switch'}
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Open Orders */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Open Orders</CardTitle>
              <CardDescription>
                {openOrders?.count ?? 0} open order{openOrders?.count !== 1 ? 's' : ''}
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
                onClick={fetchAllStatus}
                disabled={loading || actionLoading !== null}
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {openOrders && openOrders.broker_available === false ? (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {openOrders.message || 'Broker is not configured or unavailable. Please configure Alpaca API keys in backend/.env to view open orders.'}
              </AlertDescription>
            </Alert>
          ) : openOrders && openOrders.count > 0 ? (
            <>
              <div className="space-y-2">
                {openOrders.orders.map((order, idx) => (
                  <div key={order.id || idx} className="p-3 bg-muted border rounded-md">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant={order.side === 'buy' ? 'default' : 'secondary'}>
                          {order.side?.toUpperCase() || 'UNKNOWN'}
                        </Badge>
                        <span className="font-semibold">{order.symbol || 'N/A'}</span>
                      </div>
                      <div className="text-sm">
                        {order.qty || order.quantity || 'N/A'} @ ${order.limit_price || order.price || 'N/A'}
                      </div>
                    </div>
                    {order.status && (
                      <div className="text-xs text-muted-foreground mt-1">
                        Status: {order.status}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <Button
                variant="destructive"
                onClick={handleCancelAllOrders}
                disabled={actionLoading !== null}
                className="w-full"
              >
                {actionLoading === 'cancel-orders' ? 'Cancelling...' : 'Cancel All Orders'}
              </Button>
            </>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>No open orders</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Scheduler Status */}
      <Card>
        <CardHeader>
          <CardTitle>Scheduler Status</CardTitle>
          <CardDescription>Active strategy runs and scheduler information</CardDescription>
        </CardHeader>
        <CardContent>
          {schedulerStatus ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
                <div>
                  <p className="font-semibold">Active Runs</p>
                  <p className="text-sm text-muted-foreground">
                    {schedulerStatus.active_run_count} active run{schedulerStatus.active_run_count !== 1 ? 's' : ''}
                  </p>
                </div>
                <Badge variant={schedulerStatus.active_run_count > 0 ? 'default' : 'secondary'}>
                  {schedulerStatus.active_run_count}
                </Badge>
              </div>
              {schedulerStatus.active_runs.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Run IDs:</p>
                  <div className="flex flex-wrap gap-2">
                    {schedulerStatus.active_runs.map((runId) => (
                      <Badge key={runId} variant="outline">
                        {runId}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Kill Switch:</span>
                <Badge variant={schedulerStatus.kill_switch_enabled ? 'destructive' : 'default'}>
                  {schedulerStatus.kill_switch_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>Unable to load scheduler status</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

