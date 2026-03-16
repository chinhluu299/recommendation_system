"use client";

import * as React from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { createColumns, type CartItem } from "./columns";
import { DataTable } from "./data-table";

// TODO: Replace mock data with cart items returned from the cart API.
const initialCartItems: CartItem[] = [
  {
    id: "HDP-1001",
    image:
      "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=300&h=300&fit=crop",
    productName: "Premium Wireless Headphones",
    price: 299.99,
    quantity: 1,
  },
  {
    id: "EAR-2042",
    image:
      "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=300&h=300&fit=crop",
    productName: "Studio Monitor Earbuds",
    price: 199.99,
    quantity: 2,
  },
  {
    id: "GAM-3308",
    image:
      "https://images.unsplash.com/photo-1612444530582-fc66183b16f7?w=300&h=300&fit=crop",
    productName: "Over-Ear Gaming Headset",
    price: 159.99,
    quantity: 1,
  },
  {
    id: "SPK-4110",
    image:
      "https://images.unsplash.com/photo-1589492477829-5e65395b66cc?w=300&h=300&fit=crop",
    productName: "Portable Smart Speaker",
    price: 129.99,
    quantity: 1,
  },
  {
    id: "ACC-0920",
    image:
      "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=300&h=300&fit=crop",
    productName: "USB-C Charging Dock",
    price: 89.99,
    quantity: 3,
  },
  {
    id: "MIC-5021",
    image:
      "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=300&h=300&fit=crop",
    productName: "Streaming Microphone",
    price: 149.99,
    quantity: 1,
  },
];

const CartPage = () => {
  const [cartItems, setCartItems] =
    React.useState<CartItem[]>(initialCartItems);

  const handleRemoveItem = (itemId: CartItem["id"]) => {
    setCartItems((previous) => previous.filter((item) => item.id !== itemId));
  };

  const columns = React.useMemo(
    () => createColumns({ onRemove: handleRemoveItem }),
    [],
  );

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-3 py-6 sm:px-4 lg:px-0">
      <Card className="border-border/70">
        <CardHeader>
          <CardTitle className="text-3xl sm:text-4xl">Shopping Cart</CardTitle>
          <CardDescription className="max-w-2xl text-sm sm:text-base">
            Review selected products and remove any item no longer needed.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable columns={columns} data={cartItems} />
        </CardContent>
      </Card>
    </main>
  );
};

export default CartPage;
