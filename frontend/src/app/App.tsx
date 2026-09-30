import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'

import { FiltersProvider } from '@/app/FiltersProvider'
import { router } from '@/app/router'
import { SessionProvider } from '@/app/SessionProvider'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiError } from '@/lib/api/client'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Do not retry client errors (401/403/404); retry network hiccups once.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400) && count < 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <FiltersProvider>
          <TooltipProvider delayDuration={200}>
            <RouterProvider router={router} />
            <Toaster position="bottom-right" richColors closeButton />
          </TooltipProvider>
        </FiltersProvider>
      </SessionProvider>
    </QueryClientProvider>
  )
}
