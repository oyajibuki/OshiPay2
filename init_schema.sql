-- Supabase Dashboard の SQL Editor で以下のSQLを実行してください。
-- ※ supports テーブルがまだない場合は全部実行、すでにある場合は「既存テーブルの拡張」以降だけ実行

-- ========================================
-- 1. 応援データテーブル（まだ存在しない場合）
-- ========================================
CREATE TABLE IF NOT EXISTS public.supports (
    id           BIGSERIAL    PRIMARY KEY,
    support_id   UUID         UNIQUE NOT NULL,
    creator_acct TEXT         NOT NULL,
    creator_name TEXT         NOT NULL,
    amount       INTEGER      NOT NULL,
    message      TEXT         DEFAULT '',
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    reply_emoji  TEXT,
    reply_text   TEXT,
    replied_at   TIMESTAMPTZ,
    -- 将来のマーケット機能用（今は使わない）
    owner_id     TEXT,
    is_listed    BOOLEAN      DEFAULT FALSE,
    list_price   INTEGER
);
-- RLS（Row Level Security）を無効化 ─ サーバーサイドのみアクセスするため
ALTER TABLE public.supports DISABLE ROW LEVEL SECURITY;

-- ========================================
-- 2. クリエイター認証テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS public.creators (
    acct_id      TEXT         PRIMARY KEY,
    password_hash TEXT        NOT NULL,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ========================================
-- 3. サポーター認証テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS public.supporters (
    supporter_id  TEXT        PRIMARY KEY,
    display_name  TEXT        NOT NULL,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ========================================
-- 4. 既存の supports テーブルの拡張
-- ========================================
-- supporter_id カラム追加（過去の応援と紐付け用）
ALTER TABLE public.supports ADD COLUMN IF NOT EXISTS supporter_id TEXT;

-- パフォーマンス向上のためのインデックス
CREATE INDEX IF NOT EXISTS idx_supports_supporter_id ON public.supports(supporter_id);
