// A small sortable table on top of the shadcn table primitives.
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'

import { EmptyState } from '@/components/states'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

export type Column<T> = {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  /** Value used for sorting; omit to make the column unsortable. */
  sortValue?: (row: T) => number | string | null
  align?: 'left' | 'right' | 'center'
  className?: string
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  caption,
  onRowClick,
  initialSort,
  empty,
  dense = false,
}: {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  caption?: string
  onRowClick?: (row: T) => void
  initialSort?: { key: string; desc?: boolean }
  empty?: ReactNode
  dense?: boolean
}) {
  const [sort, setSort] = useState(initialSort ?? null)
  const sorted = useMemo(() => {
    const column = columns.find((c) => c.key === sort?.key)
    if (!column?.sortValue) return rows
    const value = column.sortValue
    return [...rows].sort((a, b) => {
      const x = value(a)
      const y = value(b)
      if (x === y) return 0
      if (x === null) return 1
      if (y === null) return -1
      const order = x < y ? -1 : 1
      return sort?.desc ? -order : order
    })
  }, [rows, columns, sort])

  if (rows.length === 0) return <>{empty ?? <EmptyState />}</>

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        {caption && <TableCaption className="sr-only">{caption}</TableCaption>}
        <TableHeader className="bg-muted/60">
          <TableRow>
            {columns.map((column) => {
              const active = sort?.key === column.key
              const ariaSort = active ? (sort?.desc ? 'descending' : 'ascending') : undefined
              return (
                <TableHead
                  key={column.key}
                  aria-sort={ariaSort}
                  className={cn(
                    'h-10 text-xs font-semibold tracking-wide text-muted-foreground uppercase',
                    column.align === 'right' && 'text-right',
                    column.align === 'center' && 'text-center',
                    column.className,
                  )}
                >
                  {column.sortValue ? (
                    <button
                      type="button"
                      className={cn(
                        'inline-flex items-center gap-1 rounded hover:text-foreground focus-visible:outline-2',
                        column.align === 'right' && 'flex-row-reverse',
                      )}
                      onClick={() =>
                        setSort({ key: column.key, desc: active ? !sort?.desc : true })
                      }
                    >
                      {column.header}
                      {active ? (
                        sort?.desc ? (
                          <ArrowDown className="size-3" aria-hidden />
                        ) : (
                          <ArrowUp className="size-3" aria-hidden />
                        )
                      ) : (
                        <ArrowUpDown className="size-3 opacity-40" aria-hidden />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </TableHead>
              )
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((row) => (
            <TableRow
              key={rowKey(row)}
              className={cn(onRowClick && 'cursor-pointer')}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (event) => {
                      if (event.key === 'Enter') onRowClick(row)
                    }
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((column) => (
                <TableCell
                  key={column.key}
                  className={cn(
                    dense ? 'py-2' : 'py-3',
                    column.align === 'right' && 'tabular text-right',
                    column.align === 'center' && 'text-center',
                    column.className,
                  )}
                >
                  {column.cell(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
