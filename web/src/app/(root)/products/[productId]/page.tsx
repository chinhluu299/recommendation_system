"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { useParams } from "next/navigation";

import ProductDetailContent from "@/components/features/ProductDetailContent";
import type { Product } from "@/components/features/ProducList";
import { readStoredAuthUser } from "@/lib/auth";
import { api, type ProductDetailResponse } from "@/lib/api";

const PLACEHOLDER_IMAGE =
  "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200&h=1200&fit=crop";

const fallbackProductDetails: Product[] = [
  {
    id: 1,
    name: "Premium Wireless Headphones",
    description:
      "High-quality sound with noise cancellation and 30-hour battery life.",
    price: 299.99,
    image:
      "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200&h=1200&fit=crop",
    images: [
      "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1524678606370-a47ad25cb82a?w=1200&h=1200&fit=crop",
    ],
  },
  {
    id: 2,
    name: "Studio Monitor Earbuds",
    description: "Professional-grade audio with active noise cancellation.",
    price: 199.99,
    image:
      "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=1200&h=1200&fit=crop",
    images: [
      "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1572569511254-d8f925fe2cbb?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1572569511254-d8f925fe2cbb?w=1200&h=1200&fit=crop",
    ],
  },
  {
    id: 3,
    name: "Bluetooth Sports Headphones",
    description: "Waterproof, sweat-resistant, perfect for workouts.",
    price: 129.99,
    image:
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=1200&h=1200&fit=crop",
    images: [
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1518444065439-e933c06ce9cd?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1496957961599-e35b69ef5d7c?w=1200&h=1200&fit=crop",
    ],
  },
  {
    id: 4,
    name: "Over-Ear Gaming Headset",
    description: "Immersive surround sound with comfortable padding.",
    price: 159.99,
    image:
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=1200&h=1200&fit=crop",
    images: [
      "https://images.unsplash.com/photo-1487215078519-e21cc028cb29?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1612444530582-fc66183b16f7?w=1200&h=1200&fit=crop",
      "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=1200&h=1200&fit=crop",
    ],
  },
];

const mapProductDetailToProduct = (productDetail: ProductDetailResponse): Product => {
  const image = productDetail.image_url ?? PLACEHOLDER_IMAGE;

  return {
    id: productDetail.id,
    name: productDetail.title,
    description: productDetail.description ?? "No description available.",
    price: productDetail.price ?? 0,
    image,
    images: [image],
  };
};

const ProductDetailPage = () => {
  const params = useParams<{ productId: string }>();
  const routeProductId = params.productId;
  const [productId, setProductId] = React.useState<string>("");
  const [product, setProduct] = React.useState<Product | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isMounted = true;

    const loadProduct = async () => {
      if (!isMounted) {
        return;
      }

      if (!routeProductId) {
        setError("Product ID is missing.");
        setLoading(false);
        return;
      }

      setProductId(routeProductId);

      const numericProductId = Number(routeProductId);
      if (Number.isNaN(numericProductId) || numericProductId < 1) {
        setError("Product ID is invalid.");
        setLoading(false);
        return;
      }

      const fallbackProduct = fallbackProductDetails.find(
        (item) => item.id === numericProductId,
      );
      if (fallbackProduct) {
        setProduct(fallbackProduct);
      }

      const user = readStoredAuthUser();
      if (!user?.token) {
        if (!fallbackProduct) {
          setError("Please sign in to view this product.");
        }
        setLoading(false);
        return;
      }

      try {
        const response = await api.getProductDetail(numericProductId);
        if (!isMounted) {
          return;
        }

        if (response.data) {
          setProduct(mapProductDetailToProduct(response.data));
          setError(null);
        } else if (!fallbackProduct) {
          setError(response.message || "Cannot load product detail.");
        }
      } catch {
        if (isMounted && !fallbackProduct) {
          setError("Cannot load product detail at the moment.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadProduct();

    return () => {
      isMounted = false;
    };
  }, [routeProductId]);

  if (loading) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-7xl items-center justify-center px-3 py-8 sm:px-4 md:px-0 lg:py-12">
        <div className="flex items-center gap-3 text-gray-600">
          <Loader2 className="size-5 animate-spin" />
          <span>Loading product detail...</span>
        </div>
      </main>
    );
  }

  if (!product) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-7xl flex-col items-center justify-center px-3 py-8 text-center sm:px-4 md:px-0 lg:py-12">
        <h1 className="text-2xl font-semibold text-gray-900">Product not found</h1>
        <p className="mt-2 text-sm text-gray-600">
          {error ?? "We cannot find the product you requested."}
        </p>
        <Link
          href="/products"
          className="mt-6 rounded-full border border-emerald-900 px-6 py-2 text-sm font-medium text-emerald-900 transition-colors hover:bg-emerald-50"
        >
          Back to products
        </Link>
      </main>
    );
  }

  return <ProductDetailContent key={`${product.id}-${productId}`} product={product} />;
};

export default ProductDetailPage;
