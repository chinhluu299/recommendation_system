"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { User, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { writeStoredAuthUser } from "@/lib/auth";
import { api, type UserSummary } from "@/lib/api";

export default function SignInPage() {
  const router = useRouter();
  const [users, setUsers] = React.useState<UserSummary[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [loggingIn, setLoggingIn] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .getUsers(50)
      .then((res) => {
        if (res.data) setUsers(res.data.items);
        else setError("Không thể tải danh sách user.");
      })
      .catch(() => setError("Không thể kết nối API."))
      .finally(() => setLoading(false));
  }, []);

  const handleLoginAs = async (user: UserSummary) => {
    const extId = user.external_user_id;
    if (!extId) return;
    setLoggingIn(extId);
    try {
      const res = await api.loginAs(extId);
      if (!res.data) throw new Error(res.message);

      writeStoredAuthUser({
        name: user.full_name ?? extId,
        email: res.data.email ?? "",
        token: res.data.access_token,
        userId: res.data.user_id,
        externalUserId: extId,
      });
      router.push("/");
      router.refresh();
    } catch {
      setError("Đăng nhập thất bại.");
    } finally {
      setLoggingIn(null);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-xl space-y-8">
        {/* Header */}
        <div className="text-center">
          <Link href="/" className="inline-block">
            <span className="text-4xl font-bold text-[#003d29]">Vibe</span>
          </Link>
          <h2 className="mt-6 text-3xl font-bold tracking-tight text-gray-900">
            Chọn user để đăng nhập
          </h2>
          <p className="mt-2 text-sm text-gray-500">
            Demo — click vào user để đăng nhập ngay (không cần mật khẩu)
          </p>
        </div>

        {/* User list */}
        {loading && (
          <div className="flex justify-center py-12">
            <Loader2 className="size-8 animate-spin text-emerald-600" />
          </div>
        )}

        {error && (
          <p className="text-center text-sm text-red-500">{error}</p>
        )}

        {!loading && !error && (
          <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
            {users.map((u) => (
              <button
                key={u.id}
                type="button"
                disabled={loggingIn !== null}
                onClick={() => handleLoginAs(u)}
                className="flex w-full items-center gap-4 rounded-xl border border-gray-200 bg-white px-4 py-3 text-left shadow-sm transition-all hover:border-emerald-400 hover:shadow-md disabled:opacity-60"
              >
                {/* Avatar */}
                <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                  {loggingIn === u.external_user_id ? (
                    <Loader2 className="size-5 animate-spin" />
                  ) : (
                    <User className="size-5" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">
                    {u.external_user_id}
                  </p>
                  <p className="text-xs text-gray-400">
                    {u.interaction_count} interactions
                  </p>
                </div>

                <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                  Đăng nhập
                </span>
              </button>
            ))}
          </div>
        )}

        <p className="text-center text-xs text-gray-400">
          Chỉ hiển thị user có &gt;5 interactions trong dataset
        </p>
      </div>
    </div>
  );
}
