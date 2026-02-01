import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime, timedelta
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全球廚電全網雷達 Pro", page_icon="📡", layout="wide")
st.title("📡 全球廚電全網雷達 Pro (含時光機)")

# --- 2. 核心功能函數 ---

# A. Google News 爬蟲 (僅限近期)
def fetch_google_news(keyword, lang, region):
    encoded_keyword = urllib.parse.quote(keyword)
    if region == "HK" and "zh" in lang:
        target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang}&gl={region}&ceid={region}:zh-Hant"
    else:
        ceid_lang = lang.split('-')[0]
        target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang}&gl={region}&ceid={region}:{ceid_lang}"
    
    try:
        feed = feedparser.parse(target_url)
        data = []
        for entry in feed.entries:
            try:
                pub_date = datetime(*entry.published_parsed[:6])
            except:
                pub_date = datetime.now()
                
            data.append({
                "Date": pub_date,
                "Type": "新聞 (News)",
                "Title": entry.title,
                "Source": entry.source.title if 'source' in entry else "Google News",
                "Link": entry.link,
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# B. DuckDuckGo 全網爬蟲 (支援時間回溯)
def fetch_web_search(keyword, region_code, time_range):
    # region_code 轉換
    if region_code == "US": ddg_region = "us-en"
    elif region_code == "CA": ddg_region = "ca-en"
    elif region_code == "HK": ddg_region = "hk-tzh"
    else: ddg_region = "wt-wt"
    
    # 時間參數轉換 (d=day, w=week, m=month, y=year)
    # 預設不限時間
    ddg_time = None 
    if time_range == "過去一天": ddg_time = "d"
    elif time_range == "過去一週": ddg_time = "w"
    elif time_range == "過去一個月": ddg_time = "m"
    elif time_range == "過去一年": ddg_time = "y" # 這是你要的！
    
    try:
        # 這裡的 max_results 設定多一點 (50筆)，因為我們要挖舊資料
        results = DDGS().text(keywords=keyword, region=ddg_region, time=ddg_time, max_results=50)
        
        data = []
        for r in results:
            data.append({
                "Date": datetime.now(), # DDG 不一定回傳精確日期，標記為搜尋日
                "Type": "全網 (Web/Forum)",
                "Title": r['title'],
                "Source": urllib.parse.urlparse(r['href']).netloc,
                "Link": r['href'],
                "Snippet": r['body']
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# C. 混合搜索控制器
def run_hybrid_search(keyword, location_choice, search_types, time_range):
    frames = []
    
    if location_choice == "🇺🇸 美國 (US)":
        news_tasks = [("en-US", "US"), ("zh-TW", "US")]
        ddg_region = "US"
    elif location_choice == "🇨🇦 加拿大 (CA)":
        news_tasks = [("en-CA", "CA"), ("zh-TW", "CA")]
        ddg_region = "CA"
    elif location_choice == "🇭🇰 香港 (HK)":
        news_tasks = [("zh-HK", "HK"), ("en-HK", "HK")]
        ddg_region = "HK"
    
    # 1. 新聞 (Google News RSS 不支援長時段回溯，僅跑最新)
    if "新聞媒體 (News)" in search_types:
        # 只有在選「不限」或「過去一週/月」時才跑 RSS，不然 RSS 抓不到舊的也沒用
        if time_range in ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月"]:
            for lang, region in news_tasks:
                df = fetch_google_news(keyword, lang, region)
                frames.append(df)
            
    # 2. 全網 (DuckDuckGo 支援時間回溯)
    if "論壇與部落格 (Forums/Blogs)" in search_types:
        df_web = fetch_web_search(keyword, ddg_region, time_range)
        frames.append(df_web)

    if frames:
        result_df = pd.concat(frames)
        result_df = result_df.drop_duplicates(subset=['Link'])
        return result_df
    else:
        return pd.DataFrame()

# D. 資料庫讀取
@st.cache_data(ttl=600)
def load_historical_data(url):
    try:
        df = pd.read_csv(url)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except:
        return pd.DataFrame()

# --- 3. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 雷達設定")
    mode = st.radio("模式", ["📡 全網掃描 (Live)", "🗄️ 歷史資料庫"])
    st.divider()
    today = datetime.now().date()
    start_date = st.date_input("資料庫起始日", today - timedelta(days=180))

# --- 4. 主畫面 ---

if mode == "📡 全網掃描 (Live)":
    st.subheader("📡 全球廚電全網掃描 (含歷史回溯)")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: 抽油煙機, 方太, Robam...")
    with col2:
        location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
    with col3:
        # 🔥 新功能：時間時光機
        time_range = st.selectbox(
            "⏱️ 時間範圍", 
            ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"]
        )
        
    search_scope = st.multiselect(
        "選擇搜尋來源",
        ["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"],
        default=["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"]
    )
    
    st.info("💡 提示：若想找「半年前」的舊聞，請將時間範圍設為「過去一年」，系統會深入挖掘論壇與庫存頁面。")

    if st.button("🚀 發射雷達", type="primary"):
        if search_kw:
            with st.spinner(f"正在挖掘 {time_range} 關於 '{search_kw}' 的情報..."):
                df = run_hybrid_search(search_kw, location, search_scope, time_range)
                
                if not df.empty:
                    st.success(f"掃描完成！共發現 {len(df)} 筆情報")
                    st.data_editor(
                        df,
                        column_config={
                            "Link": st.column_config.LinkColumn("連結", display_text="Go"),
                            "Date": st.column_config.DateColumn("發布/抓取日", format="YYYY-MM-DD"),
                            "Title": st.column_config.TextColumn("標題", width="medium"),
                            "Snippet": st.column_config.TextColumn("摘要", width="large"),
                        },
                        use_container_width=True
                    )
                else:
                    st.warning("未搜尋到結果。")
        else:
            st.error("請輸入關鍵字")

elif mode == "🗄️ 歷史資料庫":
    st.subheader("🗄️ 內部輿情資料庫")
    # 🔥 記得換你的 CSV 連結 🔥
    sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQai1zkVJlpDcZhzs76S_JiCsm1JogWxdYlw4vA4k1IeWLHqiReRRY29xQm7ephIk9QJfri7OlvfdmF/pubhtml"
    
    df = load_historical_data(sheet_url)
    if not df.empty:
        mask = (df['Date'].dt.date >= start_date)
        filtered_df = df.loc[mask]
        
        db_search = st.text_input("搜尋資料庫...", placeholder="輸入關鍵字...")
        if db_search:
            filtered_df = filtered_df[filtered_df['Title'].str.contains(db_search, case=False, na=False)]
            
        st.data_editor(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.error("無法讀取資料庫")
