import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime
from duckduckgo_search import DDGS

# --- 1. 頁面與基礎設定 ---
st.set_page_config(page_title="全球廚電情報中心", page_icon="🗂️", layout="wide")

# --- 2. Session State 初始化 (資料庫與資料夾結構) ---
# 這是這個 App 的記憶體
if 'favorites' not in st.session_state:
    # 建立一個空的資料框，多了一個 'Folder' 欄位
    st.session_state.favorites = pd.DataFrame(columns=['Folder', 'Date', 'Title', 'Link', 'Source'])

if 'folder_list' not in st.session_state:
    # 預設的資料夾 (你可以自己改)
    st.session_state.folder_list = ["📥 未分類", "🔥 方太 (Fotile)", "🔥 老闆 (Robam)", "🇪🇺 歐系品牌", "🇰🇷 韓系品牌"]

if 'search_results' not in st.session_state:
    st.session_state.search_results = pd.DataFrame()

# --- 3. 爬蟲函數 (維持不變，功能最強大) ---
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
                "Type": "新聞",
                "Title": entry.title,
                "Source": entry.source.title if 'source' in entry else "Google News",
                "Link": entry.link
            })
        return pd.DataFrame(data)
    except: return pd.DataFrame()

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
    except: return pd.DataFrame()

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
        cols = ['Select'] + [c for c in result.columns if c != 'Select']
        return result[cols]
    else: return pd.DataFrame()

# --- 4. 側邊欄導航 (Sidebar Navigation) ---
with st.sidebar:
    st.title("🗂️ 系統導航")
    page = st.radio("前往專區", ["🔍 情報搜尋專區", "📂 競品資料夾 (精選)"])
    
    st.divider()
    
    # 資料夾管理功能 (不論在哪一頁都能管理)
    st.subheader("⚙️ 資料夾管理")
    new_folder = st.text_input("新增資料夾名稱", placeholder="例如: Samsung")
    if st.button("➕ 新增"):
        if new_folder and new_folder not in st.session_state.folder_list:
            st.session_state.folder_list.append(new_folder)
            st.success(f"已新增: {new_folder}")
            st.rerun()
            
    st.divider()
    st.caption(f"目前資料庫總筆數: {len(st.session_state.favorites)}")

# --- 5. 頁面邏輯 ---

# === 頁面 A: 情報搜尋專區 ===
if page == "🔍 情報搜尋專區":
    st.title("🔍 情報搜尋專區")
    st.caption("在此處搜尋全網情報，勾選後「分發」到指定的競品資料夾中。")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: Range Hood, 方太, Robam...")
    with col2:
        location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
    with col3:
        time_range = st.selectbox("時間範圍", ["不限時間 (預設)", "過去一天", "過去一週", "過去一個月", "過去一年"])

    search_scope = st.multiselect(
        "搜尋來源", ["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"], default=["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"]
    )

    if st.button("🚀 開始搜尋", type="primary"):
        if search_kw:
            with st.spinner("正在全網掃描中..."):
                st.session_state.search_results = run_hybrid_search(search_kw, location, search_scope, time_range)

    # 顯示搜尋結果與分發介面
    if not st.session_state.search_results.empty:
        st.divider()
        st.markdown(f"### 📋 搜尋結果 ({len(st.session_state.search_results)} 筆)")
        
        # 1. 選擇要分發的資料夾
        target_folder = st.selectbox("📥 請選擇要存入的資料夾:", st.session_state.folder_list)
        
        # 2. 顯示勾選列表
        edited_df = st.data_editor(
            st.session_state.search_results,
            column_config={
                "Select": st.column_config.CheckboxColumn("收藏", width="small"),
                "Link": st.column_config.LinkColumn("連結", display_text="Go", width="small"),
                "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD", width="small"),
                "Title": st.column_config.TextColumn("標題"),
            },
            use_container_width=True,
            hide_index=True,
            key="search_editor"
        )
        
        # 3. 加入按鈕
        if st.button(f"⬇️ 將勾選項目加入「{target_folder}」"):
            selected_rows = edited_df[edited_df['Select'] == True].copy()
            if not selected_rows.empty:
                # 幫這些資料貼上標籤 (Tagging)
                selected_rows['Folder'] = target_folder
                # 移除 Select 欄位
                to_add = selected_rows.drop(columns=['Select'])
                # 合併到主資料庫
                st.session_state.favorites = pd.concat([st.session_state.favorites, to_add]).drop_duplicates(subset=['Link'])
                
                st.toast(f"✅ 成功將 {len(selected_rows)} 筆資料加入 {target_folder}！")
                st.success(f"已存入 {target_folder}，請切換至「📂 競品資料夾」查看。")
            else:
                st.warning("請先勾選資料！")

# === 頁面 B: 競品資料夾 (精選) ===
elif page == "📂 競品資料夾 (精選)":
    st.title("📂 競品情報資料庫")
    st.caption("這裡存放你所有篩選過的情報，已按資料夾分類。")

    if st.session_state.favorites.empty:
        st.info("目前資料庫是空的，請先去「🔍 搜尋專區」抓取資料。")
    else:
        # 使用 Tabs 呈現不同資料夾
        # 為了避免 Tab 太多，我們先過濾出「有資料的資料夾」+「預設列表」的聯集
        active_folders = [f for f in st.session_state.folder_list]
        tabs = st.tabs(active_folders)

        for i, folder_name in enumerate(active_folders):
            with tabs[i]:
                # 篩選出屬於這個資料夾的資料
                folder_data = st.session_state.favorites[st.session_state.favorites['Folder'] == folder_name]
                
                if not folder_data.empty:
                    st.write(f"📁 **{folder_name}** 共有 {len(folder_data)} 筆資料")
                    
                    st.dataframe(
                        folder_data[['Date', 'Title', 'Source', 'Link']],
                        column_config={
                            "Link": st.column_config.LinkColumn("連結", display_text="Go"),
                            "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # 該資料夾的下載按鈕
                    csv = folder_data.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label=f"📥 下載「{folder_name}」報表 (CSV)",
                        data=csv,
                        file_name=f'{folder_name}_report.csv',
                        mime='text/csv',
                    )
                    
                    # 刪除功能 (進階)
                    if st.button(f"🗑️ 清空「{folder_name}」的所有資料", key=f"del_{i}"):
                        # 保留「不屬於」這個資料夾的資料
                        st.session_state.favorites = st.session_state.favorites[st.session_state.favorites['Folder'] != folder_name]
                        st.rerun()
                else:
                    st.info(f"「{folder_name}」目前沒有資料。")
