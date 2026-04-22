import { Suspense } from "react";
import Link from "next/link";
import Banner from "@/components/features/Banner";
import ProductList from "@/components/features/ProducList";
import SearchBar from "@/components/features/SearchBar";
import SearchResults from "@/components/features/SearchResults";
import { Button } from "@/components/ui/button";

export default function Home({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  return (
    <main className="min-h-screen">
      <Banner />

      <section className="mx-auto w-full max-w-7xl px-3 sm:px-4 md:px-0">
        <SearchBar />
      </section>

      {/* Search results (client component, reads ?q= from URL) */}
      <Suspense>
        <SearchResults />
      </Suspense>

      {/* Default featured products — ẩn khi đang search */}
      <Suspense>
        <DefaultProducts searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function DefaultProducts({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const params = await searchParams;
  if (params.q) return null;

  return (
    <section className="mx-auto w-full max-w-7xl px-3 pt-4 sm:px-4 sm:pt-6 md:px-0 md:pt-8 lg:pt-10">
      <div className="mb-2 flex flex-col items-start gap-4 sm:gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="mb-2 text-2xl font-bold text-gray-900 sm:text-3xl lg:text-4xl">
            Our Products
          </h2>
          <p className="text-sm text-gray-600 sm:text-base">
            Discover our carefully curated selection of premium mobile products.
          </p>
        </div>
        <Button
          asChild
          variant="outline"
          className="mt-4 rounded-full border-emerald-600 text-emerald-700 hover:bg-emerald-600 hover:text-white"
        >
          <Link href="/products">View all products</Link>
        </Button>
      </div>
      <ProductList />
    </section>
  );
}
