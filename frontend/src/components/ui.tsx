import type { ReactNode } from 'react'

/* Shared Signal Monitor primitives — one place to keep the wire-terminal
   look consistent across all views. */

// Terminal-style form controls: dark well, hairline border, mono data.
export const inputCls =
  'bg-gray-900 border border-gray-600 text-gray-100 rounded-sm px-2.5 py-1.5 text-sm ' +
  'outline-none focus:border-blue-500 transition-colors'

export const selectCls = inputCls + ' font-mono'

export const btnPrimary =
  'bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 ' +
  'text-gray-950 font-medium px-4 py-1.5 rounded-sm text-sm transition-colors ' +
  'inline-flex items-center gap-1.5'

export const btnGhost =
  'bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-200 ' +
  'px-3 py-1.5 rounded-sm text-sm transition-colors'

// A titled panel. `eyebrow` is the mono tag; `right` holds controls/readouts.
export function Panel({
  eyebrow,
  right,
  children,
  className = '',
  bodyClass = 'p-4',
}: {
  eyebrow?: string
  right?: ReactNode
  children: ReactNode
  className?: string
  bodyClass?: string
}) {
  return (
    <section className={`bg-gray-800 border border-gray-700 rounded-sm ${className}`}>
      {(eyebrow || right) && (
        <div className="flex items-center justify-between gap-2 px-4 py-2 border-b border-gray-700">
          {eyebrow ? <span className="eyebrow">{eyebrow}</span> : <span />}
          {right}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

// A labelled filter control (mono eyebrow over the input).
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="eyebrow">{label}</span>
      {children}
    </div>
  )
}
