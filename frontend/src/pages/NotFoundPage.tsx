import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-sm text-muted-foreground">404</p>
      <h1 className="mt-2 text-xl font-semibold">Page not found</h1>
      <Button asChild variant="secondary" className="mt-6">
        <Link to="/">Back to dashboard</Link>
      </Button>
    </div>
  )
}
