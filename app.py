import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime
import time
from duckduckgo_search import DDGS
from pytrends.request import TrendReq

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全球廚電情報中心 Ultimate", page_icon="🍳", layout="wide")

# --- 2. Session State 初始化 ---
if 'favorites' not in st.session_state:
    st.session_state.favorites = pd.DataFrame(columns=['Folder', 'Date', 'Title', 'Link', 'Source'])

if 'folder_list' not in st.session_state:
    st.session_state.folder_list = ["📥 未分類", "🔥 方太 (Fotile)", "🔥 老闆 (Robam)", "🇪🇺 歐系品牌", "🇺🇸 美系品牌"]

if 'search_results' not in st.session_state:
    st.session_state.search_results = pd.DataFrame()

# --- 3. 爬蟲函數群 ---

# A. Google News
def fetch_google_news(keyword, lang, region):
    search_query = keyword
    target_gl = region
    try: target_ceid = f"{region}:{lang.split('-')[0]}"
    except: target_ceid = f"{region}:en"

    if (region in ["US", "CA"]) and ("zh" in lang):
        if region == "US": search_query = f"{keyword} (美國 OR 北美 OR USA)"
        elif region == "CA": search_query = f"{keyword} (加拿大 OR Canada OR 温哥华 OR 多伦多)"
        target_gl = "TW"
        target_ceid = "TW:zh-Hant"

    if region == "HK" and "zh" in lang:
        target_ceid = "HK:zh-Hant"
        target_gl = "HK"

    encoded_keyword = urllib.parse.quote(search_query)
    target_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl={lang}&gl={target_gl}&ceid={target_ceid}"
    
    try:
        feed = feedparser.parse(target_url)
        data = []
        if feed.entries:
            for entry in feed.entries:
                try: pub_date = datetime(*entry.published_parsed[:6])
                except: pub_date = datetime.now()
                data.append({
                    "Select": False,
                    "Date": pub_date,
                    "Type": "📰 新聞",
                    "Title": entry.title,
                    "Source": entry.source.title if 'source' in entry else "Google News",
                    "Link": entry.link
                })
            return pd.DataFrame(data)
        else: return pd.DataFrame()
    except: return pd.DataFrame()

# B. DuckDuckGo (查價邏輯已優化)
def fetch_web_search(keyword, region_code, time_range, platform_mode=None):
    if region_code == "US": ddg_region = "us-en"
    elif region_code == "CA": ddg_region = "ca-en"
    elif region_code == "HK": ddg_region = "hk-tzh"
    else: ddg_region = "wt-wt"
    
    ddg_time = None 
    if time_range == "過去一天": ddg_time = "d"
    elif time_range == "過去一週": ddg_time = "w"
    elif time_range == "過去一個月": ddg_time = "m"
    elif time_range == "過去一年": ddg_time = "y"
    
    final_keyword = keyword
    search_region = ddg_region
    source_type = "🌐 全網"

    if platform_mode == "reddit":
        final_keyword = f"{keyword} site:reddit.com"
        source_type = "💬 Reddit"
    elif platform_mode == "pinterest":
        final_keyword = f"{keyword} site:pinterest.com"
        source_type = "📌 Pinterest"
    elif platform_mode == "shopping":
        # 🔥 優化：關鍵字更自然，容易搜到電商
        final_keyword = f"buy {keyword} online price"
        source_type = "💰 價格情報"
    else:
        source_type = "🌐 論壇/部落格"
        is_chinese_query = any(u'\u4e00' <= c <= u'\u9fff' for c in keyword)
        if (region_code in ["US", "CA"]) and is_chinese_query:
            search_region = "wt-wt"
            if region_code == "US": final_keyword = f"{keyword} (美國 OR 北美 OR 華人)"
            elif region_code == "CA": final_keyword = f"{keyword} (加拿大 OR 温哥華 OR 多倫多)"

    try:
        results = DDGS().text(keywords=final_keyword, region=search_region, time=ddg_time, max_results=30)
        data = []
        if results:
            for r in results:
                link = r.get('href', '')
                title = r.get('title', '')
                if link and title:
                    try: source_domain = urllib.parse.urlparse(link).netloc
                    except: source_domain = "Web"
                    data.append({
                        "Select": False,
                        "Date": datetime.now(),
                        "Type": source_type,
                        "Title": title,
                        "Source": source_domain,
                        "Link": link
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
                if not df.empty: frames.append(df)
            
    if "論壇與部落格 (Web/Blogs)" in search_types:
        df = fetch_web_search(keyword, region_code, time_range, platform_mode=None)
        if not df.empty: frames.append(df)

    if "Reddit 討論區" in search_types:
        df = fetch_web_search(keyword, region_code, time_range, platform_mode="reddit")
        if not df.empty: frames.append(df)
        
    if "Pinterest 靈感" in search_types:
        df = fetch_web_search(keyword, region_code, time_range, platform_mode="pinterest")
        if not df.empty: frames.append(df)

    if frames:
        result = pd.concat(frames)
        if 'Select' not in result.columns: result['Select'] = False
        result = result.drop_duplicates(subset=['Link'])
        return result
    else: return pd.DataFrame(columns=['Select', 'Type', 'Date', 'Title', 'Link', 'Source'])

# D. Google Trends
def fetch_trends_data(keywords, geo='US', timeframe='today 12-m'):
    try:
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10,25))
        pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo)
        interest_over_time_df = pytrends.interest_over_time()
        if not interest_over_time_df.empty and 'isPartial' in interest_over_time_df.columns:
            interest_over_time_df = interest_over_time_df.drop(columns=['isPartial'])
        related_queries = pytrends.related_queries()
        related_df = pd.DataFrame()
        if related_queries and keywords[0] in related_queries and related_queries[keywords[0]]['top'] is not None:
            related_df = related_queries[keywords[0]]['top'].head(10)
        return interest_over_time_df, related_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

# --- 4. 側邊欄導航 ---
with st.sidebar:
    st.title("🗂️ 系統導航")
    page = st.radio("前往專區", ["🔍 情報搜尋", "📈 趨勢分析儀", "💰 競品比價中心", "📂 競品資料夾"])
    st.divider()
    
    st.subheader("⚙️ 資料夾管理")
    new_folder = st.text_input("新增資料夾", placeholder="例如: Pinterest 靈感板")
    if st.button("➕ 新增"):
        if new_folder and new_folder not in st.session_state.folder_list:
            st.session_state.folder_list.append(new_folder)
            st.success(f"已新增: {new_folder}")
            st.rerun()
    st.caption(f"已收藏: {len(st.session_state.favorites)} 筆")

# --- 5. 頁面邏輯 ---

if page == "🔍 情報搜尋":
    st.title("🔍 情報搜尋")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: search_kw = st.text_input("輸入關鍵字 (可多個)", placeholder="例如: Fotile, Robam, Review...")
    with col2: location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
    with col3: time_range = st.selectbox("時間範圍", ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"])
    
    st.markdown("---")
    col_logic, col_scope = st.columns([1, 2])
    with col_logic:
        search_logic = st.radio("🔗 關鍵字邏輯", ["🔄 個別分開搜 (A, B)", "🔀 聯集搜尋 (A OR B)", "➕ 交集搜尋 (A AND B)"])
    with col_scope:
        search_scope = st.multiselect("選擇搜尋頻道", ["新聞媒體 (News)", "論壇與部落格 (Web/Blogs)", "Reddit 討論區", "Pinterest 靈感"], default=["新聞媒體 (News)"])
    st.markdown("---")

    if st.button("🚀 開始搜尋", type="primary"):
        if search_kw:
            keywords_list = [k.strip() for k in search_kw.split(",") if k.strip()]
            st.session_state.search_results = pd.DataFrame()
            
            if "個別分開搜" in search_logic:
                all_frames = []
                progress_bar = st.progress
