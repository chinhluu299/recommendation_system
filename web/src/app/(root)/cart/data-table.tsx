"use client";

import * as React from "react";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  type RowSelectionState,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TypographyH3, TypographyMuted } from "@/components/ui/typography";

import type { CartItem } from "./columns";

type DataTableProps = {
  columns: ColumnDef<CartItem>[];
  data: CartItem[];
};

export function DataTable({ columns, data }: DataTableProps) {
  "use no memo";

  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>({});

  // TanStack Table is intentionally used in this client component.
  // React Compiler should not attempt to memoize this component.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    enableRowSelection: true,
    state: {
      sorting,
      rowSelection,
    },
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 5,
      },
    },
  });

  const selectedRows = table.getFilteredSelectedRowModel().rows;
  const selectedItemCount = selectedRows.length;
  const selectedItems = selectedRows.map((row) => row.original);

  const selectedSubtotal = selectedItems.reduce(
    (sum, item) => sum + item.price * item.quantity,
    0,
  );

  const currencyFormatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  });

  const isCheckoutDisabled = selectedItemCount === 0;

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No products in the cart.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          Next
        </Button>
      </div>

      <div className="rounded-xl border bg-card p-4">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <TypographyH3>Total Preview</TypographyH3>
            <TypographyMuted>
              Showing {table.getRowModel().rows.length} of {data.length} cart
              items.
            </TypographyMuted>
          </div>
          <div className="flex flex-col items-center gap-2 sm:items-end">
            {selectedItemCount > 0 && (
              <TypographyH3 className="text-lg font-semibold text-red-700">
                Subtotal: {currencyFormatter.format(selectedSubtotal)}
              </TypographyH3>
            )}
            <Button
              size="sm"
              disabled={isCheckoutDisabled}
              onClick={() => {
                console.log("Checkout selected items:", selectedItems);
              }}
            >
              Checkout Selected ({selectedItemCount})
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
