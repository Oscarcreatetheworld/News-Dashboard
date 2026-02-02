import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全球廚電情報中心 Pro", page_icon="🍳", layout="wide")

# --- 2. Session State 初始化 ---
if 'favorites' not in st.session_state:
    st.session_state.favorites = pd.DataFrame(columns=['Folder', 'Date', 'Title', 'Link', 'Source'])

if 'folder_list' not in st.session_state:
    st.session_state.folder_list = ["📥 未分類", "🔥 方太 (Fotile)", "🔥 老闆 (Robam)", "🇪🇺 歐系品牌", "🇺🇸 美系品牌"]

if 'search_results' not in st.session_state:
    st.session_state.search_results = pd.DataFrame()

# --- 3. 爬蟲函數群 ---

# A. 新聞爬蟲 (Google News)
def fetch_google_news(keyword, lang, region):
    search_query = keyword
    target_gl = region
    target_ceid = f"{region}:{lang.split('-')[0]}"
    
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
    except: return pd.DataFrame()

# B. 通用全網/特定平台爬蟲 (DuckDuckGo)
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
        print(f"Error: {e}")
        return pd.DataFrame()

# C. 混合搜索控制器 (🔥 重點修復區)
def run_hybrid_search(keyword, location_choice, search_types, time_range):
    frames = []
    
    # 定義任務
    if location_choice == "🇺🇸 美國 (US)":
        news_tasks = [("en-US", "US"), ("zh-TW", "US")]
        region_code = "US"
    elif location_choice == "🇨🇦 加拿大 (CA)":
        news_tasks = [("en-CA", "CA"), ("zh-TW", "CA")]
        region_code = "CA"
    elif location_choice == "🇭🇰 香港 (HK)":
        news_tasks = [("zh-HK", "HK"), ("en-HK", "HK")]
        region_code = "HK"
    
    # 執行任務
    if "新聞媒體 (News)" in search_types:
        if time_range in ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月"]:
            for lang, region in news_tasks:
                frames.append(fetch_google_news(keyword, lang, region))
            
    if "論壇與部落格 (Web/Blogs)" in search_types:
        frames.append(fetch_web_search(keyword, region_code, time_range, platform_mode=None))

    if "Reddit 討論區" in search_types:
        frames.append(fetch_web_search(keyword, region_code, time_range, platform_mode="reddit"))

    if "Pinterest 靈感" in search_types:
        frames.append(fetch_web_search(keyword, region_code, time_range, platform_mode="pinterest"))

    # 合併結果 (🔥 這裡加了防呆機制)
    if frames:
        result = pd.concat(frames)
        
        # 1. 如果合併出來是空的 (全軍覆沒)，直接回傳空表，不要往下跑
        if result.empty:
            return pd.DataFrame(columns=['Select', 'Type', 'Date', 'Title', 'Link', 'Source'])
            
        # 2. 如果因為某些原因 Select 欄位不見了，把它加回去
        if 'Select' not in result.columns:
            result['Select'] = False

        result = result.drop_duplicates(subset=['Link'])
        
        # 3. 安全地排序欄位
        cols = ['Select'] + [c for c in result.columns if c != 'Select']
        return result[cols]
    else:
        # 如果根本沒有任務執行
        return pd.DataFrame(columns=['Select', 'Type', 'Date', 'Title', 'Link', 'Source'])

# --- 4. 側邊欄導航 ---
with st.sidebar:
    st.title("🗂️ 系統導航")
    page = st.radio("前往專區", ["🔍 情報搜尋", "📂 競品資料夾"])
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
    with col1:
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: Kitchen Island Ideas, Range Hood...")
    with col2:
        location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
    with col3:
        time_range = st.selectbox("時間範圍", ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"])

    search_scope = st.multiselect(
        "選擇搜尋頻道", 
        ["新聞媒體 (News)", "論壇與部落格 (Web/Blogs)", "Reddit 討論區", "Pinterest 靈感"],
        default=["新聞媒體 (News)"]
    )

    if st.button("🚀 開始搜尋", type="primary"):
        if search_kw:
            with st.spinner("正在各大平台掃描中..."):
                st.session_state.search_results = run_hybrid_search(search_kw, location, search_scope, time_range)
