/**
 * DiffusionText — renders real denoising steps from Mercury 2.
 *
 * When receiving real diffusion data from the backend, this component
 * simply displays the current denoised state as-is. The text you see
 * IS the model's actual intermediate output at each denoising step —
 * noise resolving into coherent language through discrete diffusion.
 *
 * Falls back to a simple crossfade for non-diffusion providers.
 */

interface DiffusionTextProps {
  /** The current text to display (updated each denoising step) */
  content: string;
  /** Whether this message is still being diffused */
  active: boolean;
}

export function DiffusionText({ content, active }: DiffusionTextProps) {
  return (
    <span className="inline">
      {content}
      {active && (
        <span className="inline-block w-1.5 h-3 ml-0.5 bg-purple-400/80 animate-pulse rounded-sm align-middle" />
      )}
    </span>
  );
}
