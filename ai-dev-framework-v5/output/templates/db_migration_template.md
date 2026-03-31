# DB MIGRATION TEMPLATE — TradeOS v5.1
Naming: V{N}__{description}.sql
All migrations must be idempotent (CREATE TABLE IF NOT EXISTS).
All tables: UUID PK, soft delete (deleted_at), updated_at trigger.
