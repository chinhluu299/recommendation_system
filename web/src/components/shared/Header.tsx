import { Phone } from "lucide-react";
import Link from "next/link";

const Header = () => {
  return (
    <nav className="border-b bg-background">
      <div className="container flex h-16 items-center">
        <Link
          href={"/"}
          className="flex items-center gap-2 font-semibold text-2xl mr-6 font-mono hover:opacity-80 transition-opacity"
        >
          <Phone className="size-6 text-emerald-500" />
          <span className="bg-linear-to-r from-emerald-500 to-green-500 bg-clip-text text-transparent">
            My App
          </span>
        </Link>

        <div className="flex flex-1">
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />
        </div>

        <div className="flex items-center gap-4">
          <button className="bg-emerald-500 text-emerald-foreground hover:bg-emerald-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
            Sign In
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Header;
