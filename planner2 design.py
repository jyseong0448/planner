import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import os
import io
from github import Github, UnknownObjectException

# --- 설정 및 데이터 로드 ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
DB_FILE = "study_data.csv"
# 💡 [업데이트] 데이터베이스 컬럼 설정 추가
DB_COLUMNS = ['subject', 'topic', 'start_date', 'completed_intervals', 'memo', 'start_time', 'duration']
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
        
        # 날짜 타입 변환
        df['start_date'] = pd.to_datetime(df['start_date']).dt.date
        
        # 💡 [업데이트] 새로운 컬럼 처리: start_time, duration
        if 'start_time' not in df.columns: df['start_time'] = ""
        if 'duration' not in df.columns: df['duration'] = ""
        
        # 기존 정제 로직
        if 'history' not in df.columns: df['history'] = ""
        if 'memo' not in df.columns: df['memo'] = ""
        if 'completed_intervals' not in df.columns: df['completed_intervals'] = ""
        
        # 타입 강제 변환 및 빈칸 처리
        df['history'] = df['history'].fillna("").astype(str).replace('nan', '')
        df['memo'] = df['memo'].fillna("").astype(str).replace('nan', '')
        df['completed_intervals'] = df['completed_intervals'].fillna("").astype(str).replace('nan', '')
        df['start_time'] = df['start_time'].fillna("").astype(str).replace('nan', '')
        df['duration'] = df['duration'].fillna("0").astype(str).replace('nan', '0')
        
        # 0.0 방지 청소기
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
        
        return df
        
    except UnknownObjectException:
        # 💡 [업데이트] 파일이 없어서 새로 만들 때도 모든 칸을 유연한 object 타입으로 지정하고 새 컬럼 추가
        return pd.DataFrame(columns=DB_COLUMNS).astype(object)

def save_data(df):
    repo = get_github_repo()
    csv_buffer = io.StringIO()
    # 💡 [업데이트] 저장할 때 컬럼 순서 고정
    df[DB_COLUMNS].to_csv(csv_buffer, index=False)
    content = csv_buffer.getvalue()
    
    try:
        # 기존 파일 업데이트
        contents = repo.get_contents(DB_FILE)
        repo.update_file(contents.path, "Update study_data.csv (Auto-sync with Time Table)", content, contents.sha)
    except UnknownObjectException:
        # 새로 생성
        repo.create_file(DB_FILE, "Create study_data.csv (Initial)", content)

# 💡 [핵심] HTML/CSS 타임테이블 시각화 함수 추가
def draw_time_table(df, view_date):
    # 데이터를 view_date 기준으로 필터링하고 시작 시간 순으로 정렬
    # 💡 [핵심] 시작 시간과 소요 시간이 입력된 데이터만 사용
    filtered_df = df[(df['start_date'] == view_date) & (df['start_time'] != "") & (df['duration'] != "0")].copy()
    
    if filtered_df.empty:
        return "" # 데이터가 없으면 빈 문자열 반환
    
    # 시작 시간을 분 단위 정수로 변환하여 정렬
    def time_to_minutes(time_str):
        if not time_str or ':' not in time_str: return 0
        h, m = time_str.split(':')
        try: return int(h) * 60 + int(m)
        except ValueError: return 0
        
    filtered_df['start_minutes'] = filtered_df['start_time'].apply(time_to_minutes)
    filtered_df['duration_minutes'] = filtered_df['duration'].astype(int)
    sorted_df = filtered_df.sort_values(by='start_minutes')
    
    # 24시간 (0~23시) 그리드 생성
    hours_grids = [f"""
        <div style="flex: 1; border-right: 1px solid #eee; display: flex; flex-direction: column;">
            <div style="height: 15px; border-bottom: 1px solid #eee; text-align: center; font-size: 10px; color: #aaa;">{h}</div>
            <div style="flex: 1;"></div>
        </div>
    """ for h in range(24)]
    
    # 데이터를 순회하며 시간 블록 스타일 생성
    # 💡 [핵심] background-image: linear-gradient를 사용하여 분 단위 정확도 구현
    background_styles = []
    
    for idx, row in sorted_df.iterrows():
        start_min = row['start_minutes']
        duration_min = row['duration_minutes']
        end_min = start_min + duration_min
        
        start_hour = start_min // 60
        end_hour = end_min // 60
        
        start_percent = (start_min % 60) / 60 * 100
        end_percent = (end_min % 60) / 60 * 100
        
        # #00bcd4 파란색 형광펜 색상 (image_0.png와 유사)
        colored_color = "#00bcd4"
        transparent_color = "transparent"
        
        # 시간 단위로 쪼개서 각 <div>의 배경색 설정
        for h in range(24):
            if h < start_hour or h > end_hour:
                background_styles.setdefault(h, []).append(transparent_color)
            elif h == start_hour:
                background_styles.setdefault(h, []).append(f"{colored_color} {start_percent}%, {transparent_color} 0%")
            elif h == end_hour:
                background_styles.setdefault(h, []).append(f"{colored_color} {end_percent}%, {transparent_color} 0%")
            else: # 중간 시간대
                background_styles.setdefault(h, []).append(colored_color)
                
    # 각 시간 그리드에 배경색 적용
    for h in range(24):
        styles = background_styles.get(h, [])
        if styles:
            gradient_style = ",".join(styles)
            hours_grids[h] = hours_grids[h].replace(f"{transparent_color} 0%", f"linear-gradient(to right, {gradient_style})")

    # 전체 타임테이블 HTML 생성
    html = f"""
    <div style="font-family: 'Jua', sans-serif; margin-top: 30px;">
        <h5 style='color: #444; border-left: 4px solid #aaa; padding-left: 10px;'>오늘의 타임테이블</h5>
        <div style="display: flex; height: 150px; border: 1px solid #eee; border-radius: 5px; overflow: hidden; background-color: #fff;">
            {"".join(hours_grids)}
        </div>
    </div>
    """
    return html

# --- 디자인 및 로직 ---
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
        # 💡 [업데이트] 새 과목 추가 시 시작 시간/소요 시간 필드 추가
        date = st.date_input("학습 시작일", view_date)
        st_time = st.text_input("⌚ 시작 시간", placeholder="예: 14:30")
        du_time = st.number_input("⏱️ 소요 시간 (분)", value=0, step=15)
        submitted = st.form_submit_button("추가하기")
        if submitted and sub and top:
            new_data = {'subject': sub, 'topic': top, 'start_date': date, 'completed_intervals': "", 'history': "", 'memo': "", 'start_time': st_time, 'duration': str(du_time)}
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
        # 💡 [업데이트] 완료된 과제 데이터에 시작 시간/소요 시간 포함
        todays_tasks.append({'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': comp_int, 'label': label, 'status': 'complete', 'memo': row['memo'], 'start_time': row['start_time'], 'duration': row['duration']})

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
            # 💡 [업데이트] 미완료 과제 데이터에 시작 시간/소요 시간 포함
            todays_tasks.append({'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': str(next_interval), 'label': label, 'status': 'incomplete', 'memo': row['memo'], 'start_time': row['start_time'], 'duration': row['duration']})

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
                    
                    # 💡 [핵심 업데이트] 각 할 일 옆에 시작 시간과 소요 시간 입력 필드 추가
                    # 입력 즉시 데이터베이스 업데이트 및 저장
                    st_time_input = st.text_input("⌚ 시작 시간", value=t['start_time'], key=f"st_t_{idx}", placeholder="예: 14:30")
                    du_time_input = st.number_input("⏱️ 소요 시간 (분)", value=int(t['duration']) if t['duration'] else 0, key=f"du_t_{idx}", step=15)
                    
                    # 데이터 업데이트 로직
                    df_idx = st.session_state.df.index[idx]
                    if st_time_input != st.session_state.df.at[df_idx, 'start_time'] or str(du_time_input) != st.session_state.df.at[df_idx, 'duration']:
                        st.session_state.df.at[df_idx, 'start_time'] = st_time_input
                        st.session_state.df.at[df_idx, 'duration'] = str(du_time_input)
                        save_data(st.session_state.df)
                        # st.rerun() # 입력 즉시 리프레시하면 렉이 걸릴 수 있음

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
                    # 💡 [업데이트] 완료된 과제 옆에도 입력된 시간 표시
                    if t['start_time'] and t['duration'] != "0":
                        st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #aaa; font-style: italic;'>└ ⌚ {t['start_time']} • ⏱️ {t['duration']}분 소요</div>", unsafe_allow_html=True)
                    if t['memo']: st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #999;'>└ 기록: {t['memo']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #bbb;'>{t['label']} 완료! 🎉</div>", unsafe_allow_html=True)
                    st.write("")

with col2:
    if 'total_count' in locals():
        fig = px.pie(values=[done_count, total_count-done_count], names=['완료', '미완료'], hole=0.6, color=['완료', '미완료'], color_discrete_map={'완료':'#8BC34A', '미완료':'#EEEEEE'})
        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', annotations=[dict(text=f"{int((done_count/total_count)*100)}%", x=0.5, y=0.5, font_size=30, showarrow=False, font=dict(family='Jua'))])
        st.plotly_chart(fig, use_container_width=True)
        
        # 💡 [핵심 업데이트] 파이 차트 밑에 타임테이블 시각화 위젯 추가
        # 💡 [업데이트] 타임테이블 HTML 생성 및 렌더링
        time_table_html = draw_time_table(st.session_state.df, view_date)
        if time_table_html:
            st.markdown(time_table_html, unsafe_allow_html=True)

with st.expander("📂 전체 데이터 관리"):
    # 💡 [업데이트] 데이터 에디터에 새로운 컬럼 포함
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True, column_config={"initial_completion_date": None, "last_completed_date": None, "history": None})
    if st.button("수정사항 저장"):
        # 💡 [버그 픽스] 데이터 에디터에서 수정한 내용을 저장할 때도 문자열 변환 및 새로운 컬럼 처리 적용
        edited_df['history'] = edited_df['history'].fillna("").astype(str).replace('nan', '')
        edited_df['completed_intervals'] = edited_df['completed_intervals'].fillna("").astype(str).replace('nan', '')
        # 💡 [업데이트] 새로운 컬럼 처리
        edited_df['start_time'] = edited_df['start_time'].fillna("").astype(str).replace('nan', '')
        edited_df['duration'] = edited_df['duration'].fillna("0").astype(str).replace('nan', '0')
        
        for idx, row in edited_df.iterrows():
            old_hist_dict = {k:v for k,v in [x.split(':') for x in str(row.get('history', '')).split(',') if ':' in x]}
            raw_comps = str(row.get('completed_intervals', '')).split(',')
            new_comps = []
            for x in raw_comps:
                x = x.strip()
                if x:
                    try:
                        new_comps.append(str(int(float(x))))
                    except ValueError: pass
            
            new_hist = {}
            for comp in new_comps:
                if comp in old_hist_dict:
                    new_hist[comp] = old_hist_dict[comp]
                else:
                    new_hist[comp] = str(real_today)
            
            edited_df.loc[idx, 'history'] = ",".join([f"{k}:{v}" for k,v in new_hist.items()])
            edited_df.loc[idx, 'completed_intervals'] = ",".join(new_hist.keys())
            
        st.session_state.df = edited_df
        save_data(edited_df)
        st.rerun()

