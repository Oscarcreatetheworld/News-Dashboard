import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import altair as alt

# --- 1. 頁面設定 ---
st.set_page_config(page_title="北美廚電情資中心", page_icon="🍳", layout="wide")
st.title("🍳 北美廚電情資中心 (Live & Database)")

# --- 2. 核心功能函數 ---

# A. 爬蟲函數 (支援多語系精準搜索)
def fetch_live_news(keyword, lang_code, region):
    encoded_keyword = urllib.parse.quote(keyword)
    
    # 針對中文搜尋優化：如果是中文模式，強制設定 ceid 為地區:語言
    if "zh" in lang_code:
        # 例如搜尋北美華人內容：ceid=US:zh-Hant (繁體中文在美國)
        target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang_code}&gl={region}&ceid={region}:{lang_code}"
    else:
        # 英文模式
        target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang_code}&gl={region}&ceid={region}:{lang_code.split('-')[0]}"
    
    feed = feedparser.parse(target_url)
    data = []
    for entry in feed.entries:
        try:
            pub_date = datetime(*entry.published_parsed[:6])
        except:
            pub_date = datetime.now()
            
        data.append({
            "Date": pub_date,
            "Title": entry.title,
            "Source": entry.source.title if 'source' in entry else "N/A",
            "Link": entry.link
        })
    return pd.DataFrame(data)

# B. 資料庫讀取
@st.cache_data(ttl=600)
def load_historical_data(url):
    try:
        df = pd.read_csv(url)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except:
        return pd.DataFrame()

# --- 3. 側邊欄：模式切換 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    mode = st.radio("選擇模式", ["📡 即時偵察 (Live Search)", "🗄️ 歷史資料庫 (Database)"])
    st.divider()
    
    # 日期篩選 (給資料庫用的)
    today = datetime.now().date()
    start_date = st.date_input("資料庫-開始日期", today - timedelta(days=180))
    end_date = st.date_input("資料庫-結束日期", today)

# --- 4. 主畫面邏輯 ---

# === 模式一：即時偵察 (Live Search) ===
if mode == "📡 即時偵察 (Live Search)":
    st.subheader("📡 即時全網搜索")
    st.markdown("輸入關鍵字，立即抓取 Google News 最新資料。")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 這裡提示使用者可以輸入中文
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: Range Hood, 抽油煙機, 方太, Fotile...")
    
    with col2:
        # 這裡是最重要的「語系切換」
        target_market = st.selectbox(
            "目標市場/語言", 
            [
                "🇺🇸 美國 - 英文媒體 (Mainstream)", 
                "🇺🇸 美國 - 華人媒體 (Chinese Community)", 
                "🇨🇦 加拿大 - 英文媒體",
                "🇹🇼 台灣 - 繁體中文 (測試用)"
            ]
        )
    
    # 設定對應的參數 (語言代碼, 地區代碼)
    market_map = {
        "🇺🇸 美國 - 英文媒體 (Mainstream)": ("en-US", "US"),
        "🇺🇸 美國 - 華人媒體 (Chinese Community)": ("zh-TW", "US"), # 關鍵：在美國搜中文
        "🇨🇦 加拿大 - 英文媒體": ("en-CA", "CA"),
        "🇹🇼 台灣 - 繁體中文 (測試用)": ("zh-TW", "TW")
    }
    
    if st.button("🚀 搜尋", type="primary"):
        if search_kw:
            with st.spinner(f"正在搜尋 '{search_kw}' 的最新情報..."):
                lang, region = market_map[target_market]
                live_df = fetch_live_news(search_kw, lang, region)
                
                if not live_df.empty:
                    st.success(f"搜尋完成！在【{target_market}】找到 {len(live_df)} 筆資料")
                    st.data_editor(
                        live_df,
                        column_config={
                            "Link": st.column_config.LinkColumn("連結", display_text="點擊閱讀"),
                            "Date": st.column_config.DateColumn("發布時間", format="YYYY-MM-DD HH:mm"),
                            "Title": st.column_config.TextColumn("標題"),
                        },
                        use_container_width=True
                    )
                else:
                    st.warning(f"找不到關於 '{search_kw}' 的資料。建議：\n1. 檢查關鍵字拼寫\n2. 如果搜中文，請確認右邊已選擇「華人媒體」")
        else:
            st.error("請輸入關鍵字！")

# === 模式二：歷史資料庫 (Database) ===
elif mode == "🗄️ 歷史資料庫 (Database)":
    st.subheader("🗄️ 內部輿情資料庫")
    
    # 🔥 請記得把這裡換成你的 CSV 網址 🔥
    sheet_url = "你的_GOOGLE_SHEET_CSV_連結"
    
    df = load_historical_data(sheet_url)
    
    if not df.empty:
        # 日期篩選
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
        filtered_df = df.loc[mask]
        
        # 關鍵字篩選 (支援中文)
        db_search = st.text_input("在歷史資料中搜尋...", placeholder="輸入關鍵字 (支援中英文)...")
        if db_search:
            # case=False 讓英文不分大小寫，中文沒差
            filtered_df = filtered_df[filtered_df['Title'].str.contains(db_search, case=False, na=False)]
            
        st.metric("資料筆數", len(filtered_df))
        
        st.data_editor(
            filtered_df[['Date', 'Category', 'Title', 'Source', 'Link']],
            column_config={
                "Link": st.column_config.LinkColumn("連結", display_text="Go"),
                "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.error("無法讀取資料庫，請檢查 CSV 網址。")
