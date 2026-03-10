"use client";

import * as React from "react";
import Autoplay from "embla-carousel-autoplay";

import {
  type CarouselApi,
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";

type BannerSlide = {
  id: number;
  eyebrow: string;
  title: string;
  description: string;
  bgClassName: string;
};

const slides: BannerSlide[] = [
  {
    id: 1,
    eyebrow: "Smart Picks",
    title: "Headphones Tuned To Your Taste",
    description:
      "Discover recommendations shaped by your listening habits and product signals.",
    bgClassName:
      "bg-[radial-gradient(circle_at_top_left,_#fef3c7_0%,_#fde68a_30%,_#f97316_100%)]",
  },
  {
    id: 2,
    eyebrow: "Fresh Arrivals",
    title: "New Releases From Favorite Brands",
    description:
      "Stay ahead with weekly drops curated for your preferred sound profile.",
    bgClassName:
      "bg-[radial-gradient(circle_at_top_left,_#d1fae5_0%,_#6ee7b7_35%,_#0f766e_100%)]",
  },
  {
    id: 3,
    eyebrow: "Limited Offers",
    title: "Save More On Trending Audio Gear",
    description:
      "Catch personalized deals before they are gone with ranking based on your interests.",
    bgClassName:
      "bg-[radial-gradient(circle_at_top_left,_#fee2e2_0%,_#fda4af_35%,_#9f1239_100%)]",
  },
];

const AUTOPLAY_DELAY = 3000;

const Banner = () => {
  const emblaRef = React.useRef<HTMLDivElement | null>(null);
  const handleEmblaRef = React.useCallback((node: HTMLDivElement | null) => {
    emblaRef.current = node;
  }, []);
  const autoplayPlugin = React.useRef(
    Autoplay({
      delay: AUTOPLAY_DELAY,
      stopOnInteraction: false,
    }),
  );
  const [api, setApi] = React.useState<CarouselApi>();
  const [current, setCurrent] = React.useState(0);

  React.useEffect(() => {
    if (!api) return;

    const updateSelected = () => {
      setCurrent(api.selectedScrollSnap());
    };

    updateSelected();
    api.on("select", updateSelected);
    api.on("reInit", updateSelected);

    return () => {
      api.off("select", updateSelected);
      api.off("reInit", updateSelected);
    };
  }, [api]);

  return (
    <section className="mx-auto w-full max-w-7xl px-3 py-4 sm:px-4 sm:py-6 md:px-0 md:py-8 lg:py-10">
      <Carousel
        emblaRef={handleEmblaRef}
        setApi={setApi}
        opts={{ loop: true }}
        plugins={[autoplayPlugin.current]}
        className="group"
        onMouseEnter={() => autoplayPlugin.current.stop()}
        onMouseLeave={() => autoplayPlugin.current.play()}
      >
        <CarouselContent className="ml-0">
          {slides.map((slide) => (
            <CarouselItem key={slide.id} className="pl-0">
              <article
                className={`${slide.bgClassName} flex min-h-64 flex-col justify-end rounded-2xl px-4 py-5 text-white shadow-xl sm:min-h-72 sm:px-5 sm:py-6 md:min-h-96 md:rounded-3xl md:px-8 md:py-9 lg:min-h-105 lg:px-12 lg:py-12`}
              >
                <p className="text-[10px] uppercase tracking-[0.16em] text-white/80 sm:text-xs md:text-sm md:tracking-[0.18em]">
                  {slide.eyebrow}
                </p>
                <h2 className="mt-2 max-w-xl text-xl font-semibold leading-tight sm:mt-3 sm:max-w-2xl sm:text-3xl md:text-4xl lg:text-5xl">
                  {slide.title}
                </h2>
                <p className="mt-2 max-w-sm text-xs text-white/90 sm:mt-3 sm:max-w-xl sm:text-sm md:mt-4 md:text-base">
                  {slide.description}
                </p>
              </article>
            </CarouselItem>
          ))}
        </CarouselContent>

        <CarouselPrevious className="hidden lg:flex lg:left-8 lg:top-8 lg:z-10 lg:size-9 lg:translate-y-0 lg:border-white/40 lg:bg-white/20 lg:text-white lg:backdrop-blur-sm lg:hover:bg-white/30" />
        <CarouselNext className="hidden lg:flex lg:left-20 lg:top-8 lg:z-10 lg:size-9 lg:translate-y-0 lg:border-white/40 lg:bg-white/20 lg:text-white lg:backdrop-blur-sm lg:hover:bg-white/30" />

        <div className="absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 gap-1.5 sm:bottom-4 sm:gap-2 md:bottom-5">
          {slides.map((slide, index) => (
            <button
              key={slide.id}
              type="button"
              onClick={() => api?.scrollTo(index)}
              aria-label={`Go to slide ${index + 1}`}
              className={`rounded-full transition-all ${
                current === index
                  ? "h-2 w-7 bg-white sm:h-2.5 sm:w-8"
                  : "h-2 w-2 bg-white/45 sm:h-2.5 sm:w-2.5"
              }`}
            />
          ))}
        </div>
      </Carousel>
    </section>
  );
};

export default Banner;
