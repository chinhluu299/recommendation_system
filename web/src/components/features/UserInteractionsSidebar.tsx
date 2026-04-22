"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { Loader2, ShoppingBag, Eye, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  api,
  type UserInteractedProduct,
  type UserTrendInsightResponse,
} from "@/lib/api";
import type { AuthUser } from "@/lib/auth";

const PLACEHOLDER_IMAGE =
  "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400&h=400&fit=crop";

type UserInteractionsSidebarProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentUser: AuthUser | null;
};

const formatPrice = (price: number | null) => {
  if (price == null) {
    return "N/A";
  }
  return `$${price.toFixed(2)}`;
};

const formatTime = (isoTime: string) => {
  const date = new Date(isoTime);
  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
};

const UserInteractionsSidebar = ({
  open,
  onOpenChange,
  currentUser,
}: UserInteractionsSidebarProps) => {
  const [items, setItems] = React.useState<UserInteractedProduct[]>([]);
  const [filter, setFilter] = React.useState<"all" | "purchase">("all");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [analysisQuery, setAnalysisQuery] = React.useState("");
  const [analysisLoading, setAnalysisLoading] = React.useState(false);
  const [analysisError, setAnalysisError] = React.useState<string | null>(null);
  const [analysisResult, setAnalysisResult] =
    React.useState<UserTrendInsightResponse | null>(null);

  const fetchInteractions = React.useCallback(async () => {
    if (!currentUser?.token) {
      setItems([]);
      setError("Please sign in to view interaction history.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.getMyInteractions(
        50,
        filter === "purchase" ? "purchase" : undefined,
      );

      if (response.data) {
        setItems(response.data.items);
      } else {
        setItems([]);
        setError(response.message || "Cannot load interaction history.");
      }
    } catch {
      setItems([]);
      setError("Cannot load interaction history.");
    } finally {
      setLoading(false);
    }
  }, [currentUser?.token, filter]);

  React.useEffect(() => {
    if (!open) {
      return;
    }
    fetchInteractions();
  }, [open, fetchInteractions]);

  const handleAnalyzeTrend = async () => {
    const trimmedQuery = analysisQuery.trim();
    if (!trimmedQuery) {
      setAnalysisError("Please enter a query to analyze.");
      return;
    }

    if (!currentUser?.token) {
      setAnalysisError("Please sign in to use AI trend analysis.");
      return;
    }

    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const response = await api.getMyInteractionTrendInsight(trimmedQuery, 120);
      if (response.data) {
        setAnalysisResult(response.data);
      } else {
        setAnalysisResult(null);
        setAnalysisError(response.message || "Cannot generate trend insight.");
      }
    } catch {
      setAnalysisResult(null);
      setAnalysisError("Cannot generate trend insight.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton
        className="right-0 top-0 h-screen w-full max-w-md translate-x-0 translate-y-0 rounded-none border-l border-gray-200 p-0 data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right"
      >
        <DialogHeader className="border-b border-gray-100 px-5 py-4 text-left">
          <DialogTitle className="text-xl font-bold text-gray-900">
            Your Product Interactions
          </DialogTitle>
          <DialogDescription className="text-sm text-gray-500">
            Track products you viewed or purchased.
          </DialogDescription>

          <div className="mt-3 flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant={filter === "all" ? "default" : "outline"}
              onClick={() => setFilter("all")}
              className="rounded-full"
            >
              All
            </Button>
            <Button
              type="button"
              size="sm"
              variant={filter === "purchase" ? "default" : "outline"}
              onClick={() => setFilter("purchase")}
              className="rounded-full"
            >
              Purchased
            </Button>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={fetchInteractions}
              className="ml-auto rounded-full"
              aria-label="Refresh interactions"
            >
              <RefreshCw className="size-4" />
            </Button>
          </div>
        </DialogHeader>

        <div className="h-[calc(100vh-170px)] overflow-y-auto px-4 py-4">
          <div className="mb-4 rounded-2xl border border-emerald-100 bg-emerald-50/50 p-3">
            <p className="text-sm font-semibold text-emerald-900">
              AI Trend Insight
            </p>
            <p className="mt-1 text-xs text-emerald-800/80">
              Enter a query to see what this user is likely to prioritize.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <Input
                value={analysisQuery}
                onChange={(event) => setAnalysisQuery(event.target.value)}
                placeholder="e.g. điện thoại pin trâu dưới 300$"
                className="h-9 bg-white"
              />
              <Button
                type="button"
                size="sm"
                onClick={handleAnalyzeTrend}
                disabled={analysisLoading}
                className="h-9 shrink-0 rounded-full"
              >
                {analysisLoading ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    Analyzing
                  </>
                ) : (
                  "AI Analyze"
                )}
              </Button>
            </div>

            {analysisError && (
              <p className="mt-2 text-xs text-red-600">{analysisError}</p>
            )}

            {analysisResult && (
              <div className="mt-3 rounded-xl border border-emerald-200 bg-white p-3">
                <p className="text-xs font-semibold text-emerald-900">
                  Summary for: &ldquo;{analysisResult.query}&rdquo;
                </p>
                <p className="mt-1 text-sm leading-6 text-gray-700">
                  {analysisResult.insight}
                </p>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-gray-500">
                  <span>{analysisResult.interaction_count} interactions</span>
                  <span>{analysisResult.purchase_count} purchases</span>
                  {analysisResult.top_brands.length > 0 && (
                    <span>Top brands: {analysisResult.top_brands.join(", ")}</span>
                  )}
                </div>
              </div>
            )}
          </div>

          {loading && (
            <div className="flex items-center justify-center gap-2 py-10 text-gray-500">
              <Loader2 className="size-4 animate-spin" />
              <span>Loading interactions...</span>
            </div>
          )}

          {!loading && error && (
            <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center text-sm text-gray-500">
              No interactions found for this filter.
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div className="space-y-3">
              {items.map((item) => (
                <Link
                  key={`${item.product_id}-${item.last_interacted_at}`}
                  href={`/products/${item.product_id}`}
                  className="block rounded-2xl border border-gray-100 bg-white p-3 transition-colors hover:bg-gray-50"
                  onClick={() => onOpenChange(false)}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative size-16 shrink-0 overflow-hidden rounded-xl bg-gray-100">
                      <Image
                        src={item.image_url ?? PLACEHOLDER_IMAGE}
                        alt={item.title}
                        fill
                        sizes="64px"
                        className="object-cover"
                      />
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-sm font-semibold text-gray-900">
                        {item.title}
                      </p>
                      {item.brand && (
                        <p className="mt-0.5 text-xs font-medium text-emerald-700">
                          {item.brand}
                        </p>
                      )}
                      <p className="mt-1 text-xs text-gray-500">{formatPrice(item.price)}</p>

                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <Badge
                          variant={
                            item.last_action_type === "purchase" ? "default" : "secondary"
                          }
                          className="gap-1"
                        >
                          {item.last_action_type === "purchase" ? (
                            <ShoppingBag className="size-3" />
                          ) : (
                            <Eye className="size-3" />
                          )}
                          {item.last_action_type}
                        </Badge>

                        <span className="text-[11px] text-gray-500">
                          {item.interaction_count} interactions
                        </span>

                        {item.purchase_count > 0 && (
                          <span className="text-[11px] font-medium text-emerald-700">
                            {item.purchase_count} purchases
                          </span>
                        )}
                      </div>

                      <p className="mt-1 text-[11px] text-gray-400">
                        Last: {formatTime(item.last_interacted_at)}
                      </p>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default UserInteractionsSidebar;
