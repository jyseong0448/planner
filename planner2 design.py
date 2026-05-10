import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import os
import io
import re
from github import Github, UnknownObjectException

# --- 설정 및 데이터 로드 ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
DB_FILE = "study_data.csv"

# 컬럼 구조
DB_COLUMNS = ['subject', 'topic', 'start_date', 'completed_intervals', 'history', 'memo', 'planned_times']
REVIEW_INTERVALS = [0, 1, 3, 7, 15]

COLOR_PALETTE = ["#ffb3ba", "#ffdfba", "#ffffba", "#baffc9", "#bae1ff", "#e8baff", "#ffbaff", "#e2f0cb", "#ffc4c4", "#c4faf8"]

def get_github_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(GITHUB_REPO)

def load_data():
    repo = get_github_repo()
    try:
        file_content = repo.get_contents(DB_FILE)
        decoded_content = file_content.decoded_content.decode('utf-8')
        df = pd.read_csv(io.StringIO(decoded_content))
        
        # 💡 [버그 픽스] 날짜 변환 시 에러가 나면 빈칸 처리(coerce) 후 안전하게 date로 변경
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce').dt.date
        
        for col in DB_COLUMNS:
            if col not in df.columns: df[col] = ""
            df[col] = df[col].fillna("").astype(str).replace('nan', '')
            
        def clean_intervals(val):
            if not val: return ''
            cleaned = []
            for x in str(val).split(','):
                try: cleaned.append(str(int(float(x.strip()))))
                except ValueError: pass
            return ','.join(cleaned)
            
        df['completed_intervals'] = df['completed_intervals'].apply(clean_intervals)
        return df
        
    except UnknownObjectException:
        return pd.DataFrame(columns=DB_COLUMNS).astype(object)

def save_data(df):
    repo = get_github_repo()
    csv_buffer = io.StringIO()
    for col in DB_COLUMNS:
        if col not in df.columns: df[col] = ""
    df[DB_COLUMNS].to_csv(csv_buffer, index=False)
    content = csv_buffer.getvalue()
    
    try:
        contents = repo.get_contents(DB_FILE)
        repo.update_file(contents.path, "Update study_data.csv", content, contents.sha)
    except UnknownObjectException:
        repo.create_file(DB_FILE, "Create study_data.csv", content)

def draw_vertical_timetable(df, view_date):
    filtered_df = df[(df['start_date'] == view_date) & (df['planned_times'] != "")].copy()
    
    grid = [["" for _ in range(6)] for _ in range(24)]
    total_minutes = 0
    subject_colors = {}
    color_idx = 0
    
    for idx, row in filtered_df.iterrows():
        sub = row['subject']
        if sub not in subject_colors:
            subject_colors[sub] = COLOR_PALETTE[color_idx % len(COLOR_PALETTE)]
            color_idx += 1
            
        times_str = row['planned_times']
        blocks = times_str.split(',')
        for block in blocks:
            try:
                match = re.search(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', block)
                if not match: continue
                sh, sm, eh, em = map(int, match.groups())
                
                start_m = sh * 60 + sm
                end_m = eh * 60 + em
                if end_m <= start_m: end_m += 24 * 60
                
                total_minutes += (end_m - start_m)
                
                for m in range(start_m, end_m):
                    adj_m = m - 240
                    if adj_m < 0: adj_m += 24 * 60
                    if adj_m >= 24 * 60: continue
                    r = adj_m // 60
                    c = (adj_m % 60) // 10
                    grid[r][c] = subject_colors[sub]
            except: pass

    # 💡 [버그 픽스] 60분 칸 깨진 글씨 제거
    html = f"""
    <div style="font-family: 'Jua', sans-serif; background-color: #fff; padding: 15px; border-radius: 8px; border: 1px solid #ddd; max-width: 350px; margin: 0 auto;">
        <div style="text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 10px; letter-spacing: 2px;">TIMETABLE</div>
        <table style="width: 100%; border-collapse: collapse; text-align: center; font-size: 12px; color: #555;">
            <tr style="color: #aaa;">
                <th style="border: none; width: 15%;"></th>
                <th style="border-left: 1px solid #eee; font-weight: normal; padding-bottom: 5px;">10</th>
                <th style="border-left: 1px solid #eee; font-weight: normal; padding-bottom: 5px;">20</th>
                <th style="border-left: 1px solid #eee; font-weight: normal; padding-bottom: 5px;">30</th>
                <th style="border-left: 1px solid #eee; font-weight: normal; padding-bottom: 5px;">40</th>
                <th style="border-left: 1px solid #eee; font-weight: normal; padding-bottom: 5px;">50</th>
                <th style="border-left: 1px solid #eee; font-weight: normal; padding-bottom: 5px; border-right: 1px solid #ccc;">60</th>
            </tr>
    """
    
    hours_labels = list(range(4, 13)) + list(range(1, 13)) + list(range(1, 4))
    for r in range(24):
        html += f"<tr><td style='border-top: 1px solid #ccc; font-weight: bold; color: #333; padding: 3px 0;'>{hours_labels[r]}</td>"
        for c in range(6):
            bg_color = grid[r][c]
            html += f"<td style='border: 1px solid #ccc; border-right: none; height: 18px; background-color: {bg_color if bg_color else 'transparent'};'></td>"
        html = html[:-5] + " border-right: 1px solid #ccc;'></td></tr>"
        
    total_h = total_minutes // 60
    total_m = total_minutes % 60
    html += f"""
        </table>
        <div style="margin-top: 15px; font-weight: bold; font-size: 14px; text-align: left;">TOTAL TIME</div>
        <div style="border: 1px solid #ccc; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-family: 'Courier New', monospace; font-weight: bold; color: #333;">
            {total_h}H {total_m:02d}M
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; font-size: 12px;">
    """
    for sub, color in subject_colors.items():
        html += f"<div style='display: flex; align-items: center;'><div style='width: 12px; height: 12px; background-color: {color}; margin-right: 5px; border: 1px solid #ccc;'></div>{sub}</div>"
        
    html += "</div></div>"
    return html

st.set_page_config(page_title="감성 기말고사 플래너", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');
.stCheckbox label p { font-family: 'Jua', sans-serif !important; font-weight: 400 !important; font-size: 18px !important; color: #222 !important; }
div[data-baseweb="input"] input { font-family: 'Jua', sans-serif !important; font-size: 15px !important; }
/* 💡 시간 입력창 스타일 수정 */
div[data-baseweb="input"] { font-size: 18px !important; }
div[data-baseweb="input"] input { text-align: center !important; }
</style>
""", unsafe_allow_html=True)

if 'df' not in st.session_state:
    st.session_state.df = load_data()

KST = timezone(timedelta(hours=9))
real_today = datetime.now(KST).date()
if 'view_date' not in st.session_state: st.session_state.view_date = real_today
def set_today(): st.session_state.view_date = real_today
view_date = st.session_state.view_date

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
        
        # 💡 [입력 방식 개편] 시각 다이얼 기반 입력
        st.markdown("⏱️ 계획 시간 (시작 - 종료)")
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        with c1:
            st_h = st.number_input("시", value=9, min_value=0, max_value=23, key="st_h")
        with c2:
            st_m = st.number_input("분", value=0, min_value=0, max_value=59, step=10, key="st_m")
        with c3:
            en_h = st.number_input("시", value=10, min_value=0, max_value=23, key="en_h")
        with c4:
            en_m = st.number_input("분", value=0, min_value=0, max_value=59, step=10, key="en_m")
            
        submitted = st.form_submit_button("추가하기")
        if submitted and sub and top:
            # 💡 입력된 시/분을 형식에 맞춰 문자열로 변환
            p_times = f"{st_h:02d}:{st_m:02d}-{en_h:02d}:{en_m:02d}"
            new_data = {'subject': sub, 'topic': top, 'start_date': date, 'completed_intervals': "", 'history': "", 'memo': "", 'planned_times': p_times}
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
            save_data(st.session_state.df)
            st.rerun()

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

todays_tasks = []
for idx, row in st.session_state.df.iterrows():
    # 💡 [버그 픽스] 문자열을 확실하게 날짜 객체로 변환!
    start_ts = pd.to_datetime(row['start_date'], errors='coerce')
    start_date = start_ts.date() if pd.notna(start_ts) else real_today
    
    hist_str = str(row.get('history', ''))
    hist_dict = {k:v for k,v in [x.split(':') for x in hist_str.split(',') if ':' in x]}
    
    completed_on_view = [k for k, v in hist_dict.items() if str(pd.to_datetime(v).date()) == str(view_date)]
    for comp_int in completed_on_view:
        if comp_int == '0': label = f"{start_date.month}/{start_date.day} 계획 • 최초"
        else:
            base_date = pd.to_datetime(hist_dict.get('0', start_date)).date()
            label = f"{base_date.month}/{base_date.day} 완료 • {comp_int}일차"
        todays_tasks.append({'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': comp_int, 'label': label, 'status': 'complete', 'memo': row['memo'], 'planned_times': row['planned_times']})

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
            todays_tasks.append({'id': idx, 'subject': row['subject'], 'topic': row['topic'], 'interval': str(next_interval), 'label': label, 'status': 'incomplete', 'memo': row['memo'], 'planned_times': row['planned_times']})

col1, col2 = st.columns([1.3, 0.7])
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
                    
                    # 💡 [입력 방식 개편] Material Design 스타일 시간 입력
                    st.markdown("⏱️ 계획 시간 (시작 - 종료)")
                    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                    
                    # 💡 [디자인 연동] Hour 입력창 아래 시간 도장 배치
                    with c1:
                        st_h_input = st.number_input("시", value=9, min_value=0, max_value=23, key=f"st_h_{idx}")
                        st.markdown("<div style='text-align: center;'>🕒</div>", unsafe_allow_html=True)
                    # 💡 [디자인 연동] Minute 입력창 아래 텍스트 필드 배치
                    with c2:
                        st_m_input = st.number_input("분", value=0, min_value=0, max_value=59, step=10, key=f"st_m_{idx}")
                        st.markdown("<div style='text-align: center; font-size: 12px; color: #aaa;'>Minute</div>", unsafe_allow_html=True)
                    with c3:
                        en_h_input = st.number_input("시", value=10, min_value=0, max_value=23, key=f"en_h_{idx}")
                        st.markdown("<div style='text-align: center;'>🕒</div>", unsafe_allow_html=True)
                    with c4:
                        en_m_input = st.number_input("분", value=0, min_value=0, max_value=59, step=10, key=f"en_m_{idx}")
                        st.markdown("<div style='text-align: center; font-size: 12px; color: #aaa;'>Minute</div>", unsafe_allow_html=True)
                        
                    # 💡 입력된 시/분을 형식에 맞춰 문자열로 변환
                    p_times_input = f"{st_h_input:02d}:{st_m_input:02d}-{en_h_input:02d}:{en_m_input:02d}"
                    
                    memo_val = st.text_input("📝 메모", value=t['memo'], key=f"m_{idx}")
                        
                    if p_times_input != st.session_state.df.at[idx, 'planned_times'] or memo_val != st.session_state.df.loc[idx, 'memo']:
                        st.session_state.df.at[idx, 'planned_times'] = p_times_input
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
                    info_texts = []
                    if t['planned_times']: info_texts.append(f"⏱️ {t['planned_times']}")
                    if t['memo']: info_texts.append(f"📝 {t['memo']}")
                    if info_texts:
                        st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #aaa; font-style: italic;'>└ {' / '.join(info_texts)}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-family: \"Jua\", sans-serif; margin-left: 30px; font-size: 14px; color: #bbb;'>{t['label']} 완료! 🎉</div>", unsafe_allow_html=True)
                    st.write("")

with col2:
    if 'total_count' in locals():
        fig = px.pie(values=[done_count, total_count-done_count], names=['완료', '미완료'], hole=0.6, color=['완료', '미완료'], color_discrete_map={'완료':'#8BC34A', '미완료':'#EEEEEE'})
        fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', height=250, annotations=[dict(text=f"{int((done_count/total_count)*100)}%", x=0.5, y=0.5, font_size=30, showarrow=False, font=dict(family='Jua'))])
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(draw_vertical_timetable(st.session_state.df, view_date), unsafe_allow_html=True)

with st.expander("📂 전체 데이터 관리"):
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True, column_config={"initial_completion_date": None, "last_completed_date": None, "history": None})
    if st.button("수정사항 저장"):
        edited_df['history'] = edited_df['history'].fillna("").astype(str).replace('nan', '')
        edited_df['completed_intervals'] = edited_df['completed_intervals'].fillna("").astype(str).replace('nan', '')
        edited_df['planned_times'] = edited_df['planned_times'].fillna("").astype(str).replace('nan', '')
        
        for idx, row in edited_df.iterrows():
            old_hist_dict = {k:v for k,v in [x.split(':') for x in str(row.get('history', '')).split(',') if ':' in x]}
            raw_comps = str(row.get('completed_intervals', '')).split(',')
            new_comps = []
            for x in raw_comps:
                x = x.strip()
                if x:
                    try: new_comps.append(str(int(float(x))))
                    except ValueError: pass
            
            new_hist = {}
            for comp in new_comps:
                if comp in old_hist_dict: new_hist[comp] = old_hist_dict[comp]
                else: new_hist[comp] = str(real_today)
            
            edited_df.loc[idx, 'history'] = ",".join([f"{k}:{v}" for k,v in new_hist.items()])
            edited_df.loc[idx, 'completed_intervals'] = ",".join(new_hist.keys())
            
        st.session_state.df = edited_df
        save_data(edited_df)
        st.rerun()

