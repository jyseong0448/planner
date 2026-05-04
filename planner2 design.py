import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import os

# --- 설정 및 데이터 로드 ---
DB_FILE = 'study_data.csv'
REVIEW_INTERVALS = [0, 1, 3, 7, 15]

def load_data():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df['start_date'] = pd.to_datetime(df['start_date']).dt.date
        df['completed_intervals'] = df['completed_intervals'].astype(str).replace('nan', '')
        return df
    return pd.DataFrame(columns=['subject', 'topic', 'start_date', 'completed_intervals'])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# 페이지 설정
st.set_page_config(page_title="감성 기말고사 플래너", layout="wide")

# --- 💡 체크박스 및 전역 폰트 스타일 변경 (CSS 주입) ---
st.markdown("""
<style>
/* 체크박스(과제 내용) 글씨체 변경: 날짜와 동일하게, 굵기는 얇게 */
.stCheckbox label p {
    font-family: 'Courier New', monospace !important;
    font-weight: 400 !important;
    font-size: 16px !important;
    color: #222 !important;
}
</style>
""", unsafe_allow_html=True)

if 'df' not in st.session_state:
    st.session_state.df = load_data()

# --- 한국 표준시(KST) 고정 ---
KST = timezone(timedelta(hours=9))
today = datetime.now(KST)
today_date = today.date()

# --- 상단 다이어리 헤더 UI ---
date_str = today.strftime("%Y.%m.%d %a").upper()
exam_date = datetime(2026, 7, 1).date()
d_day = (exam_date - today_date).days
d_day_display = f"D-{d_day}" if d_day > 0 else "D-Day" if d_day == 0 else f"D+{abs(d_day)}"

header_html = f"""
<div style="border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end;">
    <div>
        <div style="font-size: 14px; color: #777; font-family: 'Gothic A1', sans-serif; letter-spacing: 1px;">Believe in myself.</div>
        <div style="font-size: 42px; font-weight: 800; font-family: 'Courier New', monospace; color: #222;">{date_str}</div>
    </div>
    <div style="font-size: 48px; font-weight: 900; color: #ff4b4b; font-family: 'Courier New', monospace;">{d_day_display}</div>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

# --- 사이드바: 새로운 학습 추가 ---
with st.sidebar:
    st.header("📝 새 계획 추가")
    with st.form("add_form", clear_on_submit=True):
        sub = st.text_input("과목명 (예: 물리학 II)")
        top = st.text_input("학습 내용")
        date = st.date_input("학습 시작일", today_date)
        submitted = st.form_submit_button("추가하기")
        
        if submitted and sub and top:
            new_data = {'subject': sub, 'topic': top, 'start_date': date, 'completed_intervals': ""}
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
            save_data(st.session_state.df)
            st.rerun()

# --- 메인 화면 로직: 밀린 일 이월 ---
todays_tasks = []

for idx, row in st.session_state.df.iterrows():
    start_date = row['start_date']
    completed_list = str(row['completed_intervals']).split(',') if pd.notna(row['completed_intervals']) and row['completed_intervals'] != '' else []
    
    for interval in REVIEW_INTERVALS:
        target_date = start_date + timedelta(days=interval)
        interval_str = str(interval)
        
        if target_date <= today_date and interval_str not in completed_list:
            
            if target_date < today_date:
                days_late = (today_date - target_date).days
                label = f"<span style='color:#ff4b4b;'>⚠️ {days_late}일 지연</span> ({'최초' if interval == 0 else str(interval) + '일차'})"
            else:
                label = "최초" if interval == 0 else f"{interval}일차"
                
            todays_tasks.append({
                'id': idx,
                'subject': row['subject'],
                'topic': row['topic'],
                'interval': interval_str,
                'label': label
            })

# --- 레이아웃 구성 ---
col1, col2 = st.columns([1.2, 0.8])

with col1:
    if not todays_tasks:
        st.write("🎉 오늘은 예정되거나 밀린 일정이 없습니다. 수고하셨어요!")
        done_count = 1; total_count = 1
    else:
        done_count = 0
        total_count = len(todays_tasks)
        
        tasks_by_subject = {}
        for task in todays_tasks:
            tasks_by_subject.setdefault(task['subject'], []).append(task)
            
        for subject, tasks in tasks_by_subject.items():
            # 💡 과목명(카테고리) 글씨체도 통일
            st.markdown(f"<h4 style='font-family: \"Courier New\", monospace; color: #444; border-left: 4px solid #aaa; padding-left: 10px; margin-top: 20px;'>{subject}</h4>", unsafe_allow_html=True)
            
            for task in tasks:
                is_done = st.checkbox(f"✔️ {task['topic']}", key=f"task_{task['id']}_{task['interval']}")
                
                # 💡 라벨(이월 표시, 회차) 글씨체도 통일
                st.markdown(f"<div style='font-family: \"Courier New\", monospace; margin-top: -30px; margin-left: 30px; font-size: 14px; color: #666;'>{task['label']}</div>", unsafe_allow_html=True)
                st.write("") 
                
                if is_done:
                    done_count += 1
                    idx = task['id']
                    current_completed = str(st.session_state.df.at[idx, 'completed_intervals'])
                    
                    if current_completed in ('', 'nan'):
                        new_val = task['interval']
                    elif task['interval'] not in current_completed.split(','):
                        new_val = f"{current_completed},{task['interval']}".strip(',')
                    else:
                        new_val = current_completed
                    
                    if st.session_state.df.at[idx, 'completed_intervals'] != new_val:
                        st.session_state.df.at[idx, 'completed_intervals'] = new_val
                        save_data(st.session_state.df)

with col2:
    st.markdown("<div style='margin-top: 40px;'></div>", unsafe_allow_html=True)
    not_done_count = total_count - done_count
    chart_data = pd.DataFrame({'상태': ['완료', '미완료'], '개수': [done_count, not_done_count]})
    
    fig = px.pie(chart_data, values='개수', names='상태', 
                 color='상태', color_discrete_map={'완료':'#8BC34A', '미완료':'#EEEEEE'},
                 hole=0.6)
    
    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), 
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      annotations=[dict(text=f"{int((done_count/total_count)*100)}%", x=0.5, y=0.5, font_size=30, showarrow=False, font=dict(family='Courier New, monospace', color='#444'))])
    st.plotly_chart(fig, use_container_width=True)

# --- 하단 관리 메뉴 ---
st.divider()
with st.expander("📂 전체 데이터 관리 (수정/삭제)"):
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True,
                               column_config={
                                   "subject": "과목", "topic": "학습 주제", 
                                   "start_date": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
                                   "completed_intervals": "완료 기록"
                               })
    if st.button("수정사항 저장"):
        st.session_state.df = edited_df
        save_data(st.session_state.df)
        st.rerun()
