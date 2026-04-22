"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode, useMemo } from "react";
import { Toaster } from "react-hot-toast";

type QueryProviderProps = {
  children: ReactNode;
};

export default function QueryProvider({ children }: QueryProviderProps) {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 0,
          },
        },
      }),
    [],
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 2800,
          style: {
            border: "1px solid #d1d5db",
            background: "#fff",
            color: "#111827",
          },
        }}
      />
    </QueryClientProvider>
  );
}
