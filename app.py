import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime, timedelta
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全球廚電全網雷達 Lite", page_icon="📡", layout="wide")
st.title("📡 全球廚電全網雷達 (Lite)")

# --- 2. 核心功能函數 ---

# A. Google News 爬蟲 (無摘要版)
def fetch_google_news(keyword, lang, region):
    # 智慧搜尋邏輯
    search_query = keyword
    target_gl = region
    target_ceid = f"{region}:{lang.split('-')[0]}"
    
    # 針對北美中文的特殊處理 (關鍵字植入 + 放寬地區)
    if (region in ["US", "CA"]) and ("zh" in lang):
        if region == "US":
            search_query = f"{keyword} (美國 OR 北美 OR USA)"
        elif region == "CA":
            search_query = f"{keyword} (加拿大 OR Canada OR 温哥华 OR 多伦多)"
        target_gl = "TW" 
        target_ceid = "TW:zh-Hant"

    # 香港維持原樣
    if region == "HK" and "zh" in lang:
        target_ceid = "HK:zh-Hant"
        target_gl = "HK"

    encoded_keyword = urllib.parse.quote(search_query)
    target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang}&gl={target_gl}&ceid={target_ceid}"
    
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
                "Type": "新聞",
                "Title": entry.title,
                "Source": entry.source.title if 'source' in entry else "Google News",
                "Link": entry.link
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# B. DuckDuckGo 全網爬蟲 (無摘要版)
def fetch_web_search(keyword, region_code, time_range):
    if region_code == "US": ddg_region = "us-en"
    elif region_code == "CA": ddg_region = "ca-en"
    elif region_code == "HK": ddg_region = "hk-tzh"
    else: ddg_region = "wt-wt"
    
    ddg_time = None 
    if time_range == "過去一天": ddg_time = "d"
    elif time_range == "過去一週": ddg_time = "w"
    elif time_range == "過去一個月": ddg_time = "m"
    elif time_range == "過去一年": ddg_time = "y"
    
    # 中文搜尋優化
    final_keyword = keyword
    search_region = ddg_region
    is_chinese_query = any(u'\u4e00' <= c <= u'\u9fff' for c in keyword)
    
    if (region_code in ["US", "CA"]) and is_chinese_query:
        search_region = "wt-wt"
        if region_code == "US":
            final_keyword = f"{keyword} (美國 OR 北美 OR 華人)"
        elif region_code == "CA":
            final_keyword = f"{keyword} (加拿大 OR 温哥華 OR 多倫多)"

    try:
        results = DDGS().text(keywords=final_keyword, region=search_region, time=ddg_time, max_results=40)
        
        data = []
        for r in results:
            data.append({
                "Date": datetime.now(),
                "Type": "全網",
                "Title": r['title'],
                "Source": urllib.parse.urlparse(r['href']).netloc,
                "Link": r['href']
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# C. 混合搜索控制器
def run_hybrid_search(keyword, location_choice, search_types, time_range):
    frames = []
    
    if location_choice == "🇺🇸 美國 (US)":
        news_tasks = [("en-US", "US"), ("zh-TW", "US")]
        region_code = "US"
    elif location_choice == "🇨🇦 加拿大 (CA)":
        news_tasks = [("en-CA", "CA"), ("zh-TW", "CA")]
        region_code = "CA"
    elif location_choice == "🇭🇰 香港 (HK)":
        news_tasks = [("zh-HK", "HK"), ("en-HK", "HK")]
        region_code = "HK"
    
    if "新聞媒體 (News)" in search_types:
        if time_range in ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月"]:
            for lang, region in news_tasks:
                df = fetch_google_news(keyword, lang, region)
                frames.append(df)
            
    if "論壇與部落格 (Forums/Blogs)" in search_types:
        df_web = fetch_web_search(keyword, region_code, time_range)
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
    st.subheader("📡 全球廚電全網掃描")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: 抽油煙機, 方太, Robam...")
    with col2:
        location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
    with col3:
        time_range = st.selectbox("⏱️ 時間範圍", ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"])
        
    search_scope = st.multiselect(
        "選擇搜尋來源",
        ["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"],
        default=["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"]
    )
    
    if st.button("🚀 發射雷達", type="primary"):
        if search_kw:
            with st.spinner(f"正在挖掘 {location} 的相關情報..."):
                df = run_hybrid_search(search_kw, location, search_scope, time_range)
                
                if not df.empty:
                    st.success(f"掃描完成！共發現 {len(df)} 筆情報")
                    st.data_editor(
                        df,
                        column_config={
                            "Link": st.column_config.LinkColumn("連結", display_text="Go", width="small"),
                            "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD", width="small"),
                            "Type": st.column_config.TextColumn("類型", width="small"),
                            "Source": st.column_config.TextColumn("來源", width="medium"),
                            "Title": st.column_config.TextColumn("標題"), # 讓標題自動填滿剩餘空間
                        },
                        use_container_width=True
                    )
                else:
                    st.warning("找不到結果。")
        else:
            st.error("請輸入關鍵字")

elif mode == "🗄️ 歷史資料庫":
    st.subheader("🗄️ 內部輿情資料庫")
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
