import os
import io
import base64
import uuid
import random

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
BASE_URL = os.environ.get("APP_URL", "https://oshipay.streamlit.app")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ヘルパー関数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def create_connect_account():
    account = stripe.Account.create(
        type="express", country="JP",
        capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
        business_type="individual",
        business_profile={"mcc": "7922", "product_description": "OshiPay - 投げ銭サービス"},
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
        return {"charges_enabled": account.charges_enabled, "details_submitted": account.details_submitted}
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ページスタイル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Noto+Sans+JP:wght@400;700;900&display=swap');
#MainMenu, header, footer, .stDeployButton {visibility: hidden; display: none;}
[data-testid="stToolbar"], [data-testid="stDecoration"] {display: none;}
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
.particles-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 0; overflow: hidden; }
.particle { position: absolute; border-radius: 50%; animation: floatParticle linear infinite; opacity: 0.15; }
@keyframes floatParticle { 0% { transform: translateY(100vh); opacity: 0; } 10% { opacity: 0.15; } 90% { opacity: 0.15; } 100% { transform: translateY(-10vh); opacity: 0; } }
.legal-links a { font-size: 10px; color: rgba(240,240,245,0.3); text-decoration: none; margin: 0 5px; }
</style>
""", unsafe_allow_html=True)

# ── パーティクル ──
particles_html = '<div class="particles-bg">'
for _ in range(20):
    size = random.uniform(2, 4); left = random.uniform(0, 100); dur = random.uniform(15, 25); dly = random.uniform(0, 10)
    particles_html += f'<div class="particle" style="width:{size}px;height:{size}px;left:{left}%;background:#8b5cf6;animation-duration:{dur}s;animation-delay:{dly}s;"></div>'
st.markdown(particles_html + '</div>', unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ルーティング
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
params = st.query_params
page = params.get("page", "lp")

# LP用フルワイドCSS
if page == "lp":
    st.markdown("<style>.stMainBlockContainer, .block-container { max-width: none !important; padding: 0 !important; margin: 0 !important; } .particles-bg { display: none !important; }</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>.stMainBlockContainer, .block-container { max-width: 460px !important; margin: 0 auto; }</style>", unsafe_allow_html=True)

# ── 法務ページコンテンツ集約 ──
LEGAL_DOCS = {
    "terms": """
<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>利用規約 - OshiPay</title><script src="https://cdn.tailwindcss.com"></script><script src="https://unpkg.com/lucide@latest"></script></head><body class="bg-[#0a0a0f] text-slate-200 p-8"><main class="max-w-3xl mx-auto"><h1 class="text-3xl font-bold mb-8 text-white">利用規約</h1><div class="space-y-6 text-slate-300"><section><h2 class="text-xl font-bold text-white border-b border-white/10 pb-2 mb-4">第1条（目的）</h2><p>OshiPayは、活動する方への「純粋な応援」を届けるためのサービスです。</p></section><section><h2 class="text-xl font-bold text-white border-b border-white/10 pb-2 mb-4">第2条（手数料）</h2><p>応援金額の10%をシステム利用料として差し引き、90%を受取人に還元します。</p></section><section><h2 class="text-xl font-bold text-white border-b border-white/10 pb-2 mb-4">第3条（禁止事項）</h2><p>マネーロンダリング、法令違反、対価を伴う商品の販売などを禁止します。</p></section></div></main></body></html>
""",
    "privacy": """
<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>プライバシーポリシー - OshiPay</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a0f] text-slate-200 p-8"><main class="max-w-3xl mx-auto"><h1 class="text-3xl font-bold mb-8 text-white">プライバシーポリシー</h1><div class="space-y-6"><p>OshiPayは、皆様のプライバシー保護を最優先事項として設計されています。</p><p>運営側（OshiPay）が応援者の個人情報や決済情報、メッセージ内容を閲覧・保持することはありません。すべての決済情報はStripe社によって安全に処理されます。</p></div></main></body></html>
""",
    "legal": """
<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>特定商取引法に基づく表記 - OshiPay</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a0f] text-slate-200 p-8"><main class="max-w-3xl mx-auto"><h1 class="text-3xl font-bold mb-8 text-white">特定商取引法に基づく表記</h1><table class="w-full text-left border-collapse border border-white/10"><tr><th class="p-4 border border-white/10 bg-white/5">代表責任者</th><td class="p-4 border border-white/10">関　元喜</td></tr><tr><th class="p-4 border border-white/10 bg-white/5">所在地</th><td class="p-4 border border-white/10">〒418-0108 静岡県富士宮市猪之頭字内野941-35</td></tr><tr><th class="p-4 border border-white/10 bg-white/5">連絡先</th><td class="p-4 border border-white/10">oyajibuki@gmail.com</td></tr><tr><th class="p-4 border border-white/10 bg-white/5">販売価格</th><td class="p-4 border border-white/10">任意の応援金額</td></tr><tr><th class="p-4 border border-white/10 bg-white/5">返金について</th><td class="p-4 border border-white/10">性質上、決済完了後の返金・キャンセルはできません。</td></tr></table></main></body></html>
"""
}

if page in LEGAL_DOCS:
    components.html(LEGAL_DOCS[page], height=1200, scrolling=True); st.stop()

# ── 成功ページ ──
if page == "success":
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:48px;margin:20px 0;">🎉</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">応援完了！</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">あなたの応援が届きました！🙏</div>', unsafe_allow_html=True)
    
    # シェアボタン
    s_name = params.get("s_name", ""); s_amt = params.get("s_amt", "")
    share_text = f"{s_name}さんに{s_amt}円 応援したよ！\n{BASE_URL} #OshiPay"
    st.link_button("𝕏 でシェア", f"https://twitter.com/intent/tweet?text={urllib.parse.quote(share_text)}", use_container_width=True)
    
    st.markdown(f'<div class="oshi-footer">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="legal-links text-center pt-2"><a href="{BASE_URL}?page=terms">利用規約</a><a href="{BASE_URL}?page=privacy">プライバシーポリシー</a><a href="{BASE_URL}?page=legal">特定商取引法</a></div>', unsafe_allow_html=True)
    st.stop()

# ── キャンセル ──
elif page == "cancel":
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:48px;margin:20px 0;">🤔</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">キャンセルしました</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="oshi-footer">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.stop()

# ── ランディングページ ──
elif page == "lp":
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, "oshipay-lp", "index.html"), "r", encoding="utf-8") as f:
            lp_html = f.read()
        # Iframe高さ制御
        st.markdown("<style>iframe { height: 3800px !important; width: 100% !important; border: none; }</style>", unsafe_allow_html=True)
        components.html(lp_html, height=3800)
    except Exception as e: st.error(f"LPエラー: {e}")
    st.stop()

# ── 応援・ダッシュボード等のロジックは継続 ──
support_user = params.get("user", "")
connect_acct = params.get("acct", "")

if page == "support" and support_user:
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="support-avatar">{params.get("icon", "🎤")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="support-name">{params.get("name", "クリエイター")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="support-label">を応援しよう</div>', unsafe_allow_html=True)
    
    if "amt" not in st.session_state: st.session_state.amt = 1000
    cols = st.columns(3)
    for i, a in enumerate(PRESET_AMOUNTS):
        with cols[i % 3]:
            if st.button(f"¥{a:,}", key=f"a_{a}"): st.session_state.amt = a
    
    st.markdown(f'<div class="selected-amount-display">¥{st.session_state.amt:,}</div>', unsafe_allow_html=True)
    msg = st.text_area("応援メッセージ", max_chars=140)
    
    if st.button("🔥 応援する！"):
        amt = st.session_state.amt
        try:
            params = {
                "payment_method_types": ["card"], "mode": "payment",
                "line_items": [{"price_data": {"currency": "jpy", "product_data": {"name": "応援資金"}, "unit_amount": amt}, "quantity": 1}],
                "success_url": f"{BASE_URL}?page=success&s_name=Creator&s_amt={amt}", "cancel_url": f"{BASE_URL}?page=cancel",
                "metadata": {"user_id": support_user, "message": msg}
            }
            if connect_acct:
                params["payment_intent_data"] = {"application_fee_amount": int(amt * 0.1)}
                session = stripe.checkout.Session.create(**params, stripe_account=connect_acct)
            else: session = stripe.checkout.Session.create(**params)
            st.markdown(f'<script>window.top.location.href = "{session.url}";</script>', unsafe_allow_html=True)
            st.link_button("💳 決済ページへ", session.url)
        except Exception as e: st.error(e)
    
    st.markdown(f'<div class="oshi-footer">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="legal-links text-center pt-2"><a href="{BASE_URL}?page=terms">利用規約</a><a href="{BASE_URL}?page=privacy">プライバシーポリシー</a><a href="{BASE_URL}?page=legal">特定商取引法</a></div>', unsafe_allow_html=True)

else: # Dashboard
    st.markdown('<div class="oshi-logo"><span class="icon">🔥</span> <span class="text">OshiPay</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">応援を受け取ろう</div>', unsafe_allow_html=True)
    
    acct_id = connect_acct or st.session_state.get("acct_id", "")
    if not acct_id:
        if st.button("🔗 Stripeアカウントを連携する"):
            acct_id = create_connect_account()
            st.session_state.acct_id = acct_id
            url = create_account_link(acct_id)
            st.markdown(f'<script>window.top.location.href = "{url}";</script>', unsafe_allow_html=True)
            st.link_button("🔗 Stripe登録へ", url)
    else:
        st.success("連携済み")
        name = st.text_input("表示名")
        if st.button("✨ QRコード生成"):
            url = f"{BASE_URL}?page=support&user=user&name={name}&acct={acct_id}"
            st.qrcode(url)
            st.write(url)
    
    st.markdown(f'<div class="oshi-footer">Powered by <a href="{BASE_URL}?page=dashboard">OshiPay</a></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="legal-links text-center pt-2"><a href="{BASE_URL}?page=terms">利用規約</a><a href="{BASE_URL}?page=privacy">プライバシーポリシー</a><a href="{BASE_URL}?page=legal">特定商取引法</a></div>', unsafe_allow_html=True)