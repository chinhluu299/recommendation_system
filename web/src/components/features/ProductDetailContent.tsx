"use client";

import * as React from "react";
import Image from "next/image";
import Autoplay from "embla-carousel-autoplay";
import { Minus, Plus, ShoppingCart } from "lucide-react";

import type { Product } from "@/components/features/ProducList";
import { Button } from "@/components/ui/button";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
  type CarouselApi,
} from "@/components/ui/carousel";
import { cn } from "@/lib/utils";
import { Separator } from "../ui/separator";
import DeliveryInfo from "../shared/DeliveryInfo";

type ProductDetailContentProps = {
  product: Product;
};

const ProductDetailContent = ({ product }: ProductDetailContentProps) => {
  const [quantity, setQuantity] = React.useState("1");
  const [carouselApi, setCarouselApi] = React.useState<CarouselApi>();
  const [selectedImageIndex, setSelectedImageIndex] = React.useState(0);
  const [isMobileViewport, setIsMobileViewport] = React.useState(false);
  const autoplayPlugin = React.useRef(
    Autoplay({
      delay: 2500,
      stopOnInteraction: true,
      stopOnMouseEnter: true,
    }),
  );

  const productImages = React.useMemo(() => {
    if (product.images && product.images.length > 0) {
      return product.images;
    }

    return [product.image];
  }, [product.image, product.images]);
  const hasMultipleImages = productImages.length > 1;

  const normalizedQuantity = React.useMemo(() => {
    const parsedQuantity = Number.parseInt(quantity, 10);

    if (Number.isNaN(parsedQuantity) || parsedQuantity < 1) {
      return 1;
    }

    return parsedQuantity;
  }, [quantity]);

  const updateQuantity = (nextQuantity: number) => {
    setQuantity(String(Math.max(1, nextQuantity)));
  };

  const handleBuyNow = () => {
    console.log(`Buy now: ${product.id}, quantity: ${normalizedQuantity}`);
  };

  const handleAddToCart = () => {
    console.log(`Add to cart: ${product.id}, quantity: ${normalizedQuantity}`);
  };

  React.useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 767px)");

    const updateViewport = (event?: MediaQueryListEvent) => {
      setIsMobileViewport(event ? event.matches : mediaQuery.matches);
    };

    updateViewport();
    mediaQuery.addEventListener("change", updateViewport);

    return () => {
      mediaQuery.removeEventListener("change", updateViewport);
    };
  }, []);

  React.useEffect(() => {
    if (!carouselApi) {
      return;
    }

    const updateSelectedImage = () => {
      setSelectedImageIndex(carouselApi.selectedScrollSnap());
    };

    updateSelectedImage();
    carouselApi.on("select", updateSelectedImage);
    carouselApi.on("reInit", updateSelectedImage);

    return () => {
      carouselApi.off("select", updateSelectedImage);
      carouselApi.off("reInit", updateSelectedImage);
    };
  }, [carouselApi]);

  return (
    <main className="mx-auto w-full max-w-7xl px-3 py-8 sm:px-4 md:px-0 lg:py-12">
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-12">
        <div className="mx-auto w-full space-y-4">
          <Carousel
            setApi={setCarouselApi}
            opts={{ loop: hasMultipleImages }}
            plugins={isMobileViewport ? [autoplayPlugin.current] : []}
          >
            <CarouselContent className="ml-0">
              {productImages.map((image, index) => (
                <CarouselItem
                  key={`${product.id}-${index}`}
                  className="basis-full pl-0"
                >
                  <AspectRatio
                    ratio={1}
                    className="overflow-hidden rounded-3xl bg-gray-100"
                  >
                    <Image
                      src={image}
                      alt={`${product.name} image ${index + 1}`}
                      fill
                      priority={index === 0}
                      sizes="(max-width: 1024px) 100vw, 50vw"
                      className="h-full w-full object-cover"
                    />
                  </AspectRatio>
                </CarouselItem>
              ))}
            </CarouselContent>
            {hasMultipleImages && (
              <>
                <CarouselPrevious className="left-4 top-1/2 border-none bg-white/90 shadow-sm hover:bg-white disabled:bg-white/70" />
                <CarouselNext className="right-4 top-1/2 border-none bg-white/90 shadow-sm hover:bg-white disabled:bg-white/70" />
              </>
            )}
          </Carousel>

          {hasMultipleImages && (
            <div className="grid w-full grid-cols-3 gap-3 sm:grid-cols-4">
              {productImages.map((image, index) => (
                <button
                  key={`thumbnail-${product.id}-${index}`}
                  type="button"
                  onClick={() => carouselApi?.scrollTo(index)}
                  className={cn(
                    "overflow-hidden rounded-2xl border-2 border-transparent bg-gray-100 transition-all",
                    selectedImageIndex === index && "border-emerald-600",
                  )}
                  aria-label={`View image ${index + 1}`}
                >
                  <AspectRatio ratio={1}>
                    <Image
                      src={image}
                      alt={`${product.name} thumbnail ${index + 1}`}
                      fill
                      sizes="160px"
                      className="h-full w-full object-cover"
                    />
                  </AspectRatio>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col justify-start">
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-gray-950 sm:text-4xl">
            {product.name}
          </h1>
          <p className="mt-4 text-base leading-7 text-gray-600 sm:text-lg">
            {product.description}
          </p>

          <Separator className="my-6" />

          <div className="text-3xl font-bold text-gray-950">
            ${product.price.toFixed(2)}
          </div>

          <p className="mt-1 text-sm italic text-muted-foreground">
            Suggested payments with 6 months special financing
          </p>

          <div className="mt-8">
            <p className="text-sm font-medium text-gray-700">Quantity</p>
            <div className="mt-3 flex w-full max-w-xs items-center overflow-hidden rounded-full border border-gray-200 bg-[#F5F6F6]">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => updateQuantity(normalizedQuantity - 1)}
                aria-label="Decrease quantity"
                className="h-10 w-10 text-gray-700 hover:bg-white/50 cursor-pointer"
              >
                <Minus className="size-4" />
              </Button>

              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={quantity}
                disabled
                className="h-10 flex-1 bg-transparent px-2 text-center text-sm font-semibold text-gray-950 outline-none"
                aria-label="Product quantity"
              />

              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => updateQuantity(normalizedQuantity + 1)}
                aria-label="Increase quantity"
                className="h-10 w-10 text-gray-700 hover:bg-white/50 cursor-pointer"
              >
                <Plus className="size-4" />
              </Button>
            </div>
          </div>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button
              type="button"
              size="lg"
              onClick={handleBuyNow}
              className="min-w-40 rounded-full bg-emerald-900 px-8 text-white hover:bg-emerald-800 cursor-pointer"
            >
              Buy now
            </Button>
            <Button
              type="button"
              size="lg"
              variant="outline"
              onClick={handleAddToCart}
              className="min-w-40 rounded-full px-8 border border-emerald-900 hover:bg-gray-100 cursor-pointer"
            >
              <ShoppingCart className="size-4" />
              Add to Cart
            </Button>
          </div>
          <div className="mt-8 w-full max-w-md">
            <DeliveryInfo />
          </div>
        </div>
      </section>
    </main>
  );
};

export default ProductDetailContent;
