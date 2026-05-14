import { Component } from 'react';
import type { ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[JetWatch ErrorBoundary]', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] p-8">
          <div className="glass-card p-xl text-center border-accent-red/30 max-w-lg">
            <h3 className="sp-h5 text-accent-red mb-sm">Erreur d'affichage</h3>
            <p className="sp-caption text-muted-foreground mb-md">
              {this.props.fallbackMessage || "Un composant a rencontré une erreur inattendue."}
            </p>
            <p className="sp-micro text-muted-foreground font-mono mb-md bg-black/40 p-sm rounded">
              {this.state.error?.message}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-md py-sm bg-accent-blue hover:bg-blue-600 text-white sp-body-semibold rounded-lg transition-colors"
            >
              Réessayer
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
