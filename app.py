import streamlit as st
import pandas as pd

st.set_page_config(page_title="北美廚電戰情室", page_icon="🍳", layout="wide")

st.title("🍳 北美廚電市場監測儀表板")
st.markdown("### Real-time Market Intelligence Dashboard")

# --- 🔥 請把你的 CSV 網址貼在下面這行引號裡 ---
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQai1zkVJlpDcZhzs76S_JiCsm1JogWxdYlw4vA4k1IeWLHqiReRRY29xQm7ephIk9QJfri7OlvfdmF/pub?output=csv" 

try:
    df = pd.read_csv(sheet_url)
    
    # 側邊欄篩選
    with st.sidebar:
        st.header("篩選條件")
        cat_filter = st.selectbox("選擇情報類別", ["全部"] + list(df['Category'].unique()))

    # 內容篩選邏輯
    if cat_filter != "全部":
        df = df[df['Category'] == cat_filter]

    # 顯示數據
    st.metric("目前資料筆數", len(df))
    
    # 顯示表格 (把連結變成可點擊)
    st.data_editor(
        df,
        column_config={
            "Link": st.column_config.LinkColumn("文章連結"),
            "Title": st.column_config.TextColumn("標題"),
        },
        hide_index=True,
        use_container_width=True
    )

except Exception as e:
    st.error(f"讀取失敗，請檢查 CSV 網址是否正確。錯誤訊息: {e}")
