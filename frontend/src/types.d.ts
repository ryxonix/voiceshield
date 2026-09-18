/// <reference types="vite/client" />

export interface LiveSessionReturn {
  connected: boolean
  micActive: boolean
  events: any[]
  connect(opts: { role: string; language: string; speaker: string }): void
  sendEnd(): void
  shielding: boolean
  mitigation: any
  setShielded(on: boolean, mitigationEvent?: any): void
}

declare module '../lib' {
  import type { LiveSessionReturn } from './types'
  export function useLiveSession(): LiveSessionReturn
}
