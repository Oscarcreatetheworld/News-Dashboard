import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime, timedelta
import altair as alt

# --- 1. 頁面設定 ---
st.set_page_config(page_title="Daily Monitoring", page_icon="🍳", layout="wide")
st.title("🍳 新聞資料庫")

# --- 2. 核心功能函數 ---

# A. 基礎爬蟲函數
def fetch_rss(keyword, lang, region):
    encoded_keyword = urllib.parse.quote(keyword)
    # 組合 Google News RSS URL
    # 這裡會根據傳入的 lang (例如 zh-TW 或 en-US) 自動調整搜索源
    ceid_lang = lang.split('-')[0]
    target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang}&gl={region}&ceid={region}:{lang}"
    
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
            "Link": entry.link,
            "Lang": "中文" if "zh" in lang else "English" # 標記來源語言
        })
    return pd.DataFrame(data)

# B. 整合搜索函數 (這裡就是「中英通吃」的關鍵)
def fetch_mixed_news(keyword, location_choice):
    # 定義每個地區要搜哪些語言
    # 格式: (語言代碼, 地區代碼)
    tasks = []
    
    if location_choice == "🇺🇸 美國 (US)":
        tasks = [
            ("en-US", "US"), # 搜美國英文
            ("zh-TW", "US")  # 搜美國中文 (繁體)
        ]
    elif location_choice == "🇨🇦 加拿大 (CA)":
        tasks = [
            ("en-CA", "CA"), # 搜加拿大英文
            ("zh-TW", "CA")  # 搜加拿大中文
        ]

    # 開始執行雙軌搜索
    frames = []
    for lang, region in tasks:
        df = fetch_rss(keyword, lang, region)
        frames.append(df)
    
    # 合併結果
    if frames:
        result_df = pd.concat(frames)
        # 去除重複 (如果同一篇新聞被重複抓到)
        result_df = result_df.drop_duplicates(subset=['Link'])
        # 依照日期排序 (新的在上面)
        result_df = result_df.sort_values(by='Date', ascending=False)
        return result_df
    else:
        return pd.DataFrame()

# C. 資料庫讀取
@st.cache_data(ttl=600)
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
    mode = st.radio("選擇模式", ["📡 即時偵察 (Live)", "🗄️ 歷史資料庫 (DB)"])
    st.divider()
    
    # 日期篩選
    today = datetime.now().date()
    start_date = st.date_input("資料庫-開始", today - timedelta(days=180))
    end_date = st.date_input("資料庫-結束", today)

# --- 4. 主畫面邏輯 ---

# === 模式一：即時偵察 (Live) ===
if mode == "📡 即時偵察 (Live)":
    st.subheader("📡 全網即時搜索 (中英混合)")
    st.markdown("輸入關鍵字，系統將自動同時掃描該地區的「英文主流媒體」與「華人社群媒體」。")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: Range Hood, 方太, Fotile...")
    with col2:
        # 這裡變簡單了！只選地點
        location = st.selectbox("選擇市場區域", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)"])
    
    if st.button("🚀 開始搜索", type="primary"):
        if search_kw:
            with st.spinner(f"正在同時掃描 {location} 的中英文情報..."):
                live_df = fetch_mixed_news(search_kw, location)
                
                if not live_df.empty:
                    st.success(f"搜尋完成！找到 {len(live_df)} 筆資料")
                    
                    st.data_editor(
                        live_df,
                        column_config={
                            "Link": st.column_config.LinkColumn("連結", display_text="點擊閱讀"),
                            "Date": st.column_config.DateColumn("發布時間", format="YYYY-MM-DD HH:mm"),
                            "Title": st.column_config.TextColumn("標題"),
                            "Lang": st.column_config.TextColumn("語系", width="small"),
                        },
                        use_container_width=True
                    )
                else:
                    st.warning("找不到資料，請檢查關鍵字。")
        else:
            st.error("請輸入關鍵字！")

# === 模式二：歷史資料庫 (DB) ===
elif mode == "🗄️ 歷史資料庫 (DB)":
    st.subheader("🗄️ 內部輿情資料庫")
    
    # 🔥 請記得把這裡換成你的 CSV 網址 🔥
    sheet_url = "你的_GOOGLE_SHEET_CSV_連結"
    
    df = load_historical_data(sheet_url)
    
    if not df.empty:
        mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
        filtered_df = df.loc[mask]
        
        db_search = st.text_input("搜尋歷史資料...", placeholder="輸入關鍵字...")
        if db_search:
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
