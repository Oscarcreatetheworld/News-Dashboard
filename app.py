import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
from datetime import datetime, timedelta
from duckduckgo_search import DDGS

# --- 1. 頁面設定 ---
st.set_page_config(page_title="海外新聞圖書館", page_icon="📡", layout="wide")
st.title("📡 全海外新聞圖書館 (NA + HK)")

# --- 2. 核心功能函數 ---

# A. Google News 爬蟲
def fetch_google_news(keyword, lang, region):
    encoded_keyword = urllib.parse.quote(keyword)
    # Google RSS URL 組合邏輯
    # 香港特別處理: ceid=HK:zh-Hant (中文), ceid=HK:en (英文)
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
                "Snippet": "點擊連結閱讀全文..."
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# B. DuckDuckGo 全網爬蟲
def fetch_web_search(keyword, region_code):
    # 設定 DDG 的地區代碼
    if region_code == "US": ddg_region = "us-en"
    elif region_code == "CA": ddg_region = "ca-en"
    elif region_code == "HK": ddg_region = "hk-tzh" # 香港繁體
    else: ddg_region = "wt-wt"
    
    try:
        # max_results 設定抓 25 筆，避免太慢
        results = DDGS().text(keywords=keyword, region=ddg_region, max_results=25)
        
        data = []
        for r in results:
            data.append({
                "Date": datetime.now(),
                "Type": "全網 (Forum/Blog)",
                "Title": r['title'],
                "Source": urllib.parse.urlparse(r['href']).netloc,
                "Link": r['href'],
                "Snippet": r['body']
            })
        return pd.DataFrame(data)
    except Exception as e:
        # st.error(f"全網搜索錯誤: {e}") # 暫時隱藏錯誤訊息讓介面乾淨
        return pd.DataFrame()

# C. 混合搜索控制器 (新增香港邏輯)
def run_hybrid_search(keyword, location_choice, search_types):
    frames = []
    
    # 定義地區任務清單
    if location_choice == "🇺🇸 美國 (US)":
        news_tasks = [("en-US", "US"), ("zh-TW", "US")]
        ddg_region = "US"
    elif location_choice == "🇨🇦 加拿大 (CA)":
        news_tasks = [("en-CA", "CA"), ("zh-TW", "CA")]
        ddg_region = "CA"
    elif location_choice == "🇭🇰 香港 (HK)":
        # 香港：同時搜中文(zh-HK)與英文(en-HK)
        news_tasks = [("zh-HK", "HK"), ("en-HK", "HK")]
        ddg_region = "HK"
    
    # 1. 跑新聞
    if "新聞媒體 (News)" in search_types:
        for lang, region in news_tasks:
            df = fetch_google_news(keyword, lang, region)
            frames.append(df)
            
    # 2. 跑論壇
    if "論壇與部落格 (Forums/Blogs)" in search_types:
        # 針對香港論壇優化：可以在這裡幫關鍵字加料
        # 例如: if ddg_region == "HK": keyword += " site:.hk" (這是一個進階技巧，目前先不加)
        df_web = fetch_web_search(keyword, ddg_region)
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
    st.markdown("支援地區：🇺🇸 美國、🇨🇦 加拿大、🇭🇰 香港")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_kw = st.text_input("輸入關鍵字", placeholder="例如: 抽油煙機, 洗碗機, Miele, German Pool...")
    with col2:
        # 新增香港選項
        location = st.selectbox("目標市場", ["🇺🇸 美國 (US)", "🇨🇦 加拿大 (CA)", "🇭🇰 香港 (HK)"])
        
    search_scope = st.multiselect(
        "選擇搜尋來源",
        ["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"],
        default=["新聞媒體 (News)", "論壇與部落格 (Forums/Blogs)"]
    )
    
    if st.button("🚀 發射雷達", type="primary"):
        if search_kw:
            with st.spinner(f"正在掃描 {location} 的相關情報..."):
                df = run_hybrid_search(search_kw, location, search_scope)
                
                if not df.empty:
                    st.success(f"掃描完成！共發現 {len(df)} 筆情報")
                    st.data_editor(
                        df,
                        column_config={
                            "Link": st.column_config.LinkColumn("連結", display_text="Go"),
                            "Date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
                            "Title": st.column_config.TextColumn("標題", width="medium"),
                            "Type": st.column_config.TextColumn("來源", width="small"),
                            "Snippet": st.column_config.TextColumn("摘要", width="large"),
                        },
                        use_container_width=True
                    )
                else:
                    st.warning("未搜尋到結果。建議：\n1. 香港搜尋建議用繁體中文\n2. 試著搜尋當地品牌 (如: German Pool, 德國寶)")
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
        st.error("無法讀取資料庫，請檢查 CSV 網址")
