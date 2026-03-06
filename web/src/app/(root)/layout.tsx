import Footer from "@/components/shared/Footer";
import Header from "@/components/shared/Header";

const Layout = ({ children }: { children: React.ReactNode }) => {
  return (
    <div className="min-h-screen flex flex-col px-16 mx-auto">
      <Header />
      {children}
      <Footer />
    </div>
  );
};

export default Layout;
