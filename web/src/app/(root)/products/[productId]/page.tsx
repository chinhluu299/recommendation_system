import { notFound } from "next/navigation";

import ProductDetailContent from "@/components/features/ProductDetailContent";
import type { Product } from "@/components/features/ProducList";

interface ProductDetailPageProps {
  params: Promise<{ productId: string }>;
}

const productDetails: Product[] = [
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

const ProductDetailPage = async ({ params }: ProductDetailPageProps) => {
  const { productId } = await params;
  const product = productDetails.find((item) => item.id === Number(productId));

  if (!product) {
    notFound();
  }

  return <ProductDetailContent product={product} />;
};

export default ProductDetailPage;
