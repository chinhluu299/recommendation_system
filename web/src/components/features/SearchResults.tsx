"use client";

import * as React from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { GitBranch, Loader2, SearchX } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  api,
  type ProductItem,
  type RankingEvaluationResponse,
  type ProductSearchTrace,
} from "@/lib/api";
import { readStoredAuthUser } from "@/lib/auth";

const PLACEHOLDER =
  "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&h=500&fit=crop";

export default function SearchResults() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.get("q") ?? "";

  const [products, setProducts] = React.useState<ProductItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [searchMode, setSearchMode] = React.useState<"pipeline" | "ilike" | null>(null);
  const [searchTrace, setSearchTrace] = React.useState<ProductSearchTrace | null>(null);
  const [traceOpen, setTraceOpen] = React.useState(false);
  const [evaluationOpen, setEvaluationOpen] = React.useState(false);
  const [evaluationLoading, setEvaluationLoading] = React.useState(false);
  const [evaluationError, setEvaluationError] = React.useState<string | null>(null);
  const [evaluation, setEvaluation] = React.useState<RankingEvaluationResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!query) {
      return;
    }

    const user = readStoredAuthUser();
    if (!user?.token) {
      router.push("/auth/signin");
      return;
    }

    setLoading(true);
    setError(null);

    api
      .searchProducts(query, 100, 0, true)
      .then((res) => {
        if (res.data) {
          setProducts(res.data.items);
          setTotal(res.data.total);
          setSearchMode(res.data.search_mode);
          setSearchTrace(res.data.trace);
          setEvaluation(null);
          setEvaluationError(null);
        } else {
          setError(res.message || "Tìm kiếm thất bại.");
          setSearchTrace(null);
          setEvaluation(null);
        }
      })
      .catch(() => {
        setError("Không thể kết nối API.");
        setSearchTrace(null);
        setEvaluation(null);
      })
      .finally(() => setLoading(false));
  }, [query, router]);

  const handleEvaluateRanking = async () => {
    const topProductIds = products.slice(0, 40).map((product) => product.id);
    if (topProductIds.length === 0) {
      setEvaluationError("No products available to evaluate.");
      setEvaluationOpen(true);
      return;
    }

    setEvaluationOpen(true);
    setEvaluationLoading(true);
    setEvaluationError(null);
    setEvaluation(null);

    try {
      const res = await api.evaluateRanking(query, topProductIds, 40);
      if (res.data) {
        setEvaluation(res.data);
      } else {
        setEvaluationError(res.message || "Cannot evaluate ranking.");
      }
    } catch {
      setEvaluationError("Cannot evaluate ranking.");
    } finally {
      setEvaluationLoading(false);
    }
  };

  if (!query) {
    return null;
  }

  return (
    <section className="mx-auto w-full max-w-7xl px-3 py-4 sm:px-4 md:px-0">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Kết quả tìm kiếm</h2>
          <p className="text-sm text-gray-500">
            &ldquo;{query}&rdquo;
            {!loading && !error && (
              <span className="ml-2 text-gray-400">— {total} sản phẩm</span>
            )}
          </p>
          {!loading && searchMode && (
            <div className="mt-1 inline-flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                  searchMode === "pipeline"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {searchMode === "pipeline" ? "✦ KG + KGAT" : "DB search"}
              </span>

              {searchMode === "pipeline" && searchTrace && (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setTraceOpen(true)}
                    className="h-6 rounded-full px-2 text-[11px]"
                  >
                    <GitBranch className="size-3.5" />
                    Trace
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleEvaluateRanking}
                    className="h-6 rounded-full px-2 text-[11px]"
                    disabled={evaluationLoading}
                  >
                    Evaluate
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="size-8 animate-spin text-emerald-600" />
          <span className="ml-3 text-gray-500">Đang tìm kiếm…</span>
        </div>
      )}

      {!loading && error && (
        <div className="flex flex-col items-center py-16 text-gray-400">
          <SearchX className="mb-3 size-12" />
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && products.length === 0 && (
        <div className="flex flex-col items-center py-16 text-gray-400">
          <SearchX className="mb-3 size-12" />
          <p>Không tìm thấy sản phẩm phù hợp với &ldquo;{query}&rdquo;</p>
        </div>
      )}

      {!loading && !error && products.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 xl:grid-cols-4">
          {products.map((product, index) => (
            <Card
              key={product.id}
              onClick={() => router.push(`/products/${product.id}`)}
              className="cursor-pointer overflow-hidden p-0 transition-shadow duration-300 hover:shadow-lg"
            >
              <CardContent className="relative p-0">
                <div className="relative aspect-square w-full overflow-hidden bg-gray-100">
                  <Image
                    src={product.image_url ?? PLACEHOLDER}
                    alt={product.title}
                    fill
                    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
                    className="object-cover transition-transform duration-300 group-hover:scale-105"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).src = PLACEHOLDER;
                    }}
                  />
                  <span className="absolute left-2 top-2 rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-bold text-white shadow">
                    #{index + 1}
                  </span>
                </div>
              </CardContent>

              <CardHeader className="pb-4">
                <div className="mb-1 flex items-start justify-between gap-2">
                  <CardTitle className="line-clamp-2 text-sm font-semibold leading-snug">
                    {product.title}
                  </CardTitle>
                  {product.price != null && (
                    <Badge variant="secondary" className="shrink-0 font-bold">
                      ${product.price.toFixed(0)}
                    </Badge>
                  )}
                </div>
                {product.brand && (
                  <CardDescription className="text-xs font-medium text-emerald-700">
                    {product.brand}
                  </CardDescription>
                )}
                {product.description && (
                  <CardDescription className="mt-1 line-clamp-2 text-xs">
                    {product.description}
                  </CardDescription>
                )}
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={traceOpen} onOpenChange={setTraceOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>KG + KGAT Trace</DialogTitle>
            <DialogDescription>
              Query: &ldquo;{query}&rdquo; | Mode: {searchTrace?.pipeline_mode ?? "unknown"}
            </DialogDescription>
          </DialogHeader>

          {!searchTrace ? (
            <p className="text-sm text-gray-500">No trace data available.</p>
          ) : (
            <div className="space-y-3">
              {searchTrace.steps.map((step, index) => (
                <div
                  key={`${step.id}-${index}`}
                  className="rounded-xl border border-gray-200 p-3"
                >
                  <p className="text-sm font-semibold text-gray-900">
                    Step {index + 1}: {step.title}
                  </p>
                  <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-50 p-2 text-xs text-gray-700">
                    {JSON.stringify(step.payload, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={evaluationOpen} onOpenChange={setEvaluationOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Top-40 Ranking Evaluation</DialogTitle>
            <DialogDescription>
              LLM-based assessment for how well top products match user trend.
            </DialogDescription>
          </DialogHeader>

          {evaluationLoading && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Loader2 className="size-4 animate-spin" />
              Evaluating ranking...
            </div>
          )}

          {!evaluationLoading && evaluationError && (
            <p className="text-sm text-red-600">{evaluationError}</p>
          )}

          {!evaluationLoading && !evaluationError && evaluation && (
            <div className="space-y-3">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                <p className="text-sm font-semibold text-emerald-900">
                  Query Fit Score: {evaluation.query_fit_score}/100
                </p>
                <p className="mt-1 text-sm font-semibold text-emerald-900">
                  User Fit Score: {evaluation.user_fit_score}/100
                </p>
                <p className="mt-1 text-sm text-emerald-900">
                  Overall Score: {evaluation.score}/100
                </p>
                <p className="mt-1 text-sm text-emerald-900">{evaluation.verdict}</p>
                <p className="mt-2 text-xs text-emerald-700">
                  Evaluated {evaluation.evaluated_count} products •{" "}
                  {evaluation.used_llm ? "LLM" : "Unavailable"}
                </p>
              </div>

              <div className="rounded-xl border border-gray-200 p-3">
                <p className="text-sm font-semibold text-gray-900">Summary</p>
                <p className="mt-1 text-sm leading-6 text-gray-700">
                  {evaluation.summary}
                </p>
              </div>

              <div className="rounded-xl border border-gray-200 p-3">
                <p className="text-sm font-semibold text-gray-900">Strengths</p>
                <ul className="mt-1 list-disc pl-5 text-sm text-gray-700">
                  {evaluation.strengths.map((item, index) => (
                    <li key={`strength-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="rounded-xl border border-gray-200 p-3">
                <p className="text-sm font-semibold text-gray-900">Risks</p>
                <ul className="mt-1 list-disc pl-5 text-sm text-gray-700">
                  {evaluation.risks.map((item, index) => (
                    <li key={`risk-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
