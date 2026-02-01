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

# A. 爬蟲函數 (即時抓取用)
def fetch_live_news(keyword, lang_code="en-US", region="US"):
    encoded_keyword = urllib.parse.quote(keyword)
    # 判斷語言代碼處理
    ceid_lang = lang_code.split('-')[0]
    target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang_code}&gl={region}&ceid={region}:{ceid_lang}"
    
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

# B. 資料庫讀取函數 (歷史資料用)
@st.cache_data(ttl=600) # 設定快取 10 分鐘，避免一直讀取 Google Sheet
def load_historical_data(url):
    try:
        df = pd.read_csv(url)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except:
        return pd.DataFrame()

# --- 3. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    mode = st.radio("選擇模式", ["📡 即時偵察 (Live Search)", "🗄️ 歷史資料庫 (Database)"])
    
    st.divider()
    
    # 日期篩選器 (預設半年內)
    today = datetime.now().date()
    half_year_ago = today - timedelta(days=180)
    
    st.subheader("📅 日期篩選")
    start_date = st.date_input("開始日期", half_year_ago)
    end_date = st.date_input("結束日期", today)

# --- 4. 主畫面邏輯 ---

# === 模式一：即時偵察 (隨意更改關鍵字) ===
if mode == "📡 即時偵察 (Live Search)":
    st.subheader("📡 即時全網搜索")
    st.info("此模式會直接連線 Google News 抓取當下最新資訊 (適合臨時查詢新競品)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_kw = st.text_input("輸入想查詢的關鍵字 (支援中英文)", "Air Fryer")
    with col2:
        region_opt = st.selectbox("地區/語言", ["🇺🇸 美國 (英文)", "🇺🇸 美國 (中文)", "🇨🇦 加拿大 (英文)"])
    
    # 設定參數
    lang_map = {
        "🇺🇸 美國 (英文)": ("en-US", "US"),
        "🇺🇸 美國 (中文)": ("zh-TW", "US"),
        "🇨🇦 加拿大 (英文)": ("en-CA", "CA")
    }
    
    if st.button("🚀 開始搜索", type="primary"):
        with st.spinner(f"正在掃描北美網路關於 '{search_kw}' 的資訊..."):
            lang, reg = lang_map[region_opt]
            live_df = fetch_live_news(search_kw, lang, reg)
            
            if not live_df.empty:
                st.success(f"搜尋完成！找到 {len(live_df)} 筆最新資料")
                
                # 顯示資料
                st.data_editor(
                    live_df,
                    column_config={
                        "Link": st.column_config.LinkColumn("閱讀連結"),
                        "Date": st.column_config.DateColumn("發布時間", format="YYYY-MM-DD HH:mm"),
                    },
                    use_container_width=True
                )
            else:
                st.warning("找不到近期相關新聞，請嘗試更換關鍵字。")

# === 模式二：歷史資料庫 (查看累積的資料) ===
elif mode == "🗄️ 歷史資料庫 (Database)":
    st.subheader("🗄️ 內部輿情資料庫")
    
    # 🔥 請記得把這裡換成你的 CSV 網址 🔥
    sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQai1zkVJlpDcZhzs76S_JiCsm1JogWxdYlw4vA4k1IeWLHqiReRRY29xQm7ephIk9QJfri7OlvfdmF/pub?output=csv"
    
    df = load_historical_data(sheet_url)
    
    if not df.empty:
        # 日期篩選邏輯
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
        filtered_df = df.loc[mask]
        
        # 關鍵字篩選 (在歷史資料中搜尋)
        db_search = st.text_input("在資料庫中搜尋標題...", placeholder="輸入關鍵字篩選歷史資料")
        if db_search:
            filtered_df = filtered_df[filtered_df['Title'].str.contains(db_search, case=False, na=False)]
            
        # 顯示統計數據
        c1, c2, c3 = st.columns(3)
        c1.metric("選定期間資料量", f"{len(filtered_df)} 筆")
        c2.metric("資料起始日", f"{start_date}")
        c3.metric("資料結束日", f"{end_date}")
        
        # 繪製聲量圖
        if not filtered_df.empty:
            st.markdown("### 📊 期間聲量趨勢")
            trend = filtered_df.groupby(filtered_df['Date'].dt.date).size().reset_index(name='Count')
            st.bar_chart(trend.set_index('Date'), color="#FF4B4B")

            st.markdown("### 📋 詳細資料表")
            st.data_editor(
                filtered_df,
                column_config={
                    "Link": st.column_config.LinkColumn("連結"),
                    "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("選定的時間範圍內沒有資料。")
            
    else:
        st.error("無法連接資料庫，請檢查 CSV 網址。")
