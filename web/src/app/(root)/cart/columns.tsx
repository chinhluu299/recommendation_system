"use client";
import type { ColumnDef } from "@tanstack/react-table";
import Image from "next/image";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

export type CartItem = {
  id: string;
  image: string;
  productName: string;
  price: number;
  quantity: number;
};

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

type CreateColumnsParams = {
  onRemove: (id: CartItem["id"]) => void;
};

export function createColumns({
  onRemove,
}: CreateColumnsParams): ColumnDef<CartItem>[] {
  return [
    {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label={`Select ${row.original.productName}`}
        />
      ),
      enableSorting: false,
      enableHiding: false,
    },
    {
      accessorKey: "productName",
      header: "Product",
      cell: ({ row }) => {
        const item = row.original;

        return (
          <div className="flex items-center gap-3">
            <div className="relative size-12 overflow-hidden rounded-md border border-border/60 bg-muted">
              <Image
                src={item.image}
                alt={item.productName}
                fill
                sizes="48px"
                className="object-cover"
              />
            </div>
            <div className="space-y-1">
              <p className="font-medium text-foreground">{item.productName}</p>
              <p className="text-sm text-muted-foreground">SKU: {item.id}</p>
            </div>
          </div>
        );
      },
    },
    {
      accessorKey: "price",
      header: "Price",
      cell: ({ row }) => currencyFormatter.format(row.original.price),
    },
    {
      accessorKey: "quantity",
      header: "Quantity",
    },
    {
      id: "total",
      header: "Total",
      cell: ({ row }) => {
        const { price, quantity } = row.original;
        return currencyFormatter.format(price * quantity);
      },
    },
    {
      id: "actions",
      header: "Action",
      cell: ({ row }) => (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={() => onRemove(row.original.id)}
          aria-label={`Remove ${row.original.productName}`}
          className="text-destructive hover:text-destructive"
        >
          <Trash2 className="size-4" />
        </Button>
      ),
      enableSorting: false,
      enableHiding: false,
    },
  ];
}
