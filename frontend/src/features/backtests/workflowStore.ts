/**
 * The one live copy of the run workflow.
 *
 * A module-level store rather than page state: the trader moves between the
 * library, a strategy's documentation, the run form and a result, and every one
 * of those is a different route. Parameter edits held in a page component would
 * be gone by the second navigation. Mirrored into sessionStorage so a reload
 * mid-experiment is not one either.
 *
 * This is genuinely client-side UI state, so it does not belong in TanStack
 * Query (ARCHITECTURE.md 2.5).
 */

import { useSyncExternalStore } from 'react'

import { createInitialWorkflow, parseWorkflow, type WorkflowState } from './workflow'

const STORAGE_KEY = 'backtest-workflow'

let state: WorkflowState = createInitialWorkflow()
let hydrated = false
const listeners = new Set<() => void>()

function storage(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage
  } catch {
    // Private-mode browsers throw on access rather than returning null.
    return null
  }
}

function hydrate(): void {
  if (hydrated) return
  hydrated = true
  const restored = parseWorkflow(storage()?.getItem(STORAGE_KEY) ?? null)
  if (restored) state = restored
}

function persist(): void {
  try {
    storage()?.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // A full or unavailable quota costs persistence across reloads, nothing more.
  }
}

function emit(): void {
  for (const listener of listeners) listener()
}

export function getWorkflow(): WorkflowState {
  hydrate()
  return state
}

export function setWorkflow(next: WorkflowState): void {
  hydrate()
  if (next === state) return
  state = next
  persist()
  emit()
}

/** Apply a patch, or a function of the current state. */
export function updateWorkflow(
  patch: Partial<WorkflowState> | ((current: WorkflowState) => WorkflowState),
): void {
  const current = getWorkflow()
  setWorkflow(typeof patch === 'function' ? patch(current) : { ...current, ...patch })
}

export function resetWorkflow(): void {
  setWorkflow(createInitialWorkflow())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Read the workflow and re-render when any part of it changes. */
export function useWorkflow(): WorkflowState {
  return useSyncExternalStore(subscribe, getWorkflow, getWorkflow)
}
