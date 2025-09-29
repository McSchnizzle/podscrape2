import { createBrowserClient } from '@supabase/ssr'

// Singleton client instance to prevent multiple GoTrueClient instances
let clientInstance: ReturnType<typeof createBrowserClient> | null = null

export function createClient() {
  // Return existing instance if available
  if (clientInstance) {
    return clientInstance
  }

  // Create new instance only if none exists
  clientInstance = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )

  return clientInstance
}