import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    // Only log in development — never expose stack traces in production
    if (import.meta.env.DEV) {
      console.error('[GroundConnect] Render error:', error, info)
    }
    // TODO(BE): POST to /api/errors for server-side error tracking (Sentry/Datadog)
  }
  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-900/20 flex items-center justify-center">
          <span className="text-3xl" role="img" aria-label="Warning">⚠️</span>
        </div>
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white mb-1">Something went wrong</h2>
          <p className="text-sm text-slate-500 max-w-sm">This page ran into an unexpected error. Your data is safe.</p>
          {/* Only show error detail in dev — never in production */}
          {import.meta.env.DEV && this.state.error && (
            <code className="block mt-3 text-[11px] font-mono text-rose-600 bg-rose-50 dark:bg-rose-900/20 px-3 py-2 rounded-lg max-w-sm truncate">
              {this.state.error.message}
            </code>
          )}
        </div>
        <button
          onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload() }}
          className="btn-primary btn-sm"
          aria-label="Reload the page">
          Reload page
        </button>
      </div>
    )
  }
}
