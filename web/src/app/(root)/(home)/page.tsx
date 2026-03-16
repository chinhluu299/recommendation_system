import Banner from "@/components/features/Banner";
import ProductList from "@/components/features/ProducList";
import SearchBar from "@/components/features/SearchBar";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="min-h-screen">
      <Banner />

      <section className="mx-auto w-full max-w-7xl px-3 sm:px-4 md:px-0">
        <SearchBar />
      </section>

      <section className="mx-auto w-full max-w-7xl px-3 pt-4 sm:px-4 sm:pt-6 md:px-0 md:pt-8 lg:pt-10">
        <div className="mb-2 flex flex-col items-start gap-4 sm:gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="mb-2 text-2xl font-bold text-gray-900 sm:text-3xl lg:text-4xl">
              Our Products
            </h2>
            <p className="text-sm text-gray-600 sm:text-base">
              Discover our carefully curated selection of premium mobile
              products.
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
      </section>

      {/* TODO: Replace default data by calling featured products API and pass via `products` prop. */}
      <ProductList />
    </main>
  );
}
