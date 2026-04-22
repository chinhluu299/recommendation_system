from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError, ServiceUnavailable
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from app.search.model import KGAT


NEO4J_URI  = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "1234567890"
NEO4J_DB   = "recphones"

GEMINI_URL   = "http://localhost:1234/v1"
GEMINI_MODEL = "gpt-oss-20b"

TOP_K        = 1000
FILTER_BONUS = 0.5
SEM_W        = 0.7
POP_W        = 0.3
MIN_RATINGS  = 3


def find_ranking_dir() -> Path:
    here = Path(__file__).parent
    if (here / "data" / "entity2id.json").exists():
        return here
    offline = here.parent.parent / "offline" / "ranking"
    if (offline / "data" / "entity2id.json").exists():
        return offline
    return here


RANKING_DIR = find_ranking_dir()


llm_client: OpenAI | None = None


def get_llm() -> OpenAI:
    global llm_client
    if llm_client is not None:
        return llm_client
    
    llm_client = OpenAI(base_url=GEMINI_URL, api_key="")
    return llm_client


def chat(messages: list[dict], max_tokens: int = 512, temperature: float = 0.1) -> str:
    client = get_llm()
    for attempt in range(5):
        try:
            resp = client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            err = str(e)
            if "429" not in err and "RESOURCE_EXHAUSTED" not in err:
                raise
            if attempt == 4:
                raise
            time.sleep(min(15 * (2 ** attempt), 120))
    return ""


neo4j_driver = None


def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    global neo4j_driver
    if neo4j_driver is None:
        neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    try:
        with neo4j_driver.session(database=NEO4J_DB) as session:
            return [dict(r) for r in session.run(cypher, params or {})]
    except ServiceUnavailable:
        raise ConnectionError(f"Neo4j không khởi động tại {NEO4J_URI}")
    except CypherSyntaxError as e:
        raise SyntaxError(f"Cypher không hợp lệ: {e.message}")


embed_model: SentenceTransformer | None = None


def embed(text: str) -> list[float]:
    global embed_model
    if embed_model is None:
        embed_model = SentenceTransformer("intfloat/multilingual-e5-small")
    return embed_model.encode(text, normalize_embeddings=True).tolist()


class KGATReranker:
    def __init__(self):
        ckpt_path = RANKING_DIR / "checkpoints" / "best_model.pt"
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Checkpoint không tồn tại: {ckpt_path}")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        ckpt = torch.load(ckpt_path, map_location=self.device, weights_only=False)

        self.model = KGAT(ckpt["cfg"]).to(self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

        self.entity2id: dict[str, int] = json.loads(
            (RANKING_DIR / "data" / "entity2id.json").read_text(encoding="utf-8")
        )
        ckg = np.load(RANKING_DIR / "data" / "ckg_triples.npy")
        ckg_t = torch.from_numpy(ckg).long().to(self.device)
        with torch.no_grad():
            self.emb = self.model(ckg_t[:, 0], ckg_t[:, 1], ckg_t[:, 2])

        self.centroid: torch.Tensor | None = None
        print(f"[Reranker] Loaded — entities={self.emb.shape[0]}, dim={self.emb.shape[1]}")

    def user_emb(self, user_id: str) -> torch.Tensor:
        key = f"user_{user_id}"
        if key in self.entity2id:
            return self.emb[self.entity2id[key]]
        if self.centroid is None:
            ids = [v for k, v in self.entity2id.items() if k.startswith("user_")]
            self.centroid = self.emb[torch.tensor(ids, device=self.device)].mean(0)
        return self.centroid

    def rerank(self, user_id: str, asins: list[str]) -> list[tuple[str, float]]:
        e_u = self.user_emb(user_id)
        with torch.no_grad():
            scores = [
                float((e_u * self.emb[self.entity2id[f"product_{a}"]]).sum())
                if f"product_{a}" in self.entity2id else 0.0
                for a in asins
            ]
        return sorted(zip(asins, scores), key=lambda x: -x[1])


reranker: KGATReranker | None = None


def get_reranker() -> KGATReranker:
    global reranker
    if reranker is None:
        reranker = KGATReranker()
    return reranker


enum_cache: dict | None = None


def load_enums() -> dict:
    global enum_cache
    if enum_cache is not None:
        return enum_cache
    try:
        enum_cache = {
            "technology": [r["v"] for r in run_query(
                "MATCH (t:Technology) RETURN DISTINCT t.label AS v") if r.get("v")],
            "carrier":    [r["v"] for r in run_query(
                "MATCH (c:Carrier) RETURN DISTINCT c.label AS v") if r.get("v")],
            "camera_mp":  sorted({r["v"] for r in run_query(
                "MATCH (s:Spec {key:'other_camera_features'}) WHERE s.numeric_value IS NOT NULL "
                "RETURN DISTINCT s.numeric_value AS v") if r.get("v") is not None}),
            "screen_range": run_query(
                "MATCH (s:Spec {key:'standing_screen_display_size'}) WHERE s.numeric_value IS NOT NULL "
                "RETURN min(s.numeric_value) AS lo, max(s.numeric_value) AS hi")[0],
        }
    except Exception:
        enum_cache = {
            "technology":   ["5g", "4g lte", "4g", "lte", "3g", "gsm", "cdma",
                             "wi-fi", "bluetooth", "nfc", "volte", "usb"],
            "carrier":      ["at&t", "t-mobile", "verizon", "cricket", "sprint",
                             "boost mobile", "tracfone", "straight talk", "google fi"],
            "camera_mp":    [2.0, 3.0, 5.0, 8.0, 12.0, 13.0, 16.0],
            "screen_range": {"lo": 3.0, "hi": 7.5},
        }
    return enum_cache


def intent_prompt() -> str:
    e = load_enums()
    return f"""\
Trích xuất điều kiện filter từ câu hỏi tìm kiếm điện thoại. Trả về JSON thuần, không markdown.

Schema:
{{
  "brand":      string | string[] | null,
  "technology": string | string[] | null,
  "carrier":    string | string[] | null,
  "price_min":  number | null,
  "price_max":  number | null,
  "rating_min": number | null,
  "specs": [
    {{
      "key":  string,        // spec key (xem bảng bên dưới)
      "min":  number | null, // so sánh >=  (ít nhất / từ / trên)
      "max":  number | null, // so sánh <=  (tối đa / dưới / đến)
      "unit": string | null  // đơn vị VIẾT THƯỜNG: "gb", "mah", "mp", "ghz"
    }}
  ]
}}

Enum Technology — dùng CHÍNH XÁC (lowercase):
  {e['technology']}

Enum Carrier — dùng CHÍNH XÁC (lowercase):
  {e['carrier']}

Bảng Spec keys (chỉ dùng các key dưới đây, không tự đặt key khác):
  Ý định người dùng              | key                           | unit  | Giá trị có trong graph
  ──────────────────────────────|──────────────────────────────|───────|─────────────────────────────────────
  RAM, bộ nhớ RAM               | ram                           | gb    | (bất kỳ, lưu trực tiếp trên product)
  bộ nhớ trong, ROM, storage    | memory_storage_capacity       | gb    | (bất kỳ, lưu trực tiếp trên product)
  màn hình, screen size         | standing_screen_display_size  | inch  | {e['screen_range']['lo']}–{e['screen_range']['hi']} inch
  camera (bất kỳ loại nào)      | other_camera_features         | mp    | {e['camera_mp']} MP
  tốc độ CPU, chip speed        | processor                     | ghz   | (ít node, ưu tiên title fallback)

Lưu ý:
  - Dung lượng pin (mAh), camera trước KHÔNG có key spec → KHÔNG tạo specs entry,
    hệ thống sẽ tự tìm trong tiêu đề sản phẩm.
  - Camera nếu user hỏi > 16MP → graph không có node tương ứng, specs entry vẫn hữu ích
    vì title fallback sẽ dùng giá trị min để tìm "48mp" trong tiêu đề.
  - Nếu người dùng không đề cập spec rõ ràng → specs: [].

Ví dụ:
  "Samsung 5G RAM ít nhất 8GB"
    → {{"brand":"Samsung","technology":"5g","specs":[{{"key":"ram","min":8,"max":null,"unit":"gb"}}]}}
  "màn hình 6.7 inch, 128GB storage"
    → {{"specs":[{{"key":"standing_screen_display_size","min":6.7,"max":null,"unit":"inch"}},{{"key":"memory_storage_capacity","min":128,"max":null,"unit":"gb"}}]}}
  "pin 5000mAh camera 48MP"
    → {{"specs":[]}}   // không có key phù hợp → để trống, title fallback xử lý
  "bộ nhớ từ 128 đến 256GB"
    → {{"specs":[{{"key":"memory_storage_capacity","min":128,"max":256,"unit":"gb"}}]}}
  "hỗ trợ AT&T và T-Mobile"
    → {{"carrier":["at&t","t-mobile"]}}

Chuyển intent người dùng sang dạng filter bằng kiến thức của bạn dựa trên key ở trên (chuyển nhẹ).
Ví dụ:
    "Điện thoại ram cao"
    → {{"specs":[{{"key":"ram","min":8,"max":null,"unit":"gb"}}]}} 
    "Điện thoại pin trâu"
    → {{"specs":[]}}  // không có key phù hợp, để spec trống
    "Điện thoại chụp hình đẹp"
    → {{"specs":[{{"key":"other_camera_features","min":12,"max":null,"unit":"mp"}}]}}  // camera tốt thường từ 12MP trở lên
    ...
Không có filter rõ ràng → trả về {{}}.
Chỉ JSON, không giải thích.\
"""


def escape_cypher(val: str) -> str:
    return val.replace("'", "\\'")


def fmt_num(n) -> str:
    f = float(n)
    return str(int(f)) if f == int(f) else str(f)


def label_num_cond(num, unit: str) -> str:
    n = fmt_num(num)
    u = escape_cypher(unit.lower())
    return f"(p.label CONTAINS '{n}{u}' OR p.label CONTAINS '{n} {u}')"


def build_filter_query(intent: dict) -> str | None:
    def str_or_list(key: str) -> list[str]:
        v = intent.get(key)
        if not v:
            return []
        return v if isinstance(v, list) else [v]

    lines: list[str] = ["MATCH (p:Product)"]
    carry: list[str] = []
    where_conds: list[str] = []
    title_conds: list[str] = []

    def add_optional(match_line: str, collect_expr: str, alias: str) -> None:
        lines.append(match_line)
        with_parts = ["p"] + carry + [f"{collect_expr} AS {alias}"]
        lines.append(f"WITH {', '.join(with_parts)}")
        carry.append(alias)

    brands = str_or_list("brand")
    if brands:
        add_optional(
            "OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)",
            "COLLECT(b.label)", "brand_labels",
        )
        if len(brands) == 1:
            where_conds.append(f"ANY(bl IN brand_labels WHERE bl CONTAINS '{escape_cypher(brands[0].lower())}')")
            title_conds.append(f"p.label CONTAINS '{escape_cypher(brands[0].lower())}'")
        else:
            cond = " OR ".join(f"bl CONTAINS '{escape_cypher(br.lower())}'" for br in brands)
            where_conds.append(f"ANY(bl IN brand_labels WHERE {cond})")
            tl = " OR ".join(f"p.label CONTAINS '{escape_cypher(br.lower())}'" for br in brands)
            title_conds.append(f"({tl})")

    techs = str_or_list("technology")
    if techs:
        add_optional(
            "OPTIONAL MATCH (p)-[:USES_TECHNOLOGY]->(t:Technology)",
            "COLLECT(t.label)", "tech_labels",
        )
        if len(techs) == 1:
            where_conds.append(f"ANY(tl IN tech_labels WHERE tl CONTAINS '{escape_cypher(techs[0].lower())}')")
            title_conds.append(f"p.label CONTAINS '{escape_cypher(techs[0].lower())}'")
        else:
            cond = " OR ".join(f"tl CONTAINS '{escape_cypher(tc.lower())}'" for tc in techs)
            where_conds.append(f"ANY(tl IN tech_labels WHERE {cond})")
            tl = " OR ".join(f"p.label CONTAINS '{escape_cypher(tc.lower())}'" for tc in techs)
            title_conds.append(f"({tl})")

    carriers = str_or_list("carrier")
    if carriers:
        add_optional(
            "OPTIONAL MATCH (p)-[:SUPPORTS_CARRIER]->(c:Carrier)",
            "COLLECT(c.label)", "carrier_labels",
        )
        if len(carriers) == 1:
            where_conds.append(f"ANY(cl IN carrier_labels WHERE cl CONTAINS '{escape_cypher(carriers[0].lower())}')")
            title_conds.append(f"p.label CONTAINS '{escape_cypher(carriers[0].lower())}'")
        else:
            cond = " OR ".join(f"cl CONTAINS '{escape_cypher(ca.lower())}'" for ca in carriers)
            where_conds.append(f"ANY(cl IN carrier_labels WHERE {cond})")
            tl = " OR ".join(f"p.label CONTAINS '{escape_cypher(ca.lower())}'" for ca in carriers)
            title_conds.append(f"({tl})")

    # RAM và storage lưu thẳng trên Product node, các spec khác dùng HAS_SPEC
    prop_specs = {
        "ram":                      "ram_gb",
        "ram_memory_installed_size": "ram_gb",
        "memory_storage_capacity":  "storage_gb",
    }

    for i, sc in enumerate(intent.get("specs") or []):
        key  = str(sc.get("key", "")).strip()
        mn   = sc.get("min")
        mx   = sc.get("max")
        unit = str(sc.get("unit") or "").lower().strip()
        if not key or (mn is None and mx is None):
            continue

        if key in prop_specs:
            prop = prop_specs[key]
            if mn is not None:
                where_conds.append(f"p.{prop} >= {float(mn)}")
                if unit:
                    title_conds.append(label_num_cond(mn, unit))
            if mx is not None:
                where_conds.append(f"p.{prop} <= {float(mx)}")
        else:
            alias = f"s{i}_vals"
            match_props = f"key: '{escape_cypher(key)}'" + (f", unit: '{escape_cypher(unit)}'" if unit else "")
            add_optional(
                f"OPTIONAL MATCH (p)-[:HAS_SPEC]->(s{i}:Spec {{{match_props}}})",
                f"COLLECT(s{i}.numeric_value)", alias,
            )
            checks: list[str] = []
            if mn is not None:
                checks.append(f"v >= {float(mn)}")
                if unit:
                    title_conds.append(label_num_cond(mn, unit))
            if mx is not None:
                checks.append(f"v <= {float(mx)}")
            if checks:
                where_conds.append(f"ANY(v IN {alias} WHERE {' AND '.join(checks)})")
    if intent.get("price_min") is not None:
        where_conds.append(f"p.price >= {float(intent['price_min'])}")
    if intent.get("price_max") is not None:
        where_conds.append(f"p.price <= {float(intent['price_max'])}")
    if intent.get("rating_min") is not None:
        where_conds.append(f"p.average_rating >= {float(intent['rating_min'])}")

    if not where_conds and not title_conds:
        return None

    strict_str = " AND ".join(where_conds)
    title_str  = " AND ".join(title_conds)

    if strict_str and title_str:
        where_clause = f"WHERE ({strict_str})\n   OR ({title_str})"
    else:
        where_clause = f"WHERE {strict_str or title_str}"

    lines.append(where_clause)
    lines.append(
        "WITH DISTINCT p\n"
        "OPTIONAL MATCH (u:User)-[r:RATE]->(p)\n"
        "WITH p.asin AS product_id, COUNT(r) AS rating_count, AVG(r.rating) AS avg_rating\n"
        f"RETURN product_id, rating_count, avg_rating  ORDER BY rating_count DESC LIMIT {TOP_K}"
    )
    return "\n".join(lines)


def minmax(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    return [0.5] * len(vals) if hi == lo else [(v - lo) / (hi - lo) for v in vals]


def pop_scores(rows: list[dict]) -> dict[str, float]:
    valid = [r for r in rows if r.get("avg_rating") and (r.get("rating_count") or 0) >= MIN_RATINGS]
    if not valid:
        return {}
    mu = sum(r["avg_rating"] for r in valid) / len(valid)
    bay = {
        r["product_id"]: (
            (MIN_RATINGS * mu + r["avg_rating"] * (r.get("rating_count") or 0))
            / (MIN_RATINGS + (r.get("rating_count") or 0))
            if (r.get("rating_count") or 0) >= MIN_RATINGS else mu
        )
        for r in rows if r.get("product_id")
    }
    lo, hi = min(bay.values()), max(bay.values())
    return {k: 0.5 for k in bay} if hi == lo else {k: (v - lo) / (hi - lo) for k, v in bay.items()}


def search_ranked(query: str, user_id: str | None = None) -> list[str]:
    return search_ranked_with_trace(query, user_id)[0]


def search_ranked_with_trace(
    query: str,
    user_id: str | None = None,
    cold_start_kgat: bool = False
) -> tuple[list[str], dict[str, Any]]:
    trace: dict[str, Any] = {"query": query, "pipeline_mode": "pipeline", "error": None, "steps": []}

    en_query = chat([
        {"role": "system", "content": "Translate the following product search query to English. Return only the translated text, no explanation."},
        {"role": "user",   "content": query},
    ], max_tokens=1024).strip()
    if not en_query:
        en_query = query
    trace["steps"].append({
        "id": "translate",
        "title": "Translate Query",
        "payload": {"original": query, "translated": en_query},
    })

    raw = chat([
        {"role": "system", "content": intent_prompt()},
        {"role": "user",   "content": en_query},
    ], max_tokens=1024)
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE).strip()
    try:
        intent = json.loads(raw) if raw and raw != "{}" else {}
    except Exception:
        intent = {}
    filter_q = build_filter_query(intent)
    trace["steps"].append({
        "id": "nl2cypher",
        "title": "NL → Intent & Filter Query",
        "payload": {"intent": intent, "filter_query": filter_q},
    })

    sem_q = (
        f"CALL db.index.vector.queryNodes('product_text_index', {200}, $query_embedding) "
        "YIELD node AS p, score AS sem_score "
        "OPTIONAL MATCH (u:User)-[r:RATE]->(p) "
        "WITH p.asin AS product_id, sem_score, COUNT(r) AS rating_count, AVG(r.rating) AS avg_rating "
        "RETURN product_id, sem_score, rating_count, avg_rating"
    )

    embedding = embed(en_query)

    fallback_used = False

    if filter_q is None:
        filter_rows = []
        fallback_used = True
        trace["steps"][1]["payload"]["fallback"] = "no_intent"
    else:
        filter_rows = run_query(filter_q)
        if not filter_rows:
            fallback_used = True
            trace["steps"][1]["payload"]["fallback"] = "no_results"

    sem_rows = run_query(sem_q, {"query_embedding": embedding})
    trace["steps"].append({
        "id": "neo4j",
        "title": "Neo4j Search",
        "payload": {
            "filter_count": len(filter_rows),
            "sem_count": len(sem_rows),
            "fallback": fallback_used,
        },
    })

    print(f"\n{'─'*60}")
    print(f"[query]       {query}")
    print(f"[translated]  {en_query}")
    print(f"[intent]      {intent}")
    print(f"[filter_q]\n{filter_q}")
    print(f"[filter_rows] {len(filter_rows)}  fallback={fallback_used}")
    print(f"[sem_rows]    {len(sem_rows)}")
    print(f"{'─'*60}\n")

    sem_map  = {r["product_id"]: r.get("sem_score", 0.0) for r in sem_rows}
    all_rows = {r["product_id"]: r for r in [*sem_rows, *filter_rows]}
    pop_map  = pop_scores(list(all_rows.values()))

    scores: dict[str, float] = {}
    for r in filter_rows:
        pid = r["product_id"]
        scores[pid] = FILTER_BONUS + sem_map.get(pid, 0.0) * SEM_W + pop_map.get(pid, 0.0) * POP_W
    for r in sem_rows:
        pid = r["product_id"]
        if pid not in scores:
            scores[pid] = r.get("sem_score", 0.0) * SEM_W + pop_map.get(pid, 0.0) * POP_W

    if not scores:
        return [], trace

    asins  = sorted(scores, key=lambda p: -scores[p])[:TOP_K]
    g_vals = [scores[p] for p in asins]
    trace["steps"].append({
        "id": "graph_scoring",
        "title": "Graph Scoring",
        "payload": {"count": len(asins)},
    })

    try:
        ranker = get_reranker()
        is_known = bool(user_id) and f"user_{user_id}" in ranker.entity2id
        if is_known:
            kgat_pairs = ranker.rerank(user_id, asins)
            k_vals = [s for _, s in sorted(kgat_pairs, key=lambda x: asins.index(x[0]))]
            trace["steps"].append({
                "id": "rerank",
                "title": "KGAT Rerank",
                "payload": {"mode": "kgat", "top5": [a for a, _ in kgat_pairs[:5]]},
            })
        elif cold_start_kgat:
            kgat_pairs = ranker.rerank(user_id or "__cold_start__", asins)
            k_vals = [s for _, s in sorted(kgat_pairs, key=lambda x: asins.index(x[0]))]
            trace["steps"].append({
                "id": "rerank",
                "title": "KGAT Rerank",
                "payload": {"mode": "kgat_cold_start_centroid",
                            "top5": [a for a, _ in kgat_pairs[:5]]},
            })
        else:
            k_vals = [0.0] * len(asins)
            trace["steps"].append({
                "id": "rerank",
                "title": "KGAT Rerank",
                "payload": {"mode": "skipped_cold_start"},
            })
    except Exception as e:
        k_vals = [0.0] * len(asins)
        trace["steps"].append({
            "id": "rerank",
            "title": "KGAT Rerank",
            "payload": {"error": str(e), "fallback": True},
        })

    g_norm = minmax(g_vals)
    k_norm = minmax(k_vals)
    ranked = sorted(
        zip(asins, [0.5 * k + 0.5 * g for k, g in zip(k_norm, g_norm)]),
        key=lambda x: -x[1],
    )
    print(f"số lượng kết quả: {len(ranked)}")
    print(trace)
    return [pid for pid, _ in ranked], trace


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test search_pipeline thủ công")
    parser.add_argument("query",  nargs="?", default=None, help="Query cần tìm kiếm")
    parser.add_argument("--user", default=None, help="user_id (tuỳ chọn)")
    parser.add_argument("--top",  type=int, default=10, help="Số kết quả hiển thị (mặc định: 10)")
    parser.add_argument("--loop", action="store_true", help="Chế độ interactive (gõ query liên tục)")
    args = parser.parse_args()

    def run_and_print(q: str, uid: str | None, top_n: int) -> None:
        print(f"\n{'═'*60}")
        print(f"QUERY   : {q}")
        print(f"USER_ID : {uid or '(anonymous)'}")
        print(f"{'═'*60}")
        try:
            results, trace = search_ranked_with_trace(q, uid)
        except Exception as exc:
            print(f"[ERROR] {exc}")
            return

        print(f"\nTop-{top_n} kết quả ({len(results)} tổng):")
        for i, pid in enumerate(results[:top_n], 1):
            print(f"  {i:>2}. {pid}")

        print("\nTrace:")
        for step in trace.get("steps", []):
            sid     = step.get("id", "?")
            payload = step.get("payload", {})
            if sid == "translate":
                print(f"  [translate]   {payload.get('original')!r} → {payload.get('translated')!r}")
            elif sid == "nl2cypher":
                print(f"  [intent]      {payload.get('intent')}")
                if payload.get("fallback"):
                    print(f"  [fallback]    {payload['fallback']}")
            elif sid == "neo4j":
                print(f"  [neo4j]       filter={payload.get('filter_count')}, sem={payload.get('sem_count')}, fallback={payload.get('fallback')}")
            elif sid == "graph_scoring":
                print(f"  [scoring]     candidates={payload.get('count')}")
            elif sid == "rerank":
                mode = payload.get("mode")
                if mode == "kgat":
                    print(f"  [rerank]      KGAT, top5={payload.get('top5')}")
                elif mode == "skipped_cold_start":
                    print(f"  [rerank]      skipped (cold-start user)")
                elif payload.get("error"):
                    print(f"  [rerank]      ERROR: {payload['error']}")
        print()

    if args.loop:
        print("=== Interactive mode (Ctrl-C để thoát) ===")
        while True:
            try:
                q = input("\nQuery: ").strip()
                if not q:
                    continue
                uid = args.user or input("User ID (Enter để bỏ qua): ").strip() or None
                run_and_print(q, uid, args.top)
            except (KeyboardInterrupt, EOFError):
                print("\nBye!")
                break
    elif args.query:
        run_and_print(args.query, args.user, args.top)
    else:
        samples = [
            ("Samsung 5G", None),
            ("điện thoại pin trâu giá dưới 300 đô", None),
            ("iPhone 128GB", None),
        ]
        for q, uid in samples:
            run_and_print(q, uid, args.top)
