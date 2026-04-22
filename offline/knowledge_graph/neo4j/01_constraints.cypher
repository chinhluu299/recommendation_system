// ============================================================
// 01_constraints.cypher
// Tạo constraints (unique) và indexes trước khi import dữ liệu.
// Chạy file này ĐẦU TIÊN để đảm bảo hiệu năng LOAD CSV.
//
// Usage:
//   cypher-shell -u neo4j -p <password> --file 01_constraints.cypher
// ============================================================

// ── Unique constraints (cũng tự động tạo index) ──────────────

CREATE CONSTRAINT product_id IF NOT EXISTS
  FOR (n:Product) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT brand_id IF NOT EXISTS
  FOR (n:Brand) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT category_id IF NOT EXISTS
  FOR (n:Category) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT feature_id IF NOT EXISTS
  FOR (n:Feature) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT spec_id IF NOT EXISTS
  FOR (n:Spec) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT carrier_id IF NOT EXISTS
  FOR (n:Carrier) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT technology_id IF NOT EXISTS
  FOR (n:Technology) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT accessory_id IF NOT EXISTS
  FOR (n:Accessory) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT store_id IF NOT EXISTS
  FOR (n:Store) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT user_id IF NOT EXISTS
  FOR (n:User) REQUIRE n.id IS UNIQUE;

// ── Additional indexes cho các property thường xuyên filter ──

CREATE INDEX product_asin IF NOT EXISTS
  FOR (n:Product) ON (n.asin);

CREATE INDEX product_price IF NOT EXISTS
  FOR (n:Product) ON (n.price);

CREATE INDEX product_rating IF NOT EXISTS
  FOR (n:Product) ON (n.average_rating);

// Shortcut properties cho RAM/Storage filter (không cần MATCH Spec)
CREATE INDEX product_ram_gb IF NOT EXISTS
  FOR (n:Product) ON (n.ram_gb);

CREATE INDEX product_storage_gb IF NOT EXISTS
  FOR (n:Product) ON (n.storage_gb);

CREATE INDEX spec_key IF NOT EXISTS
  FOR (n:Spec) ON (n.key);

// Composite index: MATCH (s:Spec {key: '...', unit: '...'}) → cực nhanh
CREATE INDEX spec_key_unit IF NOT EXISTS
  FOR (n:Spec) ON (n.key, n.unit);

CREATE INDEX spec_numeric_value IF NOT EXISTS
  FOR (n:Spec) ON (n.numeric_value);

CREATE INDEX brand_label IF NOT EXISTS
  FOR (n:Brand) ON (n.label);

CREATE INDEX carrier_label IF NOT EXISTS
  FOR (n:Carrier) ON (n.label);

CREATE INDEX technology_label IF NOT EXISTS
  FOR (n:Technology) ON (n.label);

CREATE INDEX user_user_id IF NOT EXISTS
  FOR (n:User) ON (n.user_id);
