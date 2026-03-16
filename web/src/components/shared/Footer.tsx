import Link from "next/link";
import { Facebook, Instagram, Twitter, Youtube } from "lucide-react";

const socialLinks = [
  {
    icon: Facebook,
    href: "#",
    label: "Facebook",
    color: "hover:text-[#1877F2]",
  },
  {
    icon: Instagram,
    href: "#",
    label: "Instagram",
    color: "hover:text-[#E1306C]",
  },
  { icon: Twitter, href: "#", label: "Twitter", color: "hover:text-[#1DA1F2]" },
  { icon: Youtube, href: "#", label: "YouTube", color: "hover:text-[#FF0000]" },
];

const Footer = () => {
  return (
    <footer className="border-t bg-transparent backdrop-blur-md">
      <div className="mx-auto grid w-full max-w-7xl gap-4 px-3 py-4 text-center sm:px-4 sm:py-5 lg:grid-cols-[1fr_auto_1fr] lg:items-center lg:gap-3 lg:px-0 lg:text-left">
        <Link href="/" className="justify-self-center lg:justify-self-start">
          <span className="text-xl font-bold text-[#003d29] sm:text-2xl">
            Vibe
          </span>
        </Link>

        <p className="order-3 text-xs text-gray-500 sm:text-sm lg:order-0 lg:justify-self-center">
          © {new Date().getFullYear()} Vibe. All rights reserved.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 lg:justify-self-end">
          {socialLinks.map(({ icon: Icon, href, label, color }) => (
            <Link
              key={label}
              href={href}
              aria-label={label}
              className={`flex size-8 items-center justify-center rounded-full text-gray-400 transition-colors ${color}`}
            >
              <Icon className="size-4" />
            </Link>
          ))}
        </div>
      </div>
    </footer>
  );
};

export default Footer;
