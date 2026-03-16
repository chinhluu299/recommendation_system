"use client";

import * as React from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { Heart, ShoppingCart } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";

export type Product = {
  id: number;
  name: string;
  description: string;
  price: number;
  image: string;
  images?: string[];
  isFavorite?: boolean;
};

export type ProductPagination = {
  page: number;
  totalPages: number;
  hasPrevious: boolean;
  hasNext: boolean;
};

type ProductListProps = {
  products?: Product[];
  pagination?: ProductPagination;
  showPagination?: boolean;
  paginationBasePath?: string;
};

// TODO: Replace with API call for featured products (e.g. GET /products/featured).
const defaultFeaturedProducts: Product[] = [
  {
    id: 1,
    name: "Premium Wireless Headphones",
    description:
      "High-quality sound with noise cancellation and 30-hour battery life.",
    price: 299.99,
    image:
      "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
    isFavorite: false,
  },
  {
    id: 2,
    name: "Studio Monitor Earbuds",
    description: "Professional-grade audio with active noise cancellation.",
    price: 199.99,
    image:
      "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&h=500&fit=crop",
    isFavorite: false,
  },
  {
    id: 3,
    name: "Bluetooth Sports Headphones",
    description: "Waterproof, sweat-resistant, perfect for workouts.",
    price: 129.99,
    image:
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=500&h=500&fit=crop",
    isFavorite: false,
  },
  {
    id: 4,
    name: "Over-Ear Gaming Headset",
    description: "Immersive surround sound with comfortable padding.",
    price: 159.99,
    image:
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=500&h=500&fit=crop",
    isFavorite: false,
  },
];

// TODO: Replace with pagination metadata from API response.
const defaultPagination: ProductPagination = {
  page: 1,
  totalPages: 1,
  hasPrevious: false,
  hasNext: false,
};

const ProductList = ({
  products = defaultFeaturedProducts,
  pagination = defaultPagination,
  showPagination = false,
  paginationBasePath = "/products",
}: ProductListProps) => {
  const router = useRouter();
  const [favorites, setFavorites] = React.useState<Set<number>>(new Set());

  const toggleFavorite = (productId: number) => {
    const newFavorites = new Set(favorites);
    if (newFavorites.has(productId)) {
      newFavorites.delete(productId);
    } else {
      newFavorites.add(productId);
    }
    setFavorites(newFavorites);
  };

  const addToCart = (
    event: React.MouseEvent<HTMLButtonElement>,
    productId: number,
  ) => {
    event.stopPropagation();
    // TODO: Implement add to cart functionality
    console.log(`Added product ${productId} to cart`);
  };

  return (
    <section className="mx-auto w-full max-w-7xl px-3 py-4 sm:px-4 sm:py-4 md:px-0 md:py-6 lg:py-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
        {products.map((product) => (
          <Card
            key={product.id}
            data-product-id={product.id}
            onClick={() => router.push(`/products/${product.id}`)}
            className="overflow-hidden hover:shadow-lg transition-shadow duration-300 p-0 cursor-pointer"
          >
            {/* PRODUCT IMAGE WITH HEART ICON */}
            <CardContent className="p-0 relative group">
              <div className="relative w-full overflow-hidden bg-gray-200 aspect-square">
                <Image
                  src={product.image}
                  alt={product.name}
                  fill
                  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, (max-width: 1280px) 33vw, 25vw"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />

                {/* HEART ICON - ABSOLUTE TOP RIGHT */}
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleFavorite(product.id);
                  }}
                  className="absolute top-3 right-3 z-10 bg-white rounded-full p-2 hover:bg-gray-100 transition-colors duration-200 shadow-md"
                  aria-label="Add to favorites"
                >
                  <Heart
                    className={`size-5 transition-colors duration-200 ${
                      favorites.has(product.id)
                        ? "fill-red-500 text-red-500"
                        : "text-gray-400"
                    }`}
                  />
                </button>
              </div>
            </CardContent>

            {/* CARD HEADER - BADGE, TITLE, DESCRIPTION */}
            <CardHeader>
              <div className="flex items-start justify-between gap-2 mb-2">
                <CardTitle className="text-base sm:text-lg font-semibold line-clamp-1">
                  {product.name}
                </CardTitle>
                <Badge variant="secondary" className="shrink-0 font-bold">
                  ${product.price}
                </Badge>
              </div>
              <CardDescription className="text-xs sm:text-sm line-clamp-2">
                {product.description}
              </CardDescription>
            </CardHeader>

            {/* CARD FOOTER - ADD TO CART BUTTON */}
            <CardFooter className="pb-8 md:pb-2 flex justify-start">
              <Button
                type="button"
                onClick={(event) => addToCart(event, product.id)}
                className="w-3/4 text-black rounded-full bg-transparent hover:bg-emerald-600 hover:text-white border border-black hover:border-emerald-600 px-6 text-sm sm:text-base transition-all"
              >
                <ShoppingCart className="size-4 mr-1" />
                Add to Cart
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>

      {showPagination && pagination.totalPages > 1 && (
        <div className="mt-8 sm:mt-10">
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href={`${paginationBasePath}?page=${Math.max(1, pagination.page - 1)}`}
                  aria-disabled={!pagination.hasPrevious}
                  className={
                    !pagination.hasPrevious
                      ? "pointer-events-none opacity-50"
                      : ""
                  }
                />
              </PaginationItem>

              {Array.from(
                { length: pagination.totalPages },
                (_, index) => index + 1,
              ).map((pageNumber) => (
                <PaginationItem key={pageNumber}>
                  <PaginationLink
                    href={`${paginationBasePath}?page=${pageNumber}`}
                    isActive={pageNumber === pagination.page}
                  >
                    {pageNumber}
                  </PaginationLink>
                </PaginationItem>
              ))}

              <PaginationItem>
                <PaginationNext
                  href={`${paginationBasePath}?page=${Math.min(
                    pagination.totalPages,
                    pagination.page + 1,
                  )}`}
                  aria-disabled={!pagination.hasNext}
                  className={
                    !pagination.hasNext ? "pointer-events-none opacity-50" : ""
                  }
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </section>
  );
};

export default ProductList;
