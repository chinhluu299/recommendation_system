import ProductList, {
  type Product,
  type ProductPagination,
} from "@/components/features/ProducList";

// TODO: Replace mock data by calling product list API (e.g. GET /products?page=1).
const productsFromApi: Product[] = [
  {
    id: 1,
    name: "Premium Wireless Headphones",
    description:
      "High-quality sound with noise cancellation and 30-hour battery life.",
    price: 299.99,
    image:
      "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
  },
  {
    id: 2,
    name: "Studio Monitor Earbuds",
    description: "Professional-grade audio with active noise cancellation.",
    price: 199.99,
    image:
      "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&h=500&fit=crop",
  },
  {
    id: 3,
    name: "Bluetooth Sports Headphones",
    description: "Waterproof, sweat-resistant, perfect for workouts.",
    price: 129.99,
    image:
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=500&h=500&fit=crop",
  },
  {
    id: 4,
    name: "Over-Ear Gaming Headset",
    description: "Immersive surround sound with comfortable padding.",
    price: 159.99,
    image:
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=500&h=500&fit=crop",
  },
];

// TODO: Replace with pagination metadata returned by products API.
const paginationFromApi: ProductPagination = {
  page: 1,
  totalPages: 3,
  hasPrevious: false,
  hasNext: true,
};

const Products = () => {
  return (
    <main className="min-h-screen">
      <section className="mx-auto w-full max-w-7xl px-3 py-4 sm:px-4 sm:py-2 md:px-0 md:py-4 lg:py-6">
        <h1 className="text-3xl font-bold text-gray-900 sm:text-4xl lg:text-5xl">
          Product List
        </h1>
        <p className="mt-2 text-sm text-gray-600 sm:text-base">
          Explore all products and browse with pagination.
        </p>
      </section>

      <ProductList
        products={productsFromApi}
        pagination={paginationFromApi}
        showPagination
        paginationBasePath="/products"
      />
    </main>
  );
};

export default Products;
