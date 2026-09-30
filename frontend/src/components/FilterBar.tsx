// A row of page-level filters: search box plus any number of selects.
import { Search, X } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export type SelectFilter = {
  id: string
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}

export function FilterSelect({ filter }: { filter: SelectFilter }) {
  return (
    <div className="flex flex-col gap-1">
      <span id={`${filter.id}-label`} className="text-xs font-medium text-muted-foreground">
        {filter.label}
      </span>
      <Select value={filter.value} onValueChange={filter.onChange}>
        <SelectTrigger aria-labelledby={`${filter.id}-label`} className="h-9 min-w-40 bg-card">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {filter.options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export function FilterBar({
  search,
  onSearch,
  searchLabel = 'Search',
  selects = [],
  onReset,
  children,
}: {
  search?: string
  onSearch?: (value: string) => void
  searchLabel?: string
  selects?: SelectFilter[]
  onReset?: () => void
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4 shadow-xs">
      {onSearch && (
        <div className="flex min-w-56 flex-1 flex-col gap-1">
          <label htmlFor="filter-search" className="text-xs font-medium text-muted-foreground">
            {searchLabel}
          </label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="filter-search"
              value={search ?? ''}
              onChange={(event) => onSearch(event.target.value)}
              placeholder={`${searchLabel}...`}
              className="h-9 pl-8"
            />
          </div>
        </div>
      )}
      {selects.map((filter) => (
        <FilterSelect key={filter.id} filter={filter} />
      ))}
      {children}
      {onReset && (
        <Button variant="ghost" size="sm" className="h-9" onClick={onReset}>
          <X aria-hidden /> Reset
        </Button>
      )}
    </div>
  )
}
