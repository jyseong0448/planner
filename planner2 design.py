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
        
        # 0.0 버그 방지 청소 함수
        def clean_intervals(val):
            if pd.isna(val) or str(val).lower() == 'nan' or str(val).strip() == '':
                return ''
            cleaned = []
            for x in str(val).split(','):
                try:
                    cleaned.append(str(int(float(x.strip()))))
                except ValueError:
                    pass
            return ','.join(cleaned)
            
        df['completed_intervals'] = df['completed_intervals'].apply(clean_intervals)
        
        # 데이터 호환성 체크 (initial_completion_date, last_completed_date)
        if 'initial_completion_date' not in df.columns:
            df['initial_completion_date'] = None
            mask = df['completed_intervals'].str.contains('0')
            df.loc[mask, 'initial_completion_date'] = pd.to_datetime(df.loc[mask, 'start_date']).dt.date
        if 'last_completed_date' not in df.columns:
            df['last_completed_date'] = None
            
        # 💡 [업데이트] 메모(memo) 컬럼이 없으면 추가
        if 'memo' not in df.columns:
            df['memo'] = ""
            
        df['initial_completion_date'] = pd.to_datetime(df['initial_completion_date']).dt.date.astype('object')
        df['last_completed_date'] = pd.to_datetime(df['last_completed_date']).dt.date.astype('object')
        df['memo'] = df['memo'].fillna("") # 빈칸 처리
            
        return df
    return pd.DataFrame(columns=['subject', 'topic', 'start_date', 'initial_completion_date', 'last_completed_date', 'completed_intervals', 'memo'])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

# 페이지 설정
st.set_page_config(page_title="감성 기말고사 플래너", layout="wide")

# --- 주아(Jua)체 폰트 적용 (CSS 주입) ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');

.stCheckbox label p {
    font-family: 'Jua', sans-serif !important;
    font-weight: 400 !important;
    font-size: 18px !important; 
    color: #222 !important;
}
/* 메모 입력창 폰트 설정 */
div[data-baseweb="input"] input {
    font-family: 'Jua', sans-serif !important;
    font-size: 15px !important;
}
</style>
""", unsafe_allow_html=True)

if 'df' not in st.session_state:
    st.session_state.df = load_data()

# --- 타임머신 기준 날짜 설정 ---
KST = timezone(timedelta(hours=9))
real_today = datetime.now(KST).date()

if 'view_date' not in st.session_state:
    st.session_state.view_date = real_today

def set_today():
    st.session_state.view_date = real_today

view_date = st.session_state.view_date

# --- 사이드바: 타임머신 및 추가 ---
with st.sidebar:
    st.header("🗓️ 날짜 이동")
    st.date_input("조회할 날짜", key='view_date')
    st.button("🌟 오늘로 돌아오기", on_click=set_today)
    st.divider()

    st.header("📝 새 계획 추가")
    with st.form("add_form", clear_on_submit=True):
        sub = st.text_input("과목명")
        top = st.text_input("학습 내용")
        date = st.date_input("학습 시작일", view_date)
        submitted = st.form_submit_button("추가하기")
        
        if submitted and sub and top:
            new_data = {'subject': sub, 'topic': top, 'start_date': date, 'initial_completion_date': None, 'last_completed_date': None, 'completed_intervals': "", 'memo': ""}
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
            save_data(st.session_state.df)
            st.rerun()

# --- 상단 다이어리 헤더 UI ---
date_str = view_date.strftime("%Y.%m.%d %a").upper()
exam_date = datetime(2026, 7, 1).date()
d_day = (exam_date - view_date).days
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

# --- 메인 화면 로직: 할 일 목록 생성 ---
todays_tasks = []

for idx, row in st.session_state.df.iterrows():
    start_date = row['start_date']
    completed_list = str(row['completed_intervals']).split(',') if pd.notna(row['completed_intervals']) and row['completed_intervals'] != '' else []
    
    # 1. '조회 중인 날짜'에 완료된 항목
    last_comp_date = pd.to_datetime(row['last_completed_date']).date() if pd.notna(row['last_completed_date']) else None
    if last_comp_date == view_date and len(completed_list) > 0:
        just_completed_interval = completed_list[-1]
        
        if just_completed_interval == '0':
            label = f"{start_date.month}/{start_date.day} 계획 • 최초"
        else:
            base_date = row['initial_completion_date'] if pd.notna(row['initial_completion_date']) else start_date
            label = f"{base_date.month}/{base_date.day} 완료 • {just_completed_interval}일차"
            
        todays_tasks.append({
            'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': just_completed_interval,
            'label': label, 'status': 'complete', 'memo': row['memo']
        })

    # 2. 미완료 항목 (다음 복습 단계)
    next_interval = None
    for interval in REVIEW_INTERVALS:
        if str(interval) not in completed_list:
            next_interval = interval
            break 
            
    if next_interval is not None:
        if next_interval == 0:
            target_date = start_date
            date_label = f"{start_date.month}/{start_date.day} 계획"
            interval_text = "최초"
        else:
            base_date = row['initial_completion_date'] if pd.notna(row['initial_completion_date']) else start_date
            target_date = base_date + timedelta(days=next_interval)
            date_label = f"{base_date.month}/{base_date.day} 완료"
            interval_text = f"{next_interval}일차"
            
        if target_date <= view_date:
            if target_date < view_date:
                days_late = (view_date - target_date).days
                label = f"<span style='color:#ff4b4b;'>⚠️ {days_late}일 지연</span> ({date_label} • {interval_text})"
            else:
                label = f"{date_label} • {interval_text}"
                
            todays_tasks.append({
                'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': str(next_interval),
                'label': label, 'status': 'incomplete', 'memo': row['memo']
            })

# --- 레이아웃 구성 ---
col1, col2 = st.columns([1.2, 0.8])

with col1:
    if not todays_tasks:
        st.write("🎉 오늘은 예정되거나 밀린 일정이 없습니다. 수고하셨어요!")
        done_count = 1; total_count = 1
    else:
        total_count = len(todays_tasks)
        done_count = sum(1 for task in todays_tasks if task['status'] == 'complete')
        
        tasks_by_subject = {}
        for task in todays_tasks:
            tasks_by_subject.setdefault(task['subject'], []).append(task)
            
        for subject, tasks in tasks_by_subject.items():
            st.markdown(f"<h4 style='font-family: \"Jua\", sans-serif; font-weight: normal; color: #444; border-left: 4px solid #aaa; padding-left: 10px; margin-top: 20px;'>{subject}</h4>", unsafe_allow_html=True)
            
            for task in tasks:
                idx = task['id']
                if task['status'] == 'incomplete':
                    is_done = st.checkbox(f"{task['topic']}", key=f"task_{idx}_{task['interval']}")
                    st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-top: -30px; margin-left: 30px; font-size: 15px; color: #666;'>{task['label']}</div>", unsafe_allow_html=True)
                    
                    # 💡 [업데이트] 메모 입력창
                    memo_val = st.text_input("📝 한 줄 메모", value=task['memo'], key=f"memo_{idx}", placeholder="오늘 공부한 핵심 내용을 적어보세요!")
                    if memo_val != st.session_state.df.loc[idx, 'memo']:
                        st.session_state.df.loc[idx, 'memo'] = memo_val
                        save_data(st.session_state.df)
                    st.write("") 
                    
                    if is_done:
                        current_completed = str(st.session_state.df.loc[idx, 'completed_intervals'])
                        new_val = task['interval'] if current_completed in ('', 'nan') else f"{current_completed},{task['interval']}".strip(',')
                        st.session_state.df.loc[idx, 'completed_intervals'] = new_val
                        st.session_state.df.loc[idx, 'last_completed_date'] = view_date
                        if task['interval'] == '0':
                            st.session_state.df.loc[idx, 'initial_completion_date'] = view_date
                        save_data(st.session_state.df)
                        st.rerun()
                else:
                    st.markdown(f"<div style='font-family: \"Jua\", sans-serif; font-size: 18px; color: #bbb;'><del>✅ {task['topic']}</del></div>", unsafe_allow_html=True)
                    if task['memo']:
                        st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #999; font-style: italic;'>└ 기록: {task['memo']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #bbb;'>{task['label']} 완료! 🎉</div>", unsafe_allow_html=True)
                    st.write("")

with col2:
    st.markdown("<div style='margin-top: 40px;'></div>", unsafe_allow_html=True)
    not_done_count = total_count - done_count
    chart_data = pd.DataFrame({'상태': ['완료', '미완료'], '개수': [done_count, not_done_count]})
    fig = px.pie(chart_data, values='개수', names='상태', color='상태', color_discrete_map={'완료':'#8BC34A', '미완료':'#EEEEEE'}, hole=0.6)
    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      annotations=[dict(text=f"{int((done_count/total_count)*100)}%", x=0.5, y=0.5, font_size=30, showarrow=False, font=dict(family='Jua, sans-serif', color='#444'))])
    st.plotly_chart(fig, use_container_width=True)

# --- 하단 관리 메뉴 ---
st.divider()
with st.expander("📂 전체 데이터 관리"):
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
    if st.button("수정사항 저장"):
        st.session_state.df = edited_df
        save_data(st.session_state.df)
        st.rerun()
