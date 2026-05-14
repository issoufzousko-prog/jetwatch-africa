import { type ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface InvestigationButtonProps {
  children: ReactNode;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  variant?: "solid" | "soft" | "outlined" | "plain";
}

export default function InvestigationButton({
  children,
  onClick,
  disabled = false,
  loading = false,
  className = "",
  variant = "solid",
}: InvestigationButtonProps) {
  
  const baseStyles = "relative inline-flex items-center justify-center font-medium transition-colors duration-200 rounded-lg px-4 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-accent-blue disabled:opacity-50 disabled:cursor-not-allowed";
  
  const variantStyles = {
    solid: "bg-accent-blue text-white hover:bg-blue-600 active:bg-blue-700",
    soft: "bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 active:bg-accent-blue/30",
    outlined: "border border-accent-blue text-accent-blue hover:bg-accent-blue/5 active:bg-accent-blue/10",
    plain: "text-accent-blue hover:bg-accent-blue/10 active:bg-accent-blue/20",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {loading && (
        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
      )}
      <span className={loading ? "opacity-90" : ""}>{children}</span>
    </button>
  );
}
