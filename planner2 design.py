import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import os
import io
from github import Github, UnknownObjectException

# --- 💡 [핵심] 깃허브 동기화 설정 ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
DB_FILE = "study_data.csv"
REVIEW_INTERVALS = [0, 1, 3, 7, 15]

def get_github_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(GITHUB_REPO)

def load_data():
    repo = get_github_repo()
    try:
        # 깃허브에서 파일 내용 가져오기
        file_content = repo.get_contents(DB_FILE)
        decoded_content = file_content.decoded_content.decode('utf-8')
        df = pd.read_csv(io.StringIO(decoded_content))
        
        # 데이터 정제 및 타입 변환
        df['start_date'] = pd.to_datetime(df['start_date']).dt.date
        
        def clean_intervals(val):
            if pd.isna(val) or str(val).lower() == 'nan' or str(val).strip() == '':
                return ''
            cleaned = []
            for x in str(val).split(','):
                try:
                    cleaned.append(str(int(float(x.strip()))))
                except ValueError: pass
            return ','.join(cleaned)
            
        df['completed_intervals'] = df['completed_intervals'].apply(clean_intervals)
        
        if 'history' not in df.columns: df['history'] = ""
        if 'memo' not in df.columns: df['memo'] = ""
        
        df['memo'] = df['memo'].fillna("")
        return df
        
    except UnknownObjectException:
        # 파일이 없으면 새 데이터프레임 생성
        return pd.DataFrame(columns=['subject', 'topic', 'start_date', 'completed_intervals', 'history', 'memo'])

def save_data(df):
    repo = get_github_repo()
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content = csv_buffer.getvalue()
    
    try:
        # 기존 파일 찾아서 업데이트
        contents = repo.get_contents(DB_FILE)
        repo.update_file(contents.path, "Update study_data.csv (Auto-sync)", content, contents.sha)
    except UnknownObjectException:
        # 파일이 없으면 새로 생성
        repo.create_file(DB_FILE, "Create study_data.csv (Initial)", content)

# --- 이하 디자인 및 로직 (기존과 동일) ---
st.set_page_config(page_title="감성 기말고사 플래너", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');
.stCheckbox label p { font-family: 'Jua', sans-serif !important; font-weight: 400 !important; font-size: 18px !important; color: #222 !important; }
div[data-baseweb="input"] input { font-family: 'Jua', sans-serif !important; font-size: 15px !important; }
</style>
""", unsafe_allow_html=True)

if 'df' not in st.session_state:
    st.session_state.df = load_data()

KST = timezone(timedelta(hours=9))
real_today = datetime.now(KST).date()
if 'view_date' not in st.session_state: st.session_state.view_date = real_today
def set_today(): st.session_state.view_date = real_today
view_date = st.session_state.view_date

# --- 사이드바 ---
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
            new_data = {'subject': sub, 'topic': top, 'start_date': date, 'completed_intervals': "", 'history': "", 'memo': ""}
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
            save_data(st.session_state.df)
            st.rerun()

# --- 헤더 ---
date_str = view_date.strftime("%Y.%m.%d %a").upper()
exam_date = datetime(2026, 7, 1).date()
d_day = (exam_date - view_date).days
header_html = f"""
<div style="border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end;">
    <div><div style="font-size: 14px; color: #777; font-family: 'Gothic A1', sans-serif;">Believe in myself.</div>
    <div style="font-size: 42px; font-weight: 800; font-family: 'Courier New', monospace; color: #222;">{date_str}</div></div>
    <div style="font-size: 48px; font-weight: 900; color: #ff4b4b; font-family: 'Courier New', monospace;">{"D-"+str(d_day) if d_day > 0 else "D-Day"}</div>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

# --- 메인 로직 ---
todays_tasks = []
for idx, row in st.session_state.df.iterrows():
    start_date = row['start_date']
    hist_str = str(row.get('history', ''))
    hist_dict = {k:v for k,v in [x.split(':') for x in hist_str.split(',') if ':' in x]}
    
    # 완료 항목
    completed_on_view = [k for k, v in hist_dict.items() if str(pd.to_datetime(v).date()) == str(view_date)]
    for comp_int in completed_on_view:
        if comp_int == '0': label = f"{start_date.month}/{start_date.day} 계획 • 최초"
        else:
            base_date = pd.to_datetime(hist_dict.get('0', start_date)).date()
            label = f"{base_date.month}/{base_date.day} 완료 • {comp_int}일차"
        todays_tasks.append({'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': comp_int, 'label': label, 'status': 'complete', 'memo': row['memo']})

    # 미완료 항목
    completed_before_or_on_view = [k for k, v in hist_dict.items() if pd.to_datetime(v).date() <= view_date]
    next_interval = None
    for interval in REVIEW_INTERVALS:
        if str(interval) not in completed_before_or_on_view:
            next_interval = interval
            break 
    if next_interval is not None:
        if next_interval == 0:
            target_date = start_date
            date_label = f"{start_date.month}/{start_date.day} 계획"
        else:
            base_date = pd.to_datetime(hist_dict.get('0', start_date)).date()
            target_date = base_date + timedelta(days=next_interval)
            date_label = f"{base_date.month}/{base_date.day} 완료"
        if target_date <= view_date:
            days_late = (view_date - target_date).days
            label = f"<span style='color:#ff4b4b;'>⚠️ {days_late}일 지연</span> ({date_label} • {next_interval}일차)" if days_late > 0 else f"{date_label} • {next_interval if next_interval > 0 else '최초'}일차"
            todays_tasks.append({'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': str(next_interval), 'label': label, 'status': 'incomplete', 'memo': row['memo']})

col1, col2 = st.columns([1.2, 0.8])
with col1:
    if not todays_tasks: st.write("🎉 일정이 없습니다!")
    else:
        total_count = len(todays_tasks); done_count = sum(1 for t in todays_tasks if t['status'] == 'complete')
        tasks_by_subject = {}
        for t in todays_tasks: tasks_by_subject.setdefault(t['subject'], []).append(t)
        for subject, tasks in tasks_by_subject.items():
            st.markdown(f"<h4 style='font-family: \"Jua\", sans-serif; border-left: 4px solid #aaa; padding-left: 10px;'>{subject}</h4>", unsafe_allow_html=True)
            for t in tasks:
                idx = t['id']
                if t['status'] == 'incomplete':
                    is_done = st.checkbox(f"{t['topic']}", key=f"t_{idx}_{t['interval']}")
                    st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-top: -30px; margin-left: 30px; font-size: 15px; color: #666;'>{t['label']}</div>", unsafe_allow_html=True)
                    memo_val = st.text_input("📝 메모", value=t['memo'], key=f"m_{idx}")
                    if memo_val != st.session_state.df.loc[idx, 'memo']:
                        st.session_state.df.loc[idx, 'memo'] = memo_val
                        save_data(st.session_state.df)
                    if is_done:
                        hist_str = str(st.session_state.df.loc[idx, 'history'])
                        hist_dict = {k:v for k,v in [x.split(':') for x in hist_str.split(',') if ':' in x]}
                        hist_dict[str(t['interval'])] = str(view_date)
                        st.session_state.df.loc[idx, 'history'] = ",".join([f"{k}:{v}" for k,v in hist_dict.items()])
                        st.session_state.df.loc[idx, 'completed_intervals'] = ",".join(hist_dict.keys())
                        save_data(st.session_state.df)
                        st.rerun()
                else:
                    st.markdown(f"<div style='font-family: \"Jua\", sans-serif; font-size: 18px; color: #bbb;'><del>✅ {t['topic']}</del></div>", unsafe_allow_html=True)
                    if t['memo']: st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #999;'>└ {t['memo']}</div>", unsafe_allow_html=True)
                    st.write("")

with col2:
    if 'total_count' in locals():
        fig = px.pie(values=[done_count, total_count-done_count], names=['완료', '미완료'], hole=0.6, color=['완료', '미완료'], color_discrete_map={'완료':'#8BC34A', '미완료':'#EEEEEE'})
        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', annotations=[dict(text=f"{int((done_count/total_count)*100)}%", x=0.5, y=0.5, font_size=30, showarrow=False, font=dict(family='Jua'))])
        st.plotly_chart(fig, use_container_width=True)

with st.expander("📂 전체 데이터 관리"):
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True, column_config={"initial_completion_date": None, "last_completed_date": None, "history": None})
    if st.button("수정사항 저장"):
        st.session_state.df = edited_df
        save_data(edited_df)
        st.rerun()
