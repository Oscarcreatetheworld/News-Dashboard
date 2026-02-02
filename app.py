import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全球廚電情報策展台", page_icon="🎯", layout="wide")
st.title("🎯 全球廚電情報策展台 (Search & Select)")

# --- 2. 初始化 Session State (用來暫存你的精選清單) ---
if 'favorites' not in st.session_state:
    st.session_state.favorites = pd.DataFrame(columns=['Date', 'Title', 'Link', 'Source'])

if 'search_results' not in st.session_state:
    st.session_state.search_results = pd.DataFrame()

# --- 3. 核心爬蟲函數 ---

def fetch_google_news(keyword, lang, region):
    # 智慧搜尋邏輯
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
            try:
                pub_date = datetime(*entry.published_parsed[:6])
            except:
                pub_date = datetime.now()
            data.append({
                "Select": False, # 預設不勾選
                "Date": pub_date,
                "Type": "新聞",
                "Title": entry.title,
                "Source": entry.source.title if 'source' in entry else "Google News",
                "Link": entry.link
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

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
    
    final_keyword = keyword
    search_region = ddg_region
    is_chinese_query = any(u'\u4e00' <= c <= u'\u9fff' for c in keyword)
    
    if (region_code in ["US", "CA"]) and is_chinese_query:
        search_region = "wt-wt"
        if region_code == "US": final_keyword = f"{keyword} (美國 OR 北美 OR 華人)"
        elif region_code == "CA": final_keyword = f"{keyword} (加拿大 OR 温哥華 OR 多倫多)"

    try:
        results = DDGS().text(keywords=final_keyword, region=search_region, time=ddg_time, max_results=40)
        data = []
        for r in results:
            data.append({
                "Select": False,
                "Date": datetime.now(),
                "Type": "全網",
                "Title": r['title'],
                "Source": urllib.parse.urlparse(r['href']).netloc,
                "Link": r['href']
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

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
                frames.append(fetch_google_news(keyword, lang, region))
            
    if "論壇與部落格 (Forums/Blogs)" in search_types:
        frames.append(fetch_web_search(keyword, region_code, time_range))

    if frames:
        result = pd.concat(frames).drop_duplicates(subset=['Link'])
        # 確保 Select 欄位在最前面
        cols = ['Select'] + [c for c in result.columns if c != 'Select']
        return result[cols]
    else:
        return pd.DataFrame()

# --- 4. 側邊欄 (顯示精選清單) ---
with st.sidebar:
    st.header("🌟 我的精選清單")
    
    if not st.session_state.favorites.empty:
        fav_count = len(st.session_state.favorites)
        st.success(f"目前已收藏 {fav_count} 筆資料")
        
        # 顯示清單預覽
        st.dataframe(
            st.session_state.favorites[['Title', 'Source']], 
            use_container_width=True, 
            hide_index=True
        )
        
        # 下載按鈕
        csv = st.session_state.favorites.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下載精選清單 (CSV)",
            data=csv,
            file_name=f'kitchen_favorites_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
        )
        
        if st.button("🗑️ 清空清單"):
            st.session_state.favorites = pd.DataFrame(columns=['Date', 'Title', 'Link', 'Source'])
            st.rerun()
    else:
        st.info("尚未收藏任何資料。請在右側搜尋後勾選加入。")

# --- 5. 主畫面 (搜尋與挑選) ---

st.subheader("📡 情報搜尋")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    search_kw = st.text_input("輸入關鍵字", placeholder="例如: 抽油煙機, 方太, Robam...")
with col2:
    location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
with col3:
    time_range = st.selectbox("⏱️ 時間範圍", ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"])

search_scope = st.multiselect(
    "搜尋來源",
    ["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"],
    default=["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"]
)

# 搜尋按鈕
if st.button("🚀 搜尋", type="primary"):
    if search_kw:
        with st.spinner("正在搜尋中..."):
            st.session_state.search_results = run_hybrid_search(search_kw, location, search_scope, time_range)

# 顯示搜尋結果 (如果有的話)
if not st.session_state.search_results.empty:
    st.divider()
    st.markdown(f"### 🔍 搜尋結果 (共 {len(st.session_state.search_results)} 筆)")
    st.info("請勾選你覺得有價值的情報，然後點擊下方的「加入精選」按鈕。")
    
    # 使用 Data Editor 讓使用者可以勾選
    edited_df = st.data_editor(
        st.session_state.search_results,
        column_config={
            "Select": st.column_config.CheckboxColumn("收藏", help="勾選以加入清單", width="small"),
            "Link": st.column_config.LinkColumn("連結", display_text="Go", width="small"),
            "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD", width="small"),
            "Title": st.column_config.TextColumn("標題"),
        },
        use_container_width=True,
        hide_index=True,
        key="data_editor" # 關鍵：給定 key 才能抓到狀態
    )
    
    # 加入精選按鈕
    if st.button("🌟 將勾選項目加入精選清單"):
        # 找出被勾選的行
        selected_rows = edited_df[edited_df['Select'] == True]
        
        if not selected_rows.empty:
            # 移除 Select 欄位後加入精選
            to_add = selected_rows.drop(columns=['Select'])
            st.session_state.favorites = pd.concat([st.session_state.favorites, to_add]).drop_duplicates(subset=['Link'])
            st.success(f"成功加入 {len(selected_rows)} 筆資料！請看左側側邊欄。")
            st.rerun() # 重新整理頁面以更新側邊欄
        else:
            st.warning("你還沒勾選任何項目喔！")

elif search_kw:
    st.warning("按一下搜尋按鈕開始找資料吧！")
