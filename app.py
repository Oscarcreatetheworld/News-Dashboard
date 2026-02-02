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

# --- 3. 爬蟲函數群 (強化除錯能力) ---

# A. 新聞爬蟲 (Google News) - 最穩定的來源
def fetch_google_news(keyword, lang, region):
    search_query = keyword
    target_gl = region
    # 處理語系設定
    try:
        ceid_lang = lang.split('-')[0]
        target_ceid = f"{region}:{ceid_lang}"
    except:
        target_ceid = f"{region}:en"

    # 北美中文優化
    if (region in ["US", "CA"]) and ("zh" in lang):
        if region == "US": search_query = f"{keyword} (美國 OR 北美 OR USA)"
        elif region == "CA": search_query = f"{keyword} (加拿大 OR Canada OR 温哥华 OR 多伦多)"
        target_gl = "TW" # 借用台灣介面搜海外內容
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
        else:
            return pd.DataFrame()
    except Exception as e:
        st.toast(f"Google News 讀取錯誤: {e}", icon="⚠️")
        return pd.DataFrame()

# B. 全網爬蟲 (DuckDuckGo) - 容易被擋，加強例外處理
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
        # 簡單判斷中文
        is_chinese_query = any(u'\u4e00' <= c <= u'\u9fff' for c in keyword)
        if (region_code in ["US", "CA"]) and is_chinese_query:
            search_region = "wt-wt"
            if region_code == "US": final_keyword = f"{keyword} (美國 OR 北美 OR 華人)"
            elif region_code == "CA": final_keyword = f"{keyword} (加拿大 OR 温哥華 OR 多倫多)"

    try:
        # 這裡是關鍵：DDGS 很容易在雲端失敗，要接住它
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
        # 這裡不讓它報錯，而是回傳空表，並在畫面提示
        st.toast(f"論壇搜尋暫時被阻擋 (Rate Limit)，請稍後再試。錯誤: {e}", icon="🚫")
        return pd.DataFrame()

# C. 混合搜索控制器 (確保即使一個失敗，另一個也能顯示)
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
    
    # 執行新聞搜尋
    if "新聞媒體 (News)" in search_types:
        if time_range in ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月"]:
            for lang, region in news_tasks:
                df = fetch_google_news(keyword, lang, region)
                if not df.empty: frames.append(df)
            
    # 執行論壇搜尋
    if "論壇與部落格 (Web/Blogs)" in search_types:
        df = fetch_web_search(keyword, region_code, time_range, platform_mode=None)
        if not df.empty: frames.append(df)

    if "Reddit 討論區" in search_types:
        df = fetch_web_search(keyword, region_code, time_range, platform_mode="reddit")
        if not df.empty: frames.append(df)

    if "Pinterest 靈感" in search_types:
        df = fetch_web_search(keyword, region_code, time_range, platform_mode="pinterest")
        if not df.empty: frames.append(df)

    # 合併結果
    if frames:
        result = pd.concat(frames)
        # 再次確保 Select 欄位存在
        if 'Select' not in result.columns:
            result['Select'] = False
        
        result = result.drop_duplicates(subset=['Link'])
        
        # 確保欄位順序正確，避免 KeyError
        expected_cols = ['Select', 'Type', 'Date', 'Title', 'Link', 'Source']
        # 只保留存在的欄位
        final_cols = [c for c in expected_cols if c in result.columns]
        
        return result[final_cols]
    else:
        # 全軍覆沒時回傳空表
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
            with st.spinner("正在搜尋中... (若論壇無資料可能為暫時阻擋)"):
                st.session_state.search_results = run_hybrid_search(search_kw, location, search_scope, time_range)
                
                # 檢查搜尋結果狀態
                if st.session_state.search_results.empty:
                    st.warning("⚠️ 搜尋完成，但沒有找到資料。")
                    st.info("可能原因：\n1. 該關鍵字近期無新聞。\n2. 論壇搜尋 (DuckDuckGo) 暫時阻擋了雲端請求 (請過幾分鐘再試)。\n3. 嘗試只勾選「新聞媒體」試試看。")

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
