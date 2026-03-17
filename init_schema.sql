-- ============================================
-- OshiPay DB セットアップ（完全版・冪等）
-- 何度実行しても安全（IF NOT EXISTS / DROP IF EXISTS を使用）
-- ============================================

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

-- ========================================
-- 5. creators テーブルにプロフィールカラム追加
--    ※ フェーズ1 ガバナンス対応
-- ========================================
-- ユーザーID（URL slug）: oshipay.com/username
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS slug          TEXT UNIQUE;
-- 表示名（ニックネーム）
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS display_name  TEXT;
-- プロフィール文章（最大500文字）
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS bio           TEXT DEFAULT '';
-- ジャンル
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS genre         TEXT DEFAULT '';
-- アイコン画像URL（Supabase Storage）
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS photo_url     TEXT DEFAULT '';
-- SNSリンク（JSON形式: {"x":"https://...","instagram":"https://..."}）
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS sns_links     JSONB DEFAULT '{}';
-- アカウント削除フラグ（削除後もslugをロック保持）
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS is_deleted    BOOLEAN DEFAULT FALSE;
-- プロフィール設定完了フラグ
ALTER TABLE public.creators ADD COLUMN IF NOT EXISTS profile_done  BOOLEAN DEFAULT FALSE;

-- slug 検索用インデックス
CREATE INDEX IF NOT EXISTS idx_creators_slug ON public.creators(slug);
-- 削除済みアカウントのインデックス
CREATE INDEX IF NOT EXISTS idx_creators_is_deleted ON public.creators(is_deleted);

-- ========================================
-- 6. 削除済みslugロックテーブル
--    アカウント削除後もURLをロック（なりすまし防止）
-- ========================================
CREATE TABLE IF NOT EXISTS public.deleted_slugs (
    slug        TEXT PRIMARY KEY,
    acct_id     TEXT NOT NULL,
    deleted_at  TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.deleted_slugs DISABLE ROW LEVEL SECURITY;
