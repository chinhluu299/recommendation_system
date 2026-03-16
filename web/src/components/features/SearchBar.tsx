"use client";

import * as React from "react";
import { Search, X, ArrowRight } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

// TODO: Replace with real search API results
const TRENDING_SEARCHES = [
  "Wireless Headphones",
  "Noise Cancellation",
  "Gaming Headset",
  "Bluetooth Earbuds",
  "Studio Monitor",
];

const SearchBar = () => {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);

  const filtered = TRENDING_SEARCHES.filter((item) =>
    item.toLowerCase().includes(query.toLowerCase()),
  );

  const suggestions = query.length === 0 ? TRENDING_SEARCHES : filtered;

  React.useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 80);
    } else {
      setQuery("");
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {/* TRIGGER — looks like a real search bar */}
      <DialogTrigger asChild>
        <button
          type="button"
          className="mx-auto flex w-full max-w-2xl cursor-text items-center gap-3 rounded-full border border-gray-200 bg-white/70 px-4 py-3 shadow-sm backdrop-blur-sm transition-all hover:border-emerald-400 hover:shadow-md focus:outline-none"
          aria-label="Open search"
        >
          <Search className="size-4 shrink-0 text-gray-400" />
          <span className="flex-1 text-left text-sm text-gray-400">
            Search products…
          </span>
          <kbd className="hidden rounded border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-400 sm:inline-block">
            ⌘ K
          </kbd>
        </button>
      </DialogTrigger>

      {/* DIALOG */}
      <DialogContent showCloseButton={false} className="gap-0 p-0">
        <DialogHeader className="px-4 pt-4">
          <DialogTitle className="sr-only">Search products</DialogTitle>

          {/* Input inside dialog */}
          <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5">
            <Search className="size-4 shrink-0 text-gray-400" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search products…"
              className="flex-1 bg-transparent text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none"
            />
            {query.length > 0 && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="rounded-full p-0.5 text-gray-400 hover:text-gray-600"
                aria-label="Clear search"
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>
        </DialogHeader>

        {/* Suggestions / results */}
        <div className="mt-3 px-2 pb-3">
          <p className="mb-1.5 px-2 text-xs font-medium text-gray-400">
            {query.length === 0 ? "Trending searches" : "Suggestions"}
          </p>

          {suggestions.length > 0 ? (
            <ul>
              {suggestions.map((item) => (
                <li key={item}>
                  <button
                    type="button"
                    onClick={() => {
                      setQuery(item);
                      // TODO: trigger actual search / navigate to results
                    }}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-gray-700 transition-colors hover:bg-emerald-50 hover:text-emerald-800"
                  >
                    <Search className="size-3.5 shrink-0 text-gray-400" />
                    <span className="flex-1 text-left">{item}</span>
                    <ArrowRight className="size-3.5 text-gray-300" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-4 text-center text-sm text-gray-400">
              No results for &quot;{query}&quot;
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SearchBar;
