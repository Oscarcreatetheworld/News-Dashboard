import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime
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

# B. DuckDuckGo (一般 & 比價用)
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
    elif platform_mode == "shopping": # 新增：查價模式
        # 強制加上 price 關鍵字，並排除一些無關資訊
        final_keyword = f"{keyword} price (buy OR shop OR deal)"
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
    except: return pd.DataFrame()

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
        cols = ['Select'] + [c for c in result.columns if c != 'Select']
        return result[cols]
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
    # 新增第四個選項
    page = st.radio("前往專區", ["🔍 情報搜尋", "📈 趨勢分析儀", "💰 競品比價中心 (New)", "📂 競品資料夾"])
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
    with col1: search_kw = st.text_input("輸入關鍵字", placeholder="例如: Kitchen Island Ideas...")
    with col2: location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
    with col3: time_range = st.selectbox("時間範圍", ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"])
    search_scope = st.multiselect("選擇搜尋頻道", ["新聞媒體 (News)", "論壇與部落格 (Web/Blogs)", "Reddit 討論區", "Pinterest 靈感"], default=["新聞媒體 (News)"])
    if st.button("🚀 開始搜尋", type="primary"):
        if search_kw:
            with st.spinner("正在搜尋中..."):
                st.session_state.search_results = run_hybrid_search(search_kw, location, search_scope, time_range)
    
    if not st.session_state.search_results.empty:
        st.divider()
        st.markdown(f"### 📋 搜尋結果 ({len(st.session_state.search_results)} 筆)")
        target_folder = st.selectbox("📥 存入資料夾:", st.session_state.folder_list)
        edited_df = st.data_editor(st.session_state.search_results, column_config={"Select": st.column_config.CheckboxColumn("收藏", width="small"), "Link": st.column_config.LinkColumn("連結", display_text="Go", width="small")}, use_container_width=True, hide_index=True, key="search_editor")
        if st.button(f"⬇️ 加入「{target_folder}」"):
            selected_rows = edited_df[edited_df['Select'] == True].copy()
            if not selected_rows.empty:
                selected_rows['Folder'] = target_folder
                to_add = selected_rows.drop(columns=['Select'])
                st.session_state.favorites = pd.concat([st.session_state.favorites, to_add]).drop_duplicates(subset=['Link'])
                st.success(f"已存入 {target_folder}！")
            else: st.warning("請先勾選資料！")

elif page == "📈 趨勢分析儀":
    st.title("📈 Google 趨勢分析儀")
    st.markdown("比較關鍵字在一段時間內的熱度變化。")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: trend_input = st.text_input("輸入關鍵字 (可多個，用逗號分隔)", "Fotile, Robam, Pacific")
    with col2: trend_geo = st.selectbox("地區", ["US", "CA", "HK"])
    with col3: trend_time = st.selectbox("時間範圍", ["today 12-m", "today 1-m", "today 5-y"])
    if st.button("📊 分析趨勢", type="primary"):
        kw_list = [k.strip() for k in trend_input.split(",") if k.strip()]
        if kw_list:
            with st.spinner(f"正在分析 {kw_list} ..."):
                trend_df, related_df = fetch_trends_data(kw_list, trend_geo, trend_time)
                if not trend_df.empty:
                    st.line_chart(trend_df)
                    if not related_df.empty:
                        st.subheader(f"💡 搜「{kw_list[0]}」的人也搜了...")
                        st.dataframe(related_df, use_container_width=True)
                else: st.link_button("👉 前往 Google Trends 官網 (備用)", f"https://trends.google.com/trends/explore?date={trend_time.replace(' ', '%20')}&geo={trend_geo}&q={','.join(kw_list)}")

# === 新增：競品比價中心 ===
elif page == "💰 競品比價中心 (New)":
    st.title("💰 競品比價中心 (Price Monitor)")
    st.markdown("快速查看競品官網價格，或搜尋特定型號的通路售價。")
    
    # 1. 官網快速傳送門 (靜態連結)
    st.subheader("🚀 官網快速傳送門 (Quick Links)")
    st.info("點擊按鈕直接開啟競品「抽油煙機/廚電」商店頁面")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**🇺🇸 方太 (Fotile)**")
        st.link_button("Go to Store", "https://us.fotileglobal.com/collections/range-hoods")
    with col2:
        st.markdown("**🇺🇸 老闆 (Robam)**")
        st.link_button("Go to Store", "https://robamliving.com/collections/range-hood")
    with col3:
        st.markdown("**🇺🇸 太平洋 (Pacific)**")
        st.link_button("Go to Store", "https://www.2pacific.com/zh-cn/")
    with col4:
        st.markdown("**🇺🇸 Hauslane**")
        st.link_button("Go to Store", "https://hauslane.com/collections/range-hoods")
    with col5:
        st.markdown("**🇺🇸 Le Kitchen**")
        st.link_button("Go to Store", "https://www.lekitcheninc.com/")
    st.divider()

    # 2. 型號全網查價
    st.subheader("🔎 特定型號查價")
    st.caption("輸入型號，系統會搜尋 Amazon, Best Buy, Home Depot 等通路的價格頁面。")
    
    col_a, col_b = st.columns([3, 1])
    with col_a:
        price_kw = st.text_input("輸入產品型號", placeholder="例如: JQG7501, A831, UC-PS18...")
    with col_b:
        price_region = st.selectbox("查價地區", ["US", "CA"])
    
    if st.button("💰 搜尋價格情報"):
        if price_kw:
            with st.spinner(f"正在搜尋 {price_kw} 的價格資訊..."):
                # 使用特殊的 shopping 模式
                price_df = fetch_web_search(price_kw, price_region, "過去一個月", platform_mode="shopping")
                
                if not price_df.empty:
                    st.success(f"找到 {len(price_df)} 筆相關價格頁面")
                    st.dataframe(
                        price_df[['Title', 'Source', 'Link']],
                        column_config={
                            "Link": st.column_config.LinkColumn("點擊查價", display_text="Go ->"),
                            "Source": st.column_config.TextColumn("通路/來源"),
                            "Title": st.column_config.TextColumn("商品標題"),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.warning("找不到明確的價格頁面，建議直接點擊上方官網查詢。")

elif page == "📂 競品資料夾":
    st.title("📂 競品情報資料庫")
    if st.session_state.favorites.empty: st.info("目前資料庫是空的。")
    else:
        active_folders = [f for f in st.session_state.folder_list]
        tabs = st.tabs(active_folders)
        for i, folder_name in enumerate(active_folders):
            with tabs[i]:
                folder_data = st.session_state.favorites[st.session_state.favorites['Folder'] == folder_name]
                if not folder_data.empty:
                    st.write(f"📁 **{folder_name}** ({len(folder_data)} 筆)")
                    st.dataframe(folder_data[['Type', 'Date', 'Title', 'Link']], column_config={"Link": st.column_config.LinkColumn("連結", display_text="Go"), "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD")}, use_container_width=True, hide_index=True)
                    csv = folder_data.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(label="📥 下載 CSV", data=csv, file_name=f'{folder_name}.csv', mime='text/csv')
                    if st.button(f"🗑️ 清空此資料夾", key=f"del_{i}"):
                        st.session_state.favorites = st.session_state.favorites[st.session_state.favorites['Folder'] != folder_name]
                        st.rerun()
                else: st.info("無資料。")
