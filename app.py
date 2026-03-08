import os
import io
import base64
import uuid
import random
import datetime

import streamlit as st
import streamlit.components.v1 as components
import stripe
import qrcode
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate
from PIL import Image

# ── ページ設定 ──
st.set_page_config(
    page_title="OshiPay — 応援を、もっとシンプルに。",
    page_icon="🔥",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Stripe設定
try:
    stripe.api_key = st.secrets["STRIPE_SECRET"]
except Exception:
    stripe.api_key = os.environ.get("STRIPE_SECRET", "")

# 定数
PRESET_AMOUNTS = [100, 500, 1000, 5000, 10000, 30000]
PLATFORM_FEE_PERCENT = 10
ICON_OPTIONS = {
    "🎤": "歌手・MC", "🎸": "ギター・バンド", "🎹": "ピアノ・キーボード",
    "🎨": "アーティスト・絵描き", "📷": "カメラマン・写真家", "☕": "カフェ・バリスタ",
    "✂️": "美容師・理容師", "🎮": "ゲーマー・配信者", "📚": "講師・先生",
    "💻": "エンジニア・クリエイター", "🎭": "役者・パフォーマー", "🔥": "その他",
}
BASE_URL = os.environ.get("APP_URL", "https://oshipay2.streamlit.app")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ヘルパー関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def read_html_file(file_path):
    """HTMLファイルをディスクから読み込む"""
    try:
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(cur_dir, file_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

def inject_top_scroll_script(html_content):
    """ページ上部へのスクロールを強制するJSを注入"""
    script = """
    <script>
    if (window.top !== window.self) {
        window.scrollTo(0, 0);
    }
    document.addEventListener("DOMContentLoaded", function() {
        window.scrollTo(0, 0);
    });
    </script>
    """
    if "</body>" in html_content:
        return html_content.replace("</body>", f"{script}</body>")
    return html_content + script

def create_connect_account():
    account = stripe.Account.create(
        type="express", country="JP",
        capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
        business_type="individual",
        business_profile={
            "mcc": "7922", 
            "product_description": "OshiPay - 投げ銭サービス",
            "url": BASE_URL
        },
    )
    return account.id

def create_account_link(account_id, return_params=""):
    return_url = f"{BASE_URL}?page=dashboard&acct={account_id}{return_params}"
    refresh_url = f"{BASE_URL}?page=dashboard&acct={account_id}&refresh=1{return_params}"
    link = stripe.AccountLink.create(
        account=account_id, refresh_url=refresh_url, return_url=return_url, type="account_onboarding",
    )
    return link.url

def send_support_email(to_email, creator_name, amount, message):
    try:
        smtp_server = st.secrets.get("SMTP_SERVER"); smtp_port = st.secrets.get("SMTP_PORT", 587)
        smtp_user = st.secrets.get("SMTP_USER"); smtp_pass = st.secrets.get("SMTP_PASS")
        if not all([smtp_server, smtp_user, smtp_pass]): return False, "SMTP設定不足"
        subject = f"🔥 {creator_name}さんに応援が届きました！ (OshiPay)"
        body = f"{creator_name}さん\n\nOshiPayを通じて応援が届きました！\n\n💰 応援金額: {amount:,}円\n💬 メッセージ:\n{message if message else '（なし）'}\n\n--\nOshiPay\n{BASE_URL}"
        msg = MIMEText(body); msg["Subject"] = subject; msg["From"] = smtp_user; msg["To"] = to_email; msg["Date"] = formatdate(localtime=True)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(); server.login(smtp_user, smtp_pass); server.send_message(msg)
        return True, "送信成功"
    except Exception as e: return False, str(e)

def check_account_status(account_id):
    try:
        account = stripe.Account.retrieve(account_id)
        return {"charges_enabled": account.charges_enabled, "payouts_enabled": account.payouts_enabled, "details_submitted": account.details_submitted}
    except Exception: return None

def generate_qr_data(data: str) -> tuple[str, bytes]:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(data); qr.make(fit=True); qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    logo_path = "assets/oshi_logo.png"
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            qr_w, qr_h = qr_img.size; logo_size = int(qr_w * 0.22); logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            qr_img.paste(logo, ((qr_w-logo_size)//2, (qr_h-logo_size)//2), logo)
        except Exception: pass
    buf = io.BytesIO(); qr_img.save(buf, format="PNG"); qr_bytes = buf.getvalue(); b64 = base64.b64encode(qr_bytes).decode()
    return b64, qr_bytes

def get_font(size):
    font_path = "assets/NotoSansJP-Bold.ttf"
    if not os.path.exists(font_path):
        os.makedirs("assets", exist_ok=True)
        url = "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP-Bold.ttf"
        try:
            import urllib.request
            urllib.request.urlretrieve(url, font_path)
        except Exception:
            from PIL import ImageFont
            return ImageFont.load_default()
    try:
        from PIL import ImageFont
        return ImageFont.truetype(font_path, size)
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()

def generate_coin_image(creator_name, amount, date_str, support_id, tier="bronze"):
    from PIL import Image, ImageDraw
    size = 500
    img = Image.new("RGB", (size, size), "#08080f")
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    # Tier colour palette
    if tier == "gold":
        c_outer = "#a07800"; c_rim = "#c8a200"; c_face = "#ffd700"; c_hi = "#fff080"
        c_dark  = "#7a5500"; c_text = "#3d2800"; tier_label = "GOLD"; status_jp = "\u30e1\u30c3\u30bb\u30fc\u30b8\u8fd4\u4fe1\u3042\u308a"
    elif tier == "silver":
        c_outer = "#606060"; c_rim = "#909090"; c_face = "#c0c0c0"; c_hi = "#e8e8e8"
        c_dark  = "#505050"; c_text = "#1a1a1a"; tier_label = "SILVER"; status_jp = "\u30b9\u30bf\u30f3\u30d7\u8fd4\u4fe1\u3042\u308a"
    else:  # bronze
        c_outer = "#6b3510"; c_rim = "#9a5c20"; c_face = "#cd7f32"; c_hi = "#e8a060"
        c_dark  = "#5a2c08"; c_text = "#2a1000"; tier_label = "BRONZE"; status_jp = "\u5fdc\u63f4\u6e08\u307f"

    # Coin layers (concentric circles for metallic depth)
    draw.ellipse([cx-228, cy-228, cx+228, cy+228], fill=c_dark)    # shadow
    draw.ellipse([cx-220, cy-220, cx+220, cy+220], fill=c_outer)   # outer rim
    draw.ellipse([cx-208, cy-208, cx+208, cy+208], fill=c_rim)     # main rim
    draw.ellipse([cx-195, cy-195, cx+195, cy+195], fill=c_face)    # face
    draw.ellipse([cx-182, cy-182, cx+182, cy+182], fill=c_hi)      # highlight ring
    draw.ellipse([cx-168, cy-168, cx+168, cy+168], fill=c_face)    # inner face

    font_tier  = get_font(18)
    font_amt   = get_font(54)
    font_name  = get_font(22)
    font_small = get_font(15)

    # Tier badge (top of coin)
    try:
        draw.rounded_rectangle([cx-52, cy-148, cx+52, cy-118], radius=9, fill=c_dark)
    except AttributeError:
        draw.rectangle([cx-52, cy-148, cx+52, cy-118], fill=c_dark)
    draw.text((cx, cy-133), tier_label, font=font_tier, fill="#ffffff", anchor="mm")

    # Amount (large centre)
    draw.text((cx, cy-32), f"\u00a5{amount:,}", font=font_amt, fill=c_text, anchor="mm")

    # Creator name (truncate if too long)
    cn = creator_name if len(creator_name) <= 14 else creator_name[:13] + "\u2026"
    draw.text((cx, cy+32), cn, font=font_name, fill=c_text, anchor="mm")

    # Status label
    draw.text((cx, cy+78), status_jp, font=font_small, fill=c_dark, anchor="mm")

    # Date
    draw.text((cx, cy+112), date_str, font=font_small, fill=c_dark, anchor="mm")

    # ID
    draw.text((cx, cy+140), f"ID: {support_id[:8]}", font=font_small, fill=c_dark, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Supabase 永続化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from supabase import create_client, Client

REPLY_EMOJIS = ["👍", "❤️", "🙏", "🎉", "😊", "🔥", "✨", "🌟"]

@st.cache_resource
def get_db() -> Client:
    """Supabaseクライアントをシングルトンで返す"""
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )

def add_support(support_id: str, creator_acct: str, creator_name: str, amount: int, message: str, supporter_id: str = None) -> None:
    """応援記録を追加（support_idのUNIQUE制約で重複は自動無視）"""
    try:
        data = {
            "support_id": support_id,
            "creator_acct": creator_acct,
            "creator_name": creator_name,
            "amount": amount,
            "message": message,
        }
        if supporter_id:
            data["supporter_id"] = supporter_id
        get_db().table("supports").insert(data).execute()
    except Exception:
        pass  # unique制約違反（ページリロード時の重複）は無視

def get_support(support_id: str) -> dict | None:
    """support_id で1件取得"""
    try:
        resp = get_db().table("supports").select("*").eq("support_id", support_id).execute()
        return resp.data[0] if resp.data else None
    except Exception:
        return None

import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_creator(acct_id: str, password: str) -> bool:
    try:
        resp = get_db().table("creators").select("*").eq("acct_id", acct_id).execute()
        if not resp.data: return False
        return resp.data[0]["password_hash"] == hash_password(password)
    except Exception: return False

def register_creator(acct_id: str, password: str) -> bool:
    try:
        get_db().table("creators").insert({"acct_id": acct_id, "password_hash": hash_password(password)}).execute()
        return True
    except Exception: return False

def set_reply(support_id: str, emoji: str, text: str) -> bool:
    """クリエイターの返信を保存"""
    resp = get_db().table("supports").update({
        "reply_emoji": emoji,
        "reply_text": text,
        "replied_at": datetime.datetime.utcnow().isoformat(),
    }).eq("support_id", support_id).execute()
    return bool(resp.data)

def get_supports_for_creator(creator_acct: str) -> list:
    """クリエイターの応援一覧を新着順で返す"""
    resp = (
        get_db().table("supports")
        .select("*")
        .eq("creator_acct", creator_acct)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []

def load_supports() -> list:
    """テストページ用: 全件取得（新着順）"""
    resp = get_db().table("supports").select("*").order("created_at", desc=True).execute()
    return resp.data or []

def delete_all_supports() -> None:
    """テストページ用: 全データ削除"""
    get_db().table("supports").delete().neq("support_id", "").execute()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# スタイル & UIパーツ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Noto+Sans+JP:wght@400;700;900&display=swap');
#MainMenu, header, footer, .stDeployButton {visibility: hidden; display: none !important;}
[data-testid="stToolbar"], [data-testid="stDecoration"] {display: none !important;}
.stApp { background: #08080f !important; font-family: 'Inter', 'Noto Sans JP', sans-serif !important; }
.stMainBlockContainer, .block-container { position: relative; z-index: 1; padding-top: 2rem !important; }
.oshi-logo { text-align: center; margin-bottom: 6px; }
.oshi-logo .icon { font-size: 28px; }
.oshi-logo .text { font-size: 22px; font-weight: 800; background: linear-gradient(135deg, #8b5cf6, #ec4899, #f97316); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.oshi-tagline { text-align: center; font-size: 13px; color: rgba(240,240,245,0.35); margin-bottom: 28px; }
.section-title { font-size: 20px; font-weight: 700; text-align: center; color: #f0f0f5; margin-bottom: 6px; }
.section-subtitle { font-size: 13px; color: rgba(240,240,245,0.6); text-align: center; margin-bottom: 24px; }
.support-avatar { width: 72px; height: 72px; border-radius: 50%; background: linear-gradient(135deg, #8b5cf6, #ec4899, #f97316); display: flex; align-items: center; justify-content: center; font-size: 32px; margin: 0 auto 14px; box-shadow: 0 0 30px rgba(139,92,246,0.3); }
.support-name { font-size: 22px; font-weight: 800; text-align: center; color: #f0f0f5; }
.support-label { font-size: 13px; color: rgba(240,240,245,0.6); text-align: center; margin-bottom: 20px; }
.selected-amount-display { text-align: center; font-size: 36px; font-weight: 900; background: linear-gradient(135deg, #8b5cf6, #ec4899, #f97316); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 10px 0; }
.stButton > button { width: 100%; background: linear-gradient(135deg, #8b5cf6, #ec4899, #f97316) !important; color: white !important; border: none !important; border-radius: 9999px !important; padding: 16px !important; font-weight: 700 !important; }
.oshi-footer { text-align: center; margin-top: 24px; font-size: 11px; color: rgba(240,240,245,0.35); }
.oshi-footer a { color: #8b5cf6; text-decoration: none; }
.legal-links a { font-size: 10px; color: rgba(240,240,245,0.3); text-decoration: none; margin: 0 5px; }
.oshi-divider { height: 1px; background: rgba(255,255,255,0.08); margin: 20px 0; }
.qr-frame { background: white; padding: 16px; border-radius: 20px; display: inline-block; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)

# ── ルーティング ──
params = st.query_params
page = params.get("page", "lp")

# LocalStorage保存用の簡易JS
def save_account_id_js(acct_id):
    if acct_id:
        st.components.v1.html(f"""
        <script>localStorage.setItem('oshipay_acct', '{acct_id}');</script>
        """, height=0)

if page == "dashboard":
    save_account_id_js(params.get("acct"))

# 法務ページ用の幅調整
IS_LEGAL_PAGE = page in ["terms", "privacy", "legal"]

if page == "lp":
    st.markdown("<style>.stMainBlockContainer, .block-container { max-width: none !important; padding: 0 !important; margin: 0 !important; }</style>", unsafe_allow_html=True)
elif IS_LEGAL_PAGE:
    st.markdown("<style>.stMainBlockContainer, .block-container { max-width: 800px !important; margin: 0 auto; }</style>", unsafe_allow_html=True)
elif page == "reply_view":
    st.markdown("<style>.stMainBlockContainer, .block-container { max-width: 700px !important; margin: 0 auto; }</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>.stMainBlockContainer, .block-container { max-width: 460px !important; margin: 0 auto; }</style>", unsafe_allow_html=True)

# ── 外部HTMLファイルの表示 ──
LEGAL_MAP = {
    "terms": "role/index.html",
    "privacy": "role/index2.html",
    "legal": "role/index3v2.html"
}

if page in LEGAL_MAP:
    html_content = read_html_file(LEGAL_MAP[page])
    # スクロール位置リセット用JSを注入
    html_content = inject_top_scroll_script(html_content)
    components.html(html_content, height=900, scrolling=True)
    st.stop()

# ── ランディングページ ──
if page == "lp":
    lp_html = read_html_file("oshipay-lp/index.html")
    st.markdown("""
    <style>
    /* モバイル用の高さ調整 (幅768px以下) */
    @media (max-width: 768px) {
        iframe { height: 5800px !important; }
    }
    </style>
    """, unsafe_allow_html=True)
    components.html(lp_html, height=3750)
    st.markdown(f'<div style="text-align:center; padding-bottom: 40px;"><a href="{BASE_URL}?page=supporter_dashboard" target="_top" style="display:inline-block; background:rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.5); padding:10px 20px; border-radius:12px; color:#c4b5fd; text-decoration:none; font-weight:700; font-size:14px;">🦸 過去の応援を管理する（サポーターダッシュボードへ）</a></div>', unsafe_allow_html=True)
    st.stop()

# ── 成功ページ ──
if page == "success":
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:80px;margin-bottom:20px;">🎉</div><div class="section-title">応援完了！</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">ありがとうございます！🙏</div>', unsafe_allow_html=True)

    s_name = params.get("s_name", "")
    s_amt_str = params.get("s_amt", "0")
    s_acct = params.get("s_acct", "")
    s_msg = params.get("s_msg", "")
    s_sid = params.get("s_sid", "")
    s_sup_id = params.get("s_sup_id", "")

    # ── 応援金額のパース ──
    try:
        s_amt = int(s_amt_str)
    except ValueError:
        s_amt = 0

    # ── 応援記録を Supabase に保存（冪等: s_sid があれば1回のみ） ──
    if s_sid and s_acct and s_amt > 0:
        add_support(s_sid, s_acct, s_name, s_amt, s_msg, s_sup_id)

    # ── support_id を localStorage の履歴に追記 ──
    if s_sid:
        components.html(f"""
        <script>
        try {{
            var h = JSON.parse(localStorage.getItem('oshipay_history') || '[]');
            if (!h.includes('{s_sid}')) {{
                h.unshift('{s_sid}');
                if (h.length > 50) h = h.slice(0, 50);
                localStorage.setItem('oshipay_history', JSON.stringify(h));
            }}
        }} catch(e) {{}}
        </script>
        """, height=0)

    # ── 応援証明カード ──
    if s_sid:
        my_support_url = f"{BASE_URL}?page=my_support&sid={s_sid}"
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(236,72,153,0.1));
                    border: 1px solid rgba(139,92,246,0.35); border-radius: 16px;
                    padding: 20px; margin: 20px 0; text-align: center;">
            <div style="font-size: 28px; margin-bottom: 8px;">🏅</div>
            <div style="color: #f0f0f5; font-weight: 700; font-size: 15px; margin-bottom: 6px;">応援証明をブックマークしよう</div>
            <div style="font-size: 12px; color: rgba(240,240,245,0.65); margin-bottom: 14px;">
                クリエイターからの返信もここで確認できます
            </div>
            <a href="{my_support_url}" target="_top"
               style="display:inline-block; background: linear-gradient(135deg,#8b5cf6,#ec4899);
                      color:white; text-decoration:none; border-radius:9999px;
                      padding:10px 24px; font-weight:700; font-size:14px;">
                🎫 応援証明を見る
            </a>
        </div>
        """, unsafe_allow_html=True)

    # ── 応援メール送信 ──
    if s_acct and s_name and s_amt > 0:
        try:
            acct_info = stripe.Account.retrieve(s_acct)
            creator_email = acct_info.get("email", "")
            if creator_email:
                ok, err = send_support_email(creator_email, s_name, s_amt, s_msg)
                if not ok:
                    st.error(f"⚠️ 通知メールの送信に失敗しました。\nエラー内容: {err}")
        except Exception:
            pass  # メール失敗はサイレントに

    portfolio_url = f"{BASE_URL}?page=portfolio&id={s_sup_id}" if s_sup_id else BASE_URL
    share_text = f"{s_name}にOshiPayで応援したよ！\n{portfolio_url}\n#OshiPay2"
    st.link_button("𝕏 でシェア", f"https://twitter.com/intent/tweet?text={urllib.parse.quote(share_text)}", use_container_width=True)
    st.markdown(f'<div style="text-align:center;margin-top:20px;"><a href="{BASE_URL}?page=supporter_dashboard" target="_top" style="display:inline-block; font-size:14px; font-weight:700; color:#c4b5fd; text-decoration:none; background:rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.4); border-radius:12px; padding:10px 20px;">🦸 サポーター機能で応援を記録する</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center;margin-top:10px;"><a href="{BASE_URL}?page=my_history" target="_top" style="font-size:12px;color:rgba(240,240,245,0.4); text-decoration:underline;">（ブラウザ限定）簡易履歴を見る</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="oshi-footer">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="legal-links text-center pt-2"><a href="{BASE_URL}?page=terms" target="_top">利用規約</a><a href="{BASE_URL}?page=privacy" target="_top">プライバシーポリシー</a><a href="{BASE_URL}?page=legal" target="_top">特定商取引法</a></div>', unsafe_allow_html=True)
    st.stop()

# ── 応援証明ページ（サポーター向け）──
if page == "my_support":
    s_sid = params.get("sid", "")
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🏅 応援証明</div>', unsafe_allow_html=True)

    if not s_sid:
        st.error("応援IDが見つかりません。")
        st.stop()

    record = get_support(s_sid)
    if not record:
        st.warning("応援記録が見つかりません。決済直後の場合は数秒後に再読み込みしてください。")
        st.stop()

    # ── コインティア判定 ──
    has_reply_text  = bool(record.get("reply_text"))
    has_reply_emoji = bool(record.get("reply_emoji"))
    if has_reply_text:
        coin_tier    = "gold"
        tier_label   = "GOLD"; tier_color = "#ffd700"; status_text = "メッセージ返信あり 💬"
    elif has_reply_emoji:
        coin_tier    = "silver"
        tier_label   = "SILVER"; tier_color = "#c0c0c0"; status_text = "スタンプ返信あり ✨"
    else:
        coin_tier    = "bronze"
        tier_label   = "BRONZE"; tier_color = "#cd7f32"; status_text = "応援済み 🥉"

    amt_disp     = f"¥{record['amount']:,}"
    created_disp = record["created_at"][:10]

    # コイン画像生成
    b64_card = generate_coin_image(
        record['creator_name'], record['amount'], created_disp, record['support_id'], coin_tier
    )

    st.markdown(
        f'<div style="text-align:center; margin-bottom:20px;">'
        f'<img src="data:image/png;base64,{b64_card}" '
        f'style="width:260px; height:260px; border-radius:50%; box-shadow:0 8px 32px rgba(0,0,0,0.55);" /></div>',
        unsafe_allow_html=True,
    )

    st.download_button(
        label="📥 コインバッジを保存",
        data=base64.b64decode(b64_card),
        file_name=f"oshipay_coin_{record['support_id'][:8]}.png",
        mime="image/png",
        use_container_width=True,
    )

    # ── ステータスカード（内容は非表示・ステータスのみ）──
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
                border-radius: 16px; padding: 20px; margin: 16px 0;">
        <div style="display:flex; align-items:center; gap:12px;">
            <div style="width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#8b5cf6,#ec4899,#f97316);
                        display:flex;align-items:center;justify-content:center;font-size:20px;">🔥</div>
            <div style="flex:1;">
                <div style="color:#f0f0f5;font-weight:700;font-size:16px;">{record['creator_name']}</div>
                <div style="color:rgba(240,240,245,0.5);font-size:12px;">{created_disp} に応援</div>
            </div>
            <div style="font-size:22px;font-weight:900;
                        background:linear-gradient(135deg,#8b5cf6,#ec4899,#f97316);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                {amt_disp}
            </div>
        </div>
        <div style="margin-top:14px; display:flex; align-items:center; gap:8px;">
            <span style="display:inline-block; background:{tier_color}33; border:1px solid {tier_color}99;
                         color:{tier_color}; font-size:11px; font-weight:700; padding:3px 10px; border-radius:20px;">
                {tier_label}
            </span>
            <span style="font-size:12px; color:rgba(240,240,245,0.6);">{status_text}</span>
        </div>
        <div style="margin-top:8px; font-size:11px; color:rgba(240,240,245,0.35);">
            応援ID: {record['support_id'][:8]}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="oshi-footer" style="margin-top:28px;">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="legal-links text-center pt-2"><a href="{BASE_URL}?page=terms" target="_top">利用規約</a><a href="{BASE_URL}?page=privacy" target="_top">プライバシーポリシー</a><a href="{BASE_URL}?page=legal" target="_top">特定商取引法</a></div>', unsafe_allow_html=True)
    st.stop()

# ── 返信ダッシュボードページ（クリエイター向け）──
if page == "reply_view":
    rv_acct = params.get("acct", "")
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">💌 返信ダッシュボード</div>', unsafe_allow_html=True)

    if not rv_acct:
        st.error("アカウントIDが指定されていません。ダッシュボードから開いてください。")
        st.stop()

    supports = get_supports_for_creator(rv_acct)

    if not supports:
        st.markdown("""
        <div style="background:rgba(255,255,255,0.03);border:1px dashed rgba(255,255,255,0.12);
                    border-radius:12px;padding:32px;text-align:center;margin-top:20px;">
            <div style="font-size:48px;margin-bottom:12px;">📭</div>
            <div style="color:rgba(240,240,245,0.5);font-size:14px;">まだ応援が届いていません</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # 未返信 / 返信済み カウント
    unreplied = [s for s in supports if not s["reply_emoji"] and not s["reply_text"]]
    replied = [s for s in supports if s["reply_emoji"] or s["reply_text"]]
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("応援総数", f"{len(supports)}件")
    col_b.metric("未返信", f"{len(unreplied)}件")
    col_c.metric("返信済", f"{len(replied)}件")

    st.markdown('<div class="oshi-divider"></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:14px;color:rgba(240,240,245,0.6);margin-bottom:16px;">新着 {len(supports)} 件の応援メッセージ</div>', unsafe_allow_html=True)

    for idx, record in enumerate(supports):
        sid = record["support_id"]
        amt_disp = f"¥{record['amount']:,}"
        date_disp = record["created_at"][:10]
        msg_disp = record["message"] if record["message"] else "（メッセージなし）"
        has_reply = bool(record["reply_emoji"] or record["reply_text"])
        badge_color = "#22c55e" if has_reply else "#f97316"
        badge_text = "✅ 返信済" if has_reply else "⏳ 未返信"

        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);
                    border-radius:14px;padding:18px;margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <div style="font-size:22px;font-weight:900;
                            background:linear-gradient(135deg,#8b5cf6,#ec4899);
                            -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                    {amt_disp}
                </div>
                <span style="font-size:11px;font-weight:700;color:{badge_color};
                             background:rgba(255,255,255,0.06);border-radius:9999px;
                             padding:3px 10px;border:1px solid {badge_color}40;">
                    {badge_text}
                </span>
            </div>
            <div style="font-size:13px;color:rgba(240,240,245,0.75);margin-bottom:6px;">
                💬 {msg_disp}
            </div>
            <div style="font-size:11px;color:rgba(240,240,245,0.4);">{date_disp}</div>
        </div>
        """, unsafe_allow_html=True)

        # 返信フォーム (Streamlit ウィジェット)
        with st.expander("📝 返信する" if not has_reply else "✏️ 返信を編集", expanded=False):
            cols = st.columns(len(REPLY_EMOJIS))
            selected_emoji_key = f"emoji_{sid}"
            if selected_emoji_key not in st.session_state:
                st.session_state[selected_emoji_key] = record.get("reply_emoji") or REPLY_EMOJIS[0]

            for ci, em in enumerate(REPLY_EMOJIS):
                if cols[ci].button(em, key=f"em_{sid}_{ci}"):
                    st.session_state[selected_emoji_key] = em
                    st.rerun()

            chosen_emoji = st.session_state[selected_emoji_key]
            st.markdown(f'<div style="text-align:center;font-size:36px;margin:8px 0;">{chosen_emoji}</div>', unsafe_allow_html=True)

            reply_text = st.text_area(
                "メッセージ（任意）",
                value=record.get("reply_text") or "",
                max_chars=200,
                key=f"rtxt_{sid}",
                placeholder="ありがとう！いつも応援してくれて嬉しいです 😊",
            )

            if st.button("📨 送信する", key=f"send_{sid}", type="primary"):
                ok = set_reply(sid, chosen_emoji, reply_text)
                if ok:
                    st.success("返信を保存しました！")
                    st.rerun()
                else:
                    st.error("保存に失敗しました。")

            # 応援証明リンク
            proof_url = f"{BASE_URL}?page=my_support&sid={sid}"
            st.markdown(f'<div style="margin-top:8px;font-size:12px;color:rgba(240,240,245,0.4);">🔗 <a href="{proof_url}" target="_top" style="color:#8b5cf6;">応援証明ページを確認</a></div>', unsafe_allow_html=True)

    st.markdown(f'<div class="oshi-footer" style="margin-top:28px;">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.stop()

# ── 応援履歴ページ（サポーター向け）──
if page == "my_history":
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📋 応援履歴</div>', unsafe_allow_html=True)

    sids_param = params.get("sids", "")

    if not sids_param:
        # localStorageからsupport_idリストを読み込んでURLに付け直す
        components.html(f"""
        <script>
        try {{
            var h = JSON.parse(localStorage.getItem('oshipay_history') || '[]');
            if (h.length > 0) {{
                window.top.location.href = '{BASE_URL}?page=my_history&sids=' + h.join(',');
            }}
        }} catch(e) {{}}
        </script>
        """, height=60)
        st.markdown('<div style="text-align:center;color:rgba(240,240,245,0.45);font-size:13px;margin-top:20px;">読み込み中... または応援履歴がありません。</div>', unsafe_allow_html=True)
        st.stop()

    sids = [s.strip() for s in sids_param.split(",") if s.strip()][:50]
    records = [get_support(sid) for sid in sids]
    records = [r for r in records if r]

    if not records:
        st.markdown("""
        <div style="background:rgba(255,255,255,0.03);border:1px dashed rgba(255,255,255,0.12);
                    border-radius:12px;padding:32px;text-align:center;margin-top:20px;">
            <div style="font-size:48px;margin-bottom:12px;">📭</div>
            <div style="color:rgba(240,240,245,0.5);font-size:14px;">応援履歴がありません</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    st.markdown(f'<div style="font-size:13px;color:rgba(240,240,245,0.5);margin-bottom:16px;">{len(records)}件の応援記録</div>', unsafe_allow_html=True)

    for record in records:
        amt_disp = f"¥{record['amount']:,}"
        date_disp = record["created_at"][:10]
        msg_disp = record["message"] if record["message"] else "（メッセージなし）"
        has_reply = bool(record.get("reply_emoji") or record.get("reply_text"))
        proof_url = f"{BASE_URL}?page=my_support&sid={record['support_id']}"
        reply_badge = f'<span style="color:#22c55e;font-size:11px;">💬 返信あり</span>' if has_reply else '<span style="color:rgba(240,240,245,0.35);font-size:11px;">⏳ 返信待ち</span>'

        st.markdown(f"""
        <a href="{proof_url}" target="_top" style="text-decoration:none;">
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);
                    border-radius:14px;padding:16px;margin-bottom:10px;cursor:pointer;
                    transition:border-color 0.2s;" onmouseover="this.style.borderColor='rgba(139,92,246,0.4)'"
                    onmouseout="this.style.borderColor='rgba(255,255,255,0.1)'">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div style="font-weight:700;color:#f0f0f5;font-size:15px;">{record['creator_name']}</div>
                <div style="font-size:20px;font-weight:900;
                            background:linear-gradient(135deg,#8b5cf6,#ec4899);
                            -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                    {amt_disp}
                </div>
            </div>
            <div style="font-size:12px;color:rgba(240,240,245,0.6);margin-bottom:4px;">💬 {msg_disp}</div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:11px;color:rgba(240,240,245,0.35);">{date_disp}</div>
                {reply_badge}
            </div>
        </div>
        </a>
        """, unsafe_allow_html=True)

    st.markdown(f'<div style="text-align:center;margin-top:20px;"><a href="{BASE_URL}?page=supporter_dashboard" target="_top" style="display:inline-block; font-size:14px; font-weight:700; color:#c4b5fd; text-decoration:none; background:rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.4); border-radius:12px; padding:10px 20px;">🦸 IDを作ってクラウドで一括管理する</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="oshi-footer" style="margin-top:24px;">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.stop()

# ── キャンセル ──
if page == "cancel":
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:80px;margin-bottom:20px;">🤔</div><div class="section-title">キャンセルしました</div>', unsafe_allow_html=True)
    st.stop()

# ── テストページ（開発用）──
if page == "test":
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🧪 テスト用シミュレーター</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Stripe決済をスキップして機能を確認</div>', unsafe_allow_html=True)
    st.warning("⚠️ このページは開発テスト専用です。本番では使わないでください。")

    # ── テストデータを追加 ──
    with st.form("test_support_form"):
        st.markdown("#### 応援をシミュレート")
        c1, c2 = st.columns(2)
        t_creator = c1.text_input("クリエイター名", value="テストクリエイター")
        t_acct = c2.text_input("アカウントID", value="acct_test_001")
        t_amount = st.select_slider("応援金額", options=[100, 500, 1000, 3000, 5000, 10000], value=500)
        t_msg = st.text_input("メッセージ", value="いつも応援してます！")
        go = st.form_submit_button("🔥 テスト応援を追加する", type="primary", use_container_width=True)

    if go:
        new_sid = str(uuid.uuid4())
        add_support(new_sid, t_acct, t_creator, t_amount, t_msg)
        my_url = f"{BASE_URL}?page=my_support&sid={new_sid}"
        rv_url = f"{BASE_URL}?page=reply_view&acct={t_acct}"
        st.success(f"追加完了！ `{new_sid[:8]}...`")
        b1, b2 = st.columns(2)
        b1.link_button("🏅 応援証明を確認", my_url, use_container_width=True)
        b2.link_button("💌 返信ダッシュボード", rv_url, use_container_width=True)

    # ── 保存済みデータ一覧 ──
    all_supports = load_supports()
    st.markdown(f"#### 保存済みデータ（{len(all_supports)}件）")
    if not all_supports:
        st.info("まだデータがありません。上フォームから追加してください。")
    else:
        for s in reversed(all_supports):
            replied = s["reply_emoji"] or s["reply_text"]
            badge = f"✅ {s['reply_emoji']}" if replied else "⏳ 未返信"
            my_url = f"{BASE_URL}?page=my_support&sid={s['support_id']}"
            rv_url  = f"{BASE_URL}?page=reply_view&acct={s['creator_acct']}"
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);
                        border-radius:10px;padding:14px;margin-bottom:8px;font-size:13px;
                        color:rgba(240,240,245,0.85);">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <b style="color:#c4b5fd;">{s['creator_name']}</b>
                    <span style="font-weight:700;color:#f97316;">¥{s['amount']:,}</span>
                </div>
                <div style="font-size:11px;color:rgba(240,240,245,0.45);margin-bottom:4px;">
                    acct: {s['creator_acct']} &nbsp;|&nbsp; {s['created_at'][:10]}
                </div>
                <div style="margin-bottom:6px;">💬 {s['message'] or '（なし）'}</div>
                <div style="font-size:11px;color:rgba(240,240,245,0.5);margin-bottom:8px;">{badge}</div>
                <a href="{my_url}" target="_top" style="color:#8b5cf6;font-size:12px;margin-right:12px;">🏅 応援証明</a>
                <a href="{rv_url}" target="_top" style="color:#8b5cf6;font-size:12px;">💌 返信DL</a>
            </div>
            """, unsafe_allow_html=True)

        if st.button("🗑️ テストデータを全消去", type="secondary"):
            delete_all_supports()
            st.rerun()

    st.stop()

# ── 応援・ダッシュボード ──
support_user = params.get("user", "")
connect_acct = params.get("acct", "")
support_name = params.get("name", "")
support_icon = params.get("icon", "🎤")

if page == "support" and support_user:
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="support-avatar">{support_icon}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="support-name">{support_name or "Creator"}</div><div class="support-label">を応援しよう</div>', unsafe_allow_html=True)
    if "amt" not in st.session_state: st.session_state.amt = 100
    
    st.markdown('<div class="section-subtitle">応援する金額を選んで、メッセージを送ろう</div>', unsafe_allow_html=True)
    
    # 金額の選択肢（ドラム用）: 非線形で作成して操作性を向上
    # 100-1000(100刻み), 1000-10000(500刻み), 10000-100000(5000刻み), 100000-1000000(50000刻み)
    slider_options = (
        list(range(100, 1000, 100)) + 
        list(range(1000, 10000, 500)) + 
        list(range(10000, 100000, 5000)) + 
        list(range(100000, 1000001, 50000))
    )
    # 現在のamtがoptionsにない場合は一番近い値を探す
    current_amt = int(st.session_state.amt)
    if current_amt not in slider_options:
        current_amt = min(slider_options, key=lambda x: abs(x - current_amt))

    # ドラム型スライダー
    selected_amt = st.select_slider(
        "応援金額を選択 (ドラムロール)",
        options=slider_options,
        value=current_amt,
        key="amt_slider"
    )
    if selected_amt != st.session_state.amt:
        st.session_state.amt = selected_amt
        st.rerun()

    st.markdown(f'<div class="selected-amount-display">¥{int(st.session_state.amt):,}</div>', unsafe_allow_html=True)
    msg = st.text_area("応援メッセージ（オプション）", max_chars=140)
    
    # ボタンの無効化処理を追加
    is_disabled = st.session_state.amt < 100
    if is_disabled:
        st.info("💡 応援は100円から受け付けています。金額を選択してください。")

    # ── 改正特商法に基づく最終確認表示 ──
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 16px; margin-top: 20px; margin-bottom: 20px;">
        <div style="font-size: 13px; color: #f0f0f5; font-weight: 700; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px;">最終確認</div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-size: 12px; color: rgba(240,240,245,0.6);">支払総額（税込）</span>
            <span style="font-size: 14px; color: #f97316; font-weight: 700;">¥{int(st.session_state.amt):,}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-size: 12px; color: rgba(240,240,245,0.6);">支払時期</span>
            <span style="font-size: 12px; color: #f0f0f5;">決済手続き完了時</span>
        </div>
        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed rgba(255,255,255,0.1);">
            <div style="font-size: 11px; color: rgba(240,240,245,0.5); line-height: 1.4;">
                ※デジタルコンテンツおよび投げ銭の性質上、決済手続き完了後のキャンセル、返金、返品には一切応じられません。
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="oshi-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle" style="text-align:left; margin-bottom:5px;">🎫 あなたのサポーターID（任意）</div><div style="font-size:11px;color:rgba(240,240,245,0.5);margin-bottom:10px;">IDを入れると実績が自動でアカウントに紐づきます。</div>', unsafe_allow_html=True)
    _default_sup_id = st.session_state.get("supporter_auth", {}).get("supporter_id", "")
    opt_sup_id = st.text_input("サポーターID", value=_default_sup_id, placeholder="sup_xxxxxxxx", label_visibility="collapsed")

    if st.button("🔥 応援する！", disabled=is_disabled):
        amt = st.session_state.amt
        support_id = str(uuid.uuid4())  # 応援証明用ユニークID
        try:
            checkout_params = {
                "payment_method_types": ["card"], "mode": "payment",
                "line_items": [{"price_data": {"currency": "jpy", "product_data": {"name": f"{support_name}への応援"}, "unit_amount": amt}, "quantity": 1}],
                "success_url": f"{BASE_URL}?page=success&s_name={urllib.parse.quote(support_name)}&s_amt={amt}&s_acct={connect_acct}&s_msg={urllib.parse.quote(msg or '')}&s_sid={support_id}&s_sup_id={opt_sup_id}",
                "cancel_url": f"{BASE_URL}?page=cancel",
                "metadata": {"user_id": support_user, "message": msg, "support_id": support_id, "supporter_id": opt_sup_id}
            }
            if connect_acct:
                checkout_params["payment_intent_data"] = {"application_fee_amount": int(amt * 0.1)}
                session = stripe.checkout.Session.create(**checkout_params, stripe_account=connect_acct)
            else: session = stripe.checkout.Session.create(**checkout_params)
            st.markdown(f'<script>window.top.location.href = "{session.url}";</script>', unsafe_allow_html=True)
            st.link_button("💳 決済ページへ", session.url)
        except Exception as e: st.error(e)
    st.markdown(f'<div class="oshi-footer">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="legal-links text-center pt-2"><a href="{BASE_URL}?page=terms" target="_top">利用規約</a><a href="{BASE_URL}?page=privacy" target="_top">プライバシーポリシー</a><a href="{BASE_URL}?page=legal" target="_top">特定商取引法</a></div>', unsafe_allow_html=True)

# ── サポーター公開ポートフォリオ ──
elif page == "portfolio":
    st.markdown("<style>.stMainBlockContainer, .block-container { max-width: 600px !important; margin: 0 auto; }</style>", unsafe_allow_html=True)
    p_id = params.get("id", "")
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    if not p_id:
        st.error("サポーターIDが指定されていません。")
        st.stop()
        
    resp = get_db().table("supporters").select("*").eq("supporter_id", p_id).execute()
    if not resp.data:
        st.error("サポーターが見つかりません。")
        st.stop()
        
    supporter = resp.data[0]
    st.markdown(f'<div class="section-title">{supporter["display_name"]} の応援実績 🏅</div>', unsafe_allow_html=True)
    
    s_resp = get_db().table("supports").select("*").eq("supporter_id", p_id).order("created_at", desc=True).execute()
    s_data = s_resp.data or []
    
    if not s_data:
        st.write("まだ応援実績がありません。")
        st.stop()
        
    total_amount = sum(s["amount"] for s in s_data)
    creators = list(set([s["creator_name"] for s in s_data]))
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div style="background:rgba(255,165,0,0.1); border-radius:12px; padding:16px; text-align:center;"><div style="font-size:12px; color:rgba(255,255,255,0.6);">累計応援額</div><div style="font-size:24px; font-weight:700; color:#f97316;">¥{total_amount:,}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div style="background:rgba(139,92,246,0.1); border-radius:12px; padding:16px; text-align:center;"><div style="font-size:12px; color:rgba(255,255,255,0.6);">応援した推し</div><div style="font-size:24px; font-weight:700; color:#c4b5fd;">{len(creators)}人</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>### 🏆 応援実績リスト", unsafe_allow_html=True)
    for s in s_data:
        my_url = f"{BASE_URL}?page=my_support&sid={s['support_id']}"
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1); border-radius:12px; padding:16px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-weight:700;color:#f0f0f5;font-size:15px;">{s['creator_name']} 様へ ¥{s['amount']:,}</div>
                    <div style="font-size:11px;color:rgba(240,240,245,0.5);margin-top:4px;">{s['created_at'][:10]}</div>
                </div>
                <a href="{my_url}" target="_top" style="font-size:12px;color:#8b5cf6;text-decoration:none;">📄 証明証</a>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    share_text = f"私のOshiPay応援実績はこちら！総額 ¥{total_amount:,}\n{BASE_URL}?page=portfolio&id={p_id}\n#OshiPay2"
    st.link_button("𝕏 でドヤる", f"https://twitter.com/intent/tweet?text={urllib.parse.quote(share_text)}", use_container_width=True)
    st.link_button("🔥 あなたもOshiPayを始めよう", f"{BASE_URL}?page=lp", use_container_width=True)
    st.stop()

# ── サポーター用ダッシュボード ──
elif page == "supporter_dashboard":
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">サポーター・ダッシュボード</div>', unsafe_allow_html=True)
    
    if "supporter_auth" not in st.session_state:
        st.info("過去の応援を一つにまとめたり、ドヤるための公開ポートフォリオを作成できます。")
        tab_login, tab_register = st.tabs(["🔑 ログイン", "✨ 新規アカウント作成"])
        
        with tab_login:
            l_id = st.text_input("サポーターID", key="l_id", placeholder="sup_xxxxxxxx")
            l_pass = st.text_input("パスワード", type="password", key="l_pass")
            if st.button("ログイン", use_container_width=True):
                resp = get_db().table("supporters").select("*").eq("supporter_id", l_id).execute()
                if not resp.data:
                    st.error("アカウントが見つかりません。")
                else:
                    if resp.data[0]["password_hash"] == hash_password(l_pass):
                        st.session_state["supporter_auth"] = resp.data[0]
                        st.rerun()
                    else:
                        st.error("パスワードが違います。")
                        
        with tab_register:
            st.markdown('<div style="font-size:12px; color:rgba(255,255,255,0.6); margin-bottom:10px;">名前とパスワードを決めるだけですぐに作成できます！</div>', unsafe_allow_html=True)
            r_name = st.text_input("表示名 (公開されます)", key="r_name")
            r_pass = st.text_input("パスワードを決める", type="password", key="r_pass")
            if st.button("新規アカウントを作成", type="primary", use_container_width=True):
                if r_name and r_pass:
                    new_id = f"sup_{str(uuid.uuid4())[:8]}"
                    try:
                        get_db().table("supporters").insert({
                            "supporter_id": new_id,
                            "display_name": r_name,
                            "password_hash": hash_password(r_pass)
                        }).execute()
                        st.success(f"登録完了！あなたのサポーターIDは `{new_id}` です。")
                        st.session_state["supporter_auth"] = {
                            "supporter_id": new_id,
                            "display_name": r_name
                        }
                        st.rerun()
                    except Exception as e:
                        st.error(f"登録エラー: {e}")
                else:
                    st.warning("表示名とパスワードの両方を入力してください。")
        st.stop()
        
    sup_user = st.session_state["supporter_auth"]
    st.markdown(f'<div style="font-size:18px; font-weight:700; text-align:center; color:#f0f0f5; margin-bottom:5px;">ようこそ、{sup_user["display_name"]} さん！</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:13px; text-align:center; color:rgba(255,255,255,0.5); margin-bottom:20px;">あなたのサポーターID: <code>{sup_user["supporter_id"]}</code></div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); border-radius: 12px; padding: 16px; margin-bottom: 24px;">
        <div style="color: #8b5cf6; font-weight: 700; font-size: 14px; margin-bottom: 8px;">ℹ️ 次回からの応援について</div>
        <div style="font-size: 12px; color: rgba(240,240,245,0.7);">
            応援画面（決済画面）でオプションの「サポーターID」欄に上記のIDを入力すると、自動でここに応援実績が貯まります。
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 応援を紐づける
    st.markdown('<div class="header" style="font-size:16px;">🎫 過去の応援を紐づける</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px; color:rgba(255,255,255,0.5); margin-bottom:10px;">応援証明書（<code>?page=my_support&sid=xxx</code>）の <code>xxx</code> の部分（support_id）を入力してください。</div>', unsafe_allow_html=True)
    claim_id = st.text_input("応援証明書IDを入力", placeholder="例： 123e4567-e89b-12d3... または test_dummy...")
    if st.button("このアカウントに紐づける"):
        if claim_id:
            s_data = get_support(claim_id)
            if s_data:
                if s_data.get("supporter_id"):
                    st.warning("この応援記録はすでに誰かのアカウントに紐づけられています！")
                else:
                    get_db().table("supports").update({"supporter_id": sup_user["supporter_id"]}).eq("support_id", claim_id).execute()
                    st.success("紐づけが完了しました！ポートフォリオに反映されました。")
            else:
                st.error("応援記録が見つかりません。入力内容を確認してください。")
                
    st.markdown('<div class="oshi-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="header" style="font-size:16px;">📊 ポートフォリオでドヤる</div>', unsafe_allow_html=True)
    portfolio_url = f"{BASE_URL}?page=portfolio&id={sup_user['supporter_id']}"
    st.link_button("🌐 公開用ポートフォリオ画面を見る", portfolio_url, use_container_width=True)
    st.code(portfolio_url, language="text")
    
    st.markdown('<div class="oshi-divider"></div>', unsafe_allow_html=True)
    if st.button("🚪 ログアウト", type="secondary"):
        del st.session_state["supporter_auth"]
        st.rerun()
    st.stop()

else: # Dashboard
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">QRコードを発行</div>', unsafe_allow_html=True)
    # アカウントIDの特定
    acct_id = connect_acct or params.get("acct")
    
    if not acct_id:
        st.markdown('<div class="header">応援用QRコードを作成・復元</div>', unsafe_allow_html=True)
        st.write("新しく応援（決済）を受け取るための設定を行うか、以前作成したアカウントを復元します。")
        
        tab_new, tab_recover = st.tabs(["✨ 新規作成", "🔑 既存アカウントの復元"])
        
        with tab_new:
            st.info("新しく応援受け取りを開始するには、管理用パスワードを作成してください。")
            new_pass = st.text_input("管理用パスワードを作成", type="password", key="new_pass")

            # 明示的なボタンによる発行の意思確認
            if st.checkbox("新規にQRコードを発行して応援を受け取りますか？"):
                if not new_pass:
                    st.warning("パスワードを入力してください。")
                elif "onboarding_url" not in st.session_state:
                    if st.button("🔗 Stripeアカウントを連携する"):
                        with st.spinner("Stripeと連携する準備をしています... (数秒かかります)"):
                            try:
                                # アカウント作成（ウェブサイトURLなどを事前注入）
                                acct_id = create_connect_account()
                                register_creator(acct_id, new_pass)
                                st.session_state["creator_auth"] = acct_id
                                # 登録用リンクを取得して保存
                                st.session_state.onboarding_url = create_account_link(acct_id)
                                st.rerun()
                            except Exception as e:
                                st.error(f"連携エラー: {e}")
                
                if "onboarding_url" in st.session_state:
                    st.markdown(f"""
                    <div style="background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); border-radius: 12px; padding: 20px; text-align: center;">
                        <div style="font-size: 24px; margin-bottom: 12px;">🌟</div>
                        <div style="color: #f0f0f5; font-weight: 700; font-size: 16px; margin-bottom: 8px;">ステップ 1/2: Stripeで本人確認</div>
                        <div style="font-size: 13px; color: rgba(240,240,245,0.7); margin-bottom: 20px;">
                            下のボタンを押して、Stripeの画面で「本人確認」と「銀行口座」の設定を完了させてください。<br>
                            完了すると自動的にここに戻ってきます。
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.link_button("👉 Stripeの登録画面へ進む", st.session_state.onboarding_url, type="primary")
                    # 念のための自動リダイレクトJSも併用
                    components.html(f'<script>window.top.location.href = "{st.session_state.onboarding_url}";</script>', height=0)
                    if st.button("❌ キャンセルしてやり直す"):
                        del st.session_state.onboarding_url
                        st.rerun()
            else:
                st.warning("発行・連携を進めるには上のチェックボックスをオンにしてください。")

        with tab_recover:
            # ── 既存アカウント復元フォーム ──
            st.markdown("""
            <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);
                        border-radius:14px;padding:16px 20px;margin-bottom:4px;">
                <div style="font-size:13px;font-weight:700;color:rgba(240,240,245,0.85);margin-bottom:4px;">
                    🔑 既にアカウントをお持ちの方
                </div>
                <div style="font-size:12px;color:rgba(240,240,245,0.5);">
                    以前に発行したURLに含まれる <code>acct_</code> から始まるIDを入力してください
                </div>
            </div>
            """, unsafe_allow_html=True)
            recover_input = st.text_input("アカウントID", placeholder="acct_xxxxxxxxxxxxxxxxxx", label_visibility="collapsed")
            recover_pass = st.text_input("パスワード", type="password", placeholder="パスワードを入力")
            if st.button("✅ このアカウントで開く", use_container_width=True):
                rid = recover_input.strip()
                if rid.startswith("acct_") and len(rid) > 10 and recover_pass:
                    resp = get_db().table("creators").select("*").eq("acct_id", rid).execute()
                    if not resp.data:
                        # まだパスワードが設定されていない既存アカウントへの対応
                        register_creator(rid, recover_pass)
                        st.success("初期パスワードを設定しました！")
                        st.query_params["acct"] = rid
                        st.session_state["creator_auth"] = rid
                        st.rerun()
                    else:
                        if verify_creator(rid, recover_pass):
                            st.query_params["acct"] = rid
                            st.session_state["creator_auth"] = rid
                            st.rerun()
                        else:
                            st.error("パスワードが間違っています。")
                else:
                    st.error("アカウントIDとパスワードを正しく入力してください。")
    else:
        # 認証チェック
        if st.session_state.get("creator_auth") != acct_id:
            st.warning("このダッシュボードを開くにはパスワードが必要です。")
            auth_pass = st.text_input("パスワードを入力", type="password", key="auth_pass")
            if st.button("ロックを解除", type="primary"):
                resp = get_db().table("creators").select("*").eq("acct_id", acct_id).execute()
                if not resp.data:
                    # 既存ユーザーだが未パスワード設定の場合はここで初回設定扱いにする
                    register_creator(acct_id, auth_pass)
                    st.session_state["creator_auth"] = acct_id
                    st.rerun()
                elif verify_creator(acct_id, auth_pass):
                    st.session_state["creator_auth"] = acct_id
                    st.rerun()
                else:
                    st.error("パスワードが違います。")
            st.stop()
            
        st.markdown(f"""
        <div style="background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); border-radius: 12px; padding: 16px; margin-bottom: 20px;">
            <div style="color: #8b5cf6; font-weight: 700; font-size: 14px; margin-bottom: 4px;">✅ Stripe連携済み</div>
            <div style="font-size: 12px; color: rgba(240,240,245,0.6); margin-bottom: 12px;">ID: <code>{acct_id}</code></div>
            <div style="font-size: 11px; color: #f97316; font-weight: 700; margin-bottom: 8px;">ブラウザを閉じるとログアウトされます。必ずこのページをブックマークして保存してください！</div>
        </div>
        """, unsafe_allow_html=True)
        
        name = st.text_input("表示名", value=st.session_state.get("name", ""))
        icon = st.selectbox("アイコン", list(ICON_OPTIONS.keys()))
        
        col1, col2 = st.columns([2, 1])
        if col1.button("✨ QRコードを生成"):
            support_url = f"{BASE_URL}?page=support&user={uuid.uuid4()}&name={urllib.parse.quote(name)}&icon={icon}&acct={acct_id}"
            st.session_state.qr_url = support_url

        # 返信ダッシュボードへのリンク
        reply_view_url = f"{BASE_URL}?page=reply_view&acct={acct_id}"
        st.markdown(f"""
        <div style="margin: 16px 0;">
            <a href="{reply_view_url}" target="_top"
               style="display:block; text-align:center; background:rgba(139,92,246,0.15);
                      border:1px solid rgba(139,92,246,0.35); border-radius:12px;
                      padding:12px 16px; color:#c4b5fd; text-decoration:none;
                      font-weight:700; font-size:14px;">
                💌 応援メッセージ・返信ダッシュボードを開く
            </a>
        </div>
        """, unsafe_allow_html=True)

        # 連携解除ボタン
        if col2.button("🚫 連携解除"):
            st.components.v1.html("""
            <script>
            localStorage.removeItem('oshipay_acct');
            const url = new URL(window.location.href);
            url.searchParams.delete('acct');
            window.location.href = url.href;
            </script>
            """, height=0)
            st.stop()
        if "qr_url" in st.session_state:
            b64_qr, qr_bytes = generate_qr_data(st.session_state.qr_url)
            st.markdown(f'<div class="qr-frame"><img src="data:image/png;base64,{b64_qr}"></div>', unsafe_allow_html=True)
            st.download_button(
                label="📥 QRコード画像を保存",
                data=qr_bytes,
                file_name=f"oshipay_qr_{acct_id}.png",
                mime="image/png",
                use_container_width=True,
            )
            st.code(st.session_state.qr_url)
    st.markdown(f'<div class="oshi-footer">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="legal-links text-center pt-2"><a href="{BASE_URL}?page=terms" target="_top">利用規約</a><a href="{BASE_URL}?page=privacy" target="_top">プライバシーポリシー</a><a href="{BASE_URL}?page=legal" target="_top">特定商取引法</a></div>', unsafe_allow_html=True)