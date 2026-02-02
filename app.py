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

# --- 3. 爬蟲函數群 (新增平台專用邏輯) ---

# A. 新聞爬蟲 (Google News)
def fetch_google_news(keyword, lang, region):
    search_query = keyword
    target_gl = region
    target_ceid = f"{region}:{lang.split('-')[0]}"
    
    # 北美中文優化
    if (region in ["US", "CA"]) and ("zh" in lang):
        if region == "US": search_query = f"{keyword} (美國 OR 北美 OR USA)"
        elif region == "CA": search_query = f"{keyword} (加拿大 OR Canada OR 温哥华 OR 多伦多)"
        target_gl = "TW"
        target_ceid = "TW:zh-Hant"

    # 香港優化
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
    # region_code 轉換
    if region_code == "US": ddg_region = "us-en"
    elif region_code == "CA": ddg_region = "ca-en"
    elif region_code == "HK": ddg_region = "hk-tzh"
    else: ddg_region = "wt-wt"
    
    # 時間轉換
    ddg_time = None 
    if time_range == "過去一天": ddg_time = "d"
    elif time_range == "過去一週": ddg_time = "w"
    elif time_range == "過去一個月": ddg_time = "m"
    elif time_range == "過去一年": ddg_time = "y"
    
    # 關鍵字處理
    final_keyword = keyword
    search_region = ddg_region
    
    # 1. 平台鎖定邏輯 (關鍵！)
    if platform_mode == "reddit":
        final_keyword = f"{keyword} site:reddit.com"
        source_type = "💬 Reddit"
    elif platform_mode == "pinterest":
        final_keyword = f"{keyword} site:pinterest.com"
        source_type = "📌 Pinterest"
    else:
        # 一般部落格/論壇模式
        source_type = "🌐 全網/部落格"
        # 北美中文優化
        is_chinese_query = any(u'\u4e00' <= c <= u'\u9fff' for c in keyword)
        if (region_code in ["US", "CA"]) and is_chinese_query:
            search_region = "wt-wt"
            if region_code == "US": final_keyword = f"{keyword} (美國 OR 北美 OR 華人)"
            elif region_code == "CA": final_keyword = f"{keyword} (加拿大 OR 温哥華 OR 多倫多)"

    try:
        # 執行搜索
        results = DDGS().text(keywords=final_keyword, region=search_region, time=ddg_time, max_results=30)
        data = []
        for r in results:
            data.append({
                "Select": False,
                "Date": datetime.now(),
                "Type": source_type,
                "Title": r['title'],
                "Source": urllib.parse.urlparse(r['href']).netloc, # 抓網域名稱
                "Link": r['href']
            })
        return pd.DataFrame(data)
    except: return pd.DataFrame()

# C. 混合搜索控制器
def run_hybrid_search(keyword, location_choice, search_types, time_range):
    frames = []
    
    # 地區設定
    if location_choice == "🇺🇸 美國 (US)":
        news_tasks = [("en-US", "US"), ("zh-TW", "US")]
        region_code = "US"
    elif location_choice == "🇨🇦 加拿大 (CA)":
        news_tasks = [("en-CA", "CA"), ("zh-TW", "CA")]
        region_code = "CA"
    elif location_choice == "🇭🇰 香港 (HK)":
        news_tasks = [("zh-HK", "HK"), ("en-HK", "HK")]
        region_code = "HK"
    
    # 1. 新聞搜索
    if "新聞媒體 (News)" in search_types:
        if time_range in ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月"]:
            for lang, region in news_tasks:
                frames.append(fetch_google_news(keyword, lang, region))
            
    # 2. 一般全網搜索
    if "論壇與部落格 (Web/Blogs)" in search_types:
        frames.append(fetch_web_search(keyword, region_code, time_range, platform_mode=None))

    # 3. Reddit 專屬搜索
    if "Reddit 討論區" in search_types:
        frames.append(fetch_web_search(keyword, region_code, time_range, platform_mode="reddit"))

    # 4. Pinterest 專屬搜索
    if "Pinterest 靈感" in search_types:
        frames.append(fetch_web_search(keyword, region_code, time_range, platform_mode="pinterest"))

    if frames:
        result = pd.concat(frames).drop_duplicates(subset=['Link'])
        cols = ['Select'] + [c for c in result.columns if c != 'Select']
        return result[cols]
    else: return pd.DataFrame()

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

# === 頁面 A: 情報搜尋 ===
if page == "🔍 情報搜尋":
    st.title("🔍 情報搜尋")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: Kitchen Island Ideas, Range Hood...")
    with col2:
        location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
    with col3:
        time_range = st.selectbox("時間範圍", ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"])

    # 這裡新增了 Reddit 和 Pinterest 選項
    search_scope = st.multiselect(
        "選擇搜尋頻道", 
        ["新聞媒體 (News)", "論壇與部落格 (Web/Blogs)", "Reddit 討論區", "Pinterest 靈感"],
        default=["新聞媒體 (News)"]
    )

    if st.button("🚀 開始搜尋", type="primary"):
        if search_kw:
            with st.spinner("正在各大平台掃描中..."):
                st.session_state.search_results = run_hybrid_search(search_kw, location, search_scope, time_range)

    if not st.session_state.search_results.empty:
        st.divider()
        st.markdown(f"### 📋 搜尋結果 ({len(st.session_state.search_results)} 筆)")
        
        target_folder = st.selectbox("📥 存入資料夾:", st.session_state.folder_list)
        
        edited_df = st.data_editor(
            st.session_state.search_results,
            column_config={
                "Select": st.column_config.CheckboxColumn("收藏", width="small"),
                "Type": st.column_config.TextColumn("來源類型", width="small"),
                "Link": st.column_config.LinkColumn("連結", display_text="Go", width="small"),
                "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD", width="small"),
                "Title": st.column_config.TextColumn("標題"),
            },
            use_container_width=True,
            hide_index=True,
            key="search_editor"
        )
        
        if st.button(f"⬇️ 加入「{target_folder}」"):
            selected_rows = edited_df[edited_df['Select'] == True].copy()
            if not selected_rows.empty:
                selected_rows['Folder'] = target_folder
                to_add = selected_rows.drop(columns=['Select'])
                st.session_state.favorites = pd.concat([st.session_state.favorites, to_add]).drop_duplicates(subset=['Link'])
                st.success(f"已存入 {target_folder}！")
            else:
                st.warning("請先勾選資料！")

# === 頁面 B: 競品資料夾 ===
elif page == "📂 競品資料夾":
    st.title("📂 競品情報資料庫")
    
    if st.session_state.favorites.empty:
        st.info("目前資料庫是空的。")
    else:
        active_folders = [f for f in st.session_state.folder_list]
        tabs = st.tabs(active_folders)

        for i, folder_name in enumerate(active_folders):
            with tabs[i]:
                folder_data = st.session_state.favorites[st.session_state.favorites['Folder'] == folder_name]
                
                if not folder_data.empty:
                    st.write(f"📁 **{folder_name}** ({len(folder_data)} 筆)")
                    st.dataframe(
                        folder_data[['Type', 'Date', 'Title', 'Link']],
                        column_config={
                            "Link": st.column_config.LinkColumn("連結", display_text="Go"),
                            "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
                            "Type": st.column_config.TextColumn("類型", width="small"),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    csv = folder_data.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(label="📥 下載 CSV", data=csv, file_name=f'{folder_name}.csv', mime='text/csv')
                    
                    if st.button(f"🗑️ 清空此資料夾", key=f"del_{i}"):
                        st.session_state.favorites = st.session_state.favorites[st.session_state.favorites['Folder'] != folder_name]
                        st.rerun()
                else:
                    st.info("無資料。")
