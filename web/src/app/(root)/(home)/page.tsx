import Banner from "@/components/features/Banner";

export default function Home() {
  return (
    <main className="min-h-screen">
      <Banner />

      {/* Đây là nơi bạn sẽ đặt Hero Section và Product Grid của Shopcart */}
      <section className="container mx-auto py-10">
        <h1 className="text-4xl font-bold">Headphones For You!</h1>
        <p className="text-muted-foreground mt-2">
          Explore our latest recommendations based on your style.
        </p>
      </section>
    </main>
  );
}
