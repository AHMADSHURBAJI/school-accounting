import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
import plotly.graph_objects as go

# ──────────────────────────────────────────────
st.set_page_config(
    page_title="النظام المحاسبي للمدرسة",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
* { font-family: 'Cairo', sans-serif !important; }
.main, .stApp, .stSidebar { direction: rtl; }
.metric-card {
    background: linear-gradient(135deg, #1e3c72, #2a5298);
    border-radius: 16px; padding: 20px; color: white;
    text-align: center; box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    margin-bottom: 16px;
}
.metric-card h2 { font-size: 1.8rem; font-weight: 700; margin: 0; }
.metric-card p  { margin: 4px 0 0; font-size: 0.9rem; opacity: 0.9; }
.metric-card.green  { background: linear-gradient(135deg, #11998e, #38ef7d); color: #1a1a1a; }
.metric-card.orange { background: linear-gradient(135deg, #f7971e, #ffd200); color: #1a1a1a; }
.metric-card.red    { background: linear-gradient(135deg, #cb2d3e, #ef473a); }
.metric-card.purple { background: linear-gradient(135deg, #6a3093, #a044ff); }
.metric-card.teal   { background: linear-gradient(135deg, #00b4db, #0083b0); }
.page-title {
    font-size: 1.6rem; font-weight: 700; color: #1e3c72;
    padding-bottom: 8px; border-bottom: 3px solid #2a5298; margin-bottom: 20px;
}
.salary-slip {
    border: 2px solid #1e3c72; border-radius: 12px;
    padding: 24px; background: #f8faff; direction: rtl;
}
.salary-slip h3 { color: #1e3c72; text-align: center; }
.slip-row {
    display: flex; justify-content: space-between;
    padding: 6px 0; border-bottom: 1px dashed #ccc;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# قاعدة البيانات
# ══════════════════════════════════════════════
DB = "school.db"

def get_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        acc_number TEXT, full_name TEXT NOT NULL,
        father_name TEXT, mother_name TEXT, grade TEXT, notes TEXT,
        tuition_fee REAL DEFAULT 0, books_fee REAL DEFAULT 0, supplies_fee REAL DEFAULT 0,
        pay1 REAL DEFAULT 0, pay2 REAL DEFAULT 0, pay3 REAL DEFAULT 0,
        pay4 REAL DEFAULT 0, pay5 REAL DEFAULT 0, pay6 REAL DEFAULT 0,
        pay7 REAL DEFAULT 0, pay8 REAL DEFAULT 0, pay9 REAL DEFAULT 0,
        pay10 REAL DEFAULT 0, created_at TEXT DEFAULT (date('now'))
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS treasury (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date TEXT NOT NULL, description TEXT, category TEXT,
        currency TEXT DEFAULT 'USD', income REAL DEFAULT 0, expense REAL DEFAULT 0,
        notes TEXT, created_at TEXT DEFAULT (datetime('now'))
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE, hourly_rate REAL DEFAULT 4,
        fixed_salary REAL DEFAULT 0, active INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS salary_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER, month TEXT, year INTEGER,
        hours REAL DEFAULT 0, hourly_rate REAL DEFAULT 4,
        fixed_salary REAL DEFAULT 0, total_due REAL DEFAULT 0,
        advances REAL DEFAULT 0, net_salary REAL DEFAULT 0,
        paid REAL DEFAULT 0, remaining REAL DEFAULT 0, notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS advances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER, advance_date TEXT,
        amount REAL DEFAULT 0, notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.commit()
    conn.close()

init_db()

def get_balance(currency='USD'):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(income),0)-COALESCE(SUM(expense),0) FROM treasury WHERE currency=?", (currency,))
    r = c.fetchone()[0]
    conn.close()
    return r or 0

def add_treasury(entry_date, description, category, currency, income, expense, notes=''):
    conn = get_conn()
    conn.execute(
        "INSERT INTO treasury (entry_date,description,category,currency,income,expense,notes) VALUES (?,?,?,?,?,?,?)",
        (entry_date, description, category, currency, income, expense, notes)
    )
    conn.commit()
    conn.close()

PAY_COLS = [f'pay{i}' for i in range(1,11)]
MONTHS = ['سبتمبر','أكتوبر','نوفمبر','ديسمبر','يناير','فبراير','مارس','أبريل','مايو','يونيو']
CATEGORIES = ['أقساط','رواتب','سلف معلمات','إيجار','كهرباء','مياه','قرطاسية',
              'صيانة','تنظيفات','بوفيه - مبيعات','بوفيه - مشتريات',
              'رحلة مدرسية','أرباح','تصريف عملة','مصاريف متنوعة','أخرى']

def calc_totals(df):
    for c in PAY_COLS:
        if c not in df.columns: df[c] = 0
    df['total_paid'] = df[PAY_COLS].sum(axis=1)
    df['pay_pct'] = df.apply(lambda r: (r['total_paid']/r['tuition_fee']*100) if r['tuition_fee'] else 0, axis=1).round(1)
    df['remaining'] = (df['tuition_fee'] - df['total_paid']).clip(lower=0)
    return df

# ══════════════════════════════════════════════
# الشريط الجانبي
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:16px 0 20px;'>
        <div style='font-size:2.5rem;'>🏫</div>
        <div style='font-size:1.1rem;font-weight:700;'>النظام المحاسبي</div>
        <div style='font-size:0.8rem;opacity:0.7;'>العام الدراسي 2025-2026</div>
    </div>
    """, unsafe_allow_html=True)
    page = st.radio("", ["🏠 لوحة التحكم", "👨‍🎓 الطلاب والأقساط",
                          "💰 الصندوق واليومية", "👩‍🏫 رواتب المعلمات"],
                    label_visibility="collapsed")
    st.markdown(f"<div style='font-size:0.75rem;opacity:0.5;text-align:center;margin-top:20px;'>📅 {datetime.now().strftime('%Y/%m/%d')}</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# صفحة 1 – لوحة التحكم
# ══════════════════════════════════════════════
if "لوحة التحكم" in page:
    st.markdown('<div class="page-title">🏠 لوحة التحكم</div>', unsafe_allow_html=True)

    bal_usd = get_balance('USD')
    bal_lbp = get_balance('LBP')

    conn = get_conn()
    try:
        df_s = pd.read_sql_query("SELECT * FROM students", conn)
        if not df_s.empty:
            df_s = calc_totals(df_s)
            total_paid = df_s['total_paid'].sum()
            total_rem  = df_s['remaining'].sum()
            n_stu      = len(df_s)
            paid_full  = (df_s['remaining']==0).sum()
        else:
            total_paid=total_rem=n_stu=paid_full=0
    except: total_paid=total_rem=n_stu=paid_full=0

    try:
        r2 = pd.read_sql_query("SELECT COALESCE(SUM(income),0) inc, COALESCE(SUM(expense),0) exp FROM treasury WHERE currency='USD'", conn).iloc[0]
        inc_usd, exp_usd = float(r2['inc']), float(r2['exp'])
    except: inc_usd=exp_usd=0
    conn.close()

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card green"><h2>${bal_usd:,.0f}</h2><p>💵 رصيد الصندوق $</p></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card teal"><h2>{bal_lbp:,.0f}</h2><p>🇱🇧 رصيد الصندوق ل.ل</p></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card orange"><h2>${total_paid:,.0f}</h2><p>✅ إجمالي الأقساط المحصّلة</p></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card red"><h2>${total_rem:,.0f}</h2><p>⏳ إجمالي الأقساط المتبقية</p></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c5,c6 = st.columns(2)
    with c5: st.markdown(f'<div class="metric-card" style="background:linear-gradient(135deg,#4e54c8,#8f94fb);color:white;"><h2>{n_stu}</h2><p>👨‍🎓 إجمالي الطلاب</p></div>', unsafe_allow_html=True)
    with c6:
        pct = (paid_full/n_stu*100) if n_stu else 0
        st.markdown(f'<div class="metric-card purple"><h2>{paid_full} ({pct:.0f}%)</h2><p>🏆 أتمّوا السداد</p></div>', unsafe_allow_html=True)

    st.markdown("---")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("📊 الأقساط: محصّل مقابل متبقٍّ")
        if total_paid>0 or total_rem>0:
            fig = go.Figure(data=[go.Pie(labels=['محصّل','متبقٍّ'], values=[total_paid,total_rem],
                                         hole=0.5, marker_colors=['#38ef7d','#ef473a'])])
            fig.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=260,
                              legend=dict(orientation='h',y=-0.15))
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("لا توجد بيانات أقساط بعد.")

    with col_g2:
        st.subheader("💹 حركة الصندوق بالدولار")
        conn = get_conn()
        try:
            df_t = pd.read_sql_query(
                "SELECT entry_date, SUM(income) inc, SUM(expense) exp FROM treasury WHERE currency='USD' GROUP BY entry_date ORDER BY entry_date DESC LIMIT 15",
                conn)
            conn.close()
            if not df_t.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(x=df_t['entry_date'], y=df_t['inc'], name='وارد', marker_color='#38ef7d'))
                fig2.add_trace(go.Bar(x=df_t['entry_date'], y=df_t['exp'], name='صادر', marker_color='#ef473a'))
                fig2.update_layout(barmode='group', height=260, margin=dict(t=0,b=0),
                                   legend=dict(orientation='h',y=-0.3))
                st.plotly_chart(fig2, use_container_width=True)
            else: st.info("لا توجد حركات بعد.")
        except:
            conn.close()
            st.info("لا توجد بيانات.")

    st.markdown("---")
    st.subheader("🕐 آخر العمليات")
    conn = get_conn()
    try:
        df_last = pd.read_sql_query(
            "SELECT entry_date,description,category,currency,income,expense FROM treasury ORDER BY id DESC LIMIT 10", conn)
        conn.close()
        if not df_last.empty:
            df_last.columns = ['التاريخ','البيان','التصنيف','العملة','وارد','صادر']
            st.dataframe(df_last, use_container_width=True, hide_index=True)
        else: st.info("لا توجد عمليات بعد.")
    except:
        conn.close()
        st.info("لا توجد بيانات.")

# ══════════════════════════════════════════════
# صفحة 2 – الطلاب والأقساط
# ══════════════════════════════════════════════
elif "الطلاب" in page:
    st.markdown('<div class="page-title">👨‍🎓 إدارة الطلاب والأقساط</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 قائمة الطلاب", "➕ إضافة طالب", "💳 تسجيل دفعة"])

    with tab1:
        conn = get_conn()
        df = pd.read_sql_query("SELECT * FROM students ORDER BY acc_number, full_name", conn)
        conn.close()
        if df.empty:
            st.info("لا يوجد طلاب. أضف من تبويب 'إضافة طالب'.")
        else:
            df = calc_totals(df)
            cs1,cs2 = st.columns([2,1])
            with cs1: search = st.text_input("🔍 بحث بالاسم أو الصف","")
            with cs2:
                grades = ["الكل"] + sorted([g for g in df['grade'].dropna().unique() if g])
                gf = st.selectbox("تصفية بالصف", grades)
            fdf = df.copy()
            if search:
                fdf = fdf[fdf['full_name'].str.contains(search,case=False,na=False)|
                          fdf['father_name'].str.contains(search,case=False,na=False)|
                          fdf['grade'].str.contains(search,case=False,na=False)]
            if gf!="الكل": fdf = fdf[fdf['grade']==gf]
            m1,m2,m3 = st.columns(3)
            m1.metric("عدد الطلاب", len(fdf))
            m2.metric("إجمالي محصّل", f"${fdf['total_paid'].sum():,.0f}")
            m3.metric("إجمالي متبقٍّ", f"${fdf['remaining'].sum():,.0f}")
            show_cols = ['acc_number','full_name','father_name','grade','tuition_fee','total_paid','pay_pct','remaining','notes']
            rename = {'acc_number':'رقم م.','full_name':'الاسم','father_name':'اسم الأب',
                      'grade':'الصف','tuition_fee':'القسط','total_paid':'المدفوع',
                      'pay_pct':'%','remaining':'المتبقي','notes':'ملاحظات'}
            sdf = fdf[[c for c in show_cols if c in fdf.columns]].rename(columns=rename)
            st.dataframe(sdf, use_container_width=True, hide_index=True)
            csv = fdf.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("⬇️ تحميل CSV", csv, "students.csv", "text/csv")

    with tab2:
        st.subheader("إضافة طالب جديد")
        with st.form("add_stu", clear_on_submit=True):
            c1,c2 = st.columns(2)
            with c1:
                acc = st.text_input("الرقم المحاسبي")
                fn  = st.text_input("الاسم والشهرة *")
                dad = st.text_input("اسم الأب")
                mom = st.text_input("اسم وشهرة الأم")
            with c2:
                gr  = st.text_input("الصف", placeholder="مثال: 5، kg1، L")
                tf  = st.number_input("قيمة القسط ($)", min_value=0.0, step=50.0)
                bf  = st.number_input("رسوم الكتب ($)", min_value=0.0, step=10.0)
                sf  = st.number_input("رسوم اللوازم ($)", min_value=0.0, step=10.0)
            nt = st.text_input("ملاحظات")
            if st.form_submit_button("✅ حفظ الطالب", type="primary", use_container_width=True):
                if not fn.strip():
                    st.error("يرجى إدخال اسم الطالب.")
                else:
                    conn = get_conn()
                    conn.execute("INSERT INTO students (acc_number,full_name,father_name,mother_name,grade,notes,tuition_fee,books_fee,supplies_fee) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (acc,fn.strip(),dad,mom,gr,nt,tf,bf,sf))
                    conn.commit(); conn.close()
                    st.success(f"✅ تمّ حفظ الطالب '{fn}'!"); st.balloons(); st.rerun()

    with tab3:
        st.subheader("تسجيل دفعة قسط")
        conn = get_conn()
        df_all = pd.read_sql_query("SELECT id,acc_number,full_name,grade,tuition_fee FROM students ORDER BY full_name", conn)
        conn.close()
        if df_all.empty:
            st.info("لا يوجد طلاب.")
        else:
            df_all['label'] = df_all.apply(lambda r: f"{r['full_name']} - {r['grade'] or '—'} (#{r['acc_number'] or r['id']})", axis=1)
            sel = st.selectbox("اختر الطالب", df_all['label'].tolist())
            srow = df_all[df_all['label']==sel].iloc[0]
            sid  = int(srow['id'])
            conn = get_conn()
            stu = calc_totals(pd.read_sql_query(f"SELECT * FROM students WHERE id={sid}", conn)).iloc[0]
            conn.close()
            m1,m2,m3 = st.columns(3)
            m1.metric("القسط الإجمالي", f"${stu['tuition_fee']:,.0f}")
            m2.metric("المدفوع", f"${stu['total_paid']:,.0f}")
            m3.metric("المتبقي", f"${stu['remaining']:,.0f}")
            pct = min(stu['pay_pct']/100, 1.0)
            st.progress(pct, text=f"نسبة السداد: {stu['pay_pct']:.1f}%")
            avail = [i for i in range(1,11) if stu[f'pay{i}']==0]
            if avail:
                with st.form("pay_f", clear_on_submit=True):
                    cf1,cf2,cf3 = st.columns(3)
                    with cf1: pn = st.selectbox("رقم الدفعة", avail)
                    with cf2: amt = st.number_input("المبلغ ($)", min_value=1.0, step=50.0)
                    with cf3: pd_date = st.date_input("التاريخ", value=date.today())
                    nt_p = st.text_input("ملاحظة")
                    if st.form_submit_button("💰 تسجيل الدفعة", type="primary", use_container_width=True):
                        conn = get_conn()
                        conn.execute(f"UPDATE students SET pay{pn}=? WHERE id=?", (amt, sid))
                        desc = f"قسط: {srow['full_name']} - دفعة {pn}"
                        conn.execute("INSERT INTO treasury (entry_date,description,category,currency,income,expense,notes) VALUES (?,?,?,?,?,?,?)",
                                     (str(pd_date), desc, 'أقساط', 'USD', amt, 0, nt_p))
                        conn.commit(); conn.close()
                        st.success(f"✅ دفعة {pn}: ${amt:,.0f} - تمّ الترحيل للصندوق!"); st.rerun()
            else:
                st.success("🎉 هذا الطالب أتمّ سداد جميع دفعاته!")
            rows = [{'الدفعة':f'دفعة {i}','المبلغ':f"${stu[f'pay{i}']:,.0f}" if stu[f'pay{i}'] else '—','الحالة':'✅' if stu[f'pay{i}'] else '⭕'} for i in range(1,11)]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════
# صفحة 3 – الصندوق واليومية
# ══════════════════════════════════════════════
elif "الصندوق" in page:
    st.markdown('<div class="page-title">💰 الصندوق واليومية المالية</div>', unsafe_allow_html=True)

    bal_usd = get_balance('USD')
    bal_lbp = get_balance('LBP')
    conn = get_conn()
    try:
        r = pd.read_sql_query("SELECT COALESCE(SUM(income),0) inc, COALESCE(SUM(expense),0) exp FROM treasury WHERE currency='USD'", conn).iloc[0]
        inc_usd, exp_usd = float(r['inc']), float(r['exp'])
    except: inc_usd=exp_usd=0
    conn.close()

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card green"><h2>${bal_usd:,.2f}</h2><p>💵 الرصيد الحالي $</p></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card teal"><h2>{bal_lbp:,.0f}</h2><p>🇱🇧 الرصيد ل.ل</p></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card orange"><h2>${inc_usd:,.0f}</h2><p>📥 إجمالي الوارد</p></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card red"><h2>${exp_usd:,.0f}</h2><p>📤 إجمالي الصادر</p></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    tab1,tab2,tab3 = st.tabs(["📒 كشف الحركة","➕ إدخال عملية","📊 تقارير"])

    with tab1:
        f1,f2,f3 = st.columns(3)
        with f1: cf = st.selectbox("العملة",["USD ($)","LBP (ل.ل)","الكل"])
        with f2: catf = st.selectbox("التصنيف",["الكل"]+CATEGORIES)
        with f3: srch = st.text_input("🔍 بحث","")
        conn = get_conn()
        q = "SELECT * FROM treasury WHERE 1=1"; params=[]
        if "USD" in cf: q+=" AND currency='USD'"
        elif "LBP" in cf: q+=" AND currency='LBP'"
        if catf!="الكل": q+=" AND category=?"; params.append(catf)
        if srch: q+=" AND description LIKE ?"; params.append(f"%{srch}%")
        q+=" ORDER BY entry_date DESC, id DESC"
        df_tr = pd.read_sql_query(q, conn, params=params)
        conn.close()
        if not df_tr.empty:
            disp = df_tr[['entry_date','description','category','currency','income','expense','notes']].copy()
            disp.columns=['التاريخ','البيان','التصنيف','العملة','وارد','صادر','ملاحظات']
            st.dataframe(disp, use_container_width=True, hide_index=True)
            st.download_button("⬇️ تحميل CSV", df_tr.to_csv(index=False,encoding='utf-8-sig'), "treasury.csv", "text/csv")
        else: st.info("لا توجد سجلات.")

    with tab2:
        st.subheader("إدخال عملية مالية")
        with st.form("treas_form", clear_on_submit=True):
            a1,a2 = st.columns(2)
            with a1:
                etype = st.radio("النوع",["📥 وارد","📤 صادر"], horizontal=True)
                cat   = st.selectbox("التصنيف", CATEGORIES)
                curr  = st.radio("العملة",["USD ($)","LBP (ل.ل)"], horizontal=True)
            with a2:
                amnt  = st.number_input("المبلغ", min_value=0.01, step=1.0, format="%.2f")
                edate = st.date_input("التاريخ", value=date.today())
                desc  = st.text_input("البيان *")
            nt_t = st.text_area("ملاحظات", height=68)
            if st.form_submit_button("✅ حفظ", type="primary", use_container_width=True):
                if not desc.strip(): st.error("يرجى إدخال البيان.")
                else:
                    cc = "USD" if "USD" in curr else "LBP"
                    inc = amnt if "وارد" in etype else 0
                    exp = amnt if "صادر" in etype else 0
                    add_treasury(str(edate), desc.strip(), cat, cc, inc, exp, nt_t)
                    st.success(f"✅ تمّ الحفظ! ({cat})"); st.rerun()

    with tab3:
        st.subheader("تقرير المصاريف حسب التصنيف")
        conn = get_conn()
        df_cat = pd.read_sql_query(
            "SELECT category, SUM(income) ti, SUM(expense) te FROM treasury WHERE currency='USD' GROUP BY category ORDER BY te DESC", conn)
        conn.close()
        if not df_cat.empty and df_cat['te'].sum()>0:
            fig = go.Figure(data=[go.Pie(labels=df_cat['category'], values=df_cat['te'], hole=0.4)])
            fig.update_layout(height=340, margin=dict(t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
            df_cat.columns=['التصنيف','إجمالي الوارد','إجمالي الصادر']
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
        else: st.info("لا توجد بيانات كافية.")

# ══════════════════════════════════════════════
# صفحة 4 – رواتب المعلمات
# ══════════════════════════════════════════════
elif "رواتب" in page:
    st.markdown('<div class="page-title">👩‍🏫 رواتب المعلمات</div>', unsafe_allow_html=True)
    tab1,tab2,tab3,tab4 = st.tabs(["📋 سجل الرواتب","➕ إدخال راتب","💸 سلفة","👤 المعلمات"])

    with tab1:
        conn = get_conn()
        df_t = pd.read_sql_query("SELECT * FROM teachers WHERE active=1 ORDER BY name", conn)
        conn.close()
        if df_t.empty:
            st.info("أضف معلمات من تبويب 'المعلمات'.")
        else:
            ft = st.selectbox("تصفية",["الكل"]+df_t['name'].tolist())
            conn = get_conn()
            if ft=="الكل":
                df_sal = pd.read_sql_query("SELECT sr.*,t.name tn FROM salary_records sr JOIN teachers t ON sr.teacher_id=t.id ORDER BY sr.year DESC,sr.id DESC", conn)
            else:
                tid2 = int(df_t[df_t['name']==ft]['id'].iloc[0])
                df_sal = pd.read_sql_query("SELECT sr.*,t.name tn FROM salary_records sr JOIN teachers t ON sr.teacher_id=t.id WHERE sr.teacher_id=? ORDER BY sr.year DESC,sr.id DESC", conn, params=(tid2,))
            conn.close()
            if not df_sal.empty:
                disp_sal = df_sal[['tn','month','year','hours','total_due','advances','net_salary','paid','remaining','notes']].copy()
                disp_sal.columns=['المعلمة','الشهر','السنة','الساعات','المستحق','السلف','الصافي','المدفوع','المتبقي','ملاحظات']
                st.dataframe(disp_sal, use_container_width=True, hide_index=True)
                st.markdown("---")
                st.subheader("🧾 قسيمة راتب")
                labels = df_sal.apply(lambda r: f"{r['tn']} - {r['month']} {r['year']}", axis=1).tolist()
                sel_r = st.selectbox("اختر السجل", labels)
                if sel_r:
                    rec = df_sal.iloc[labels.index(sel_r)]
                    st.markdown(f"""
                    <div class="salary-slip">
                        <h3>🧾 قسيمة راتب</h3><hr style="border-color:#1e3c72;">
                        <div class="slip-row"><span><b>المعلمة:</b></span><span>{rec.get('tn','')}</span></div>
                        <div class="slip-row"><span><b>الشهر:</b></span><span>{rec.get('month','')} {rec.get('year','')}</span></div>
                        <div class="slip-row"><span><b>عدد الساعات:</b></span><span>{rec.get('hours',0)}</span></div>
                        <div class="slip-row"><span><b>أجر الساعة:</b></span><span>${rec.get('hourly_rate',0):.2f}</span></div>
                        <div class="slip-row"><span><b>الراتب الثابت:</b></span><span>${rec.get('fixed_salary',0):.2f}</span></div>
                        <div class="slip-row" style="font-weight:700;"><span>إجمالي المستحقات:</span><span>${rec.get('total_due',0):.2f}</span></div>
                        <div class="slip-row" style="color:#dc3545;"><span>السلف:</span><span>- ${rec.get('advances',0):.2f}</span></div>
                        <div class="slip-row" style="font-weight:700;color:#155724;font-size:1.1rem;"><span>✅ صافي الراتب:</span><span>${rec.get('net_salary',0):.2f}</span></div>
                        <div class="slip-row"><span>المدفوع:</span><span>${rec.get('paid',0):.2f}</span></div>
                        <div class="slip-row" style="color:#dc3545;"><span>المتبقي:</span><span>${rec.get('remaining',0):.2f}</span></div>
                    </div>""", unsafe_allow_html=True)
            else: st.info("لا توجد سجلات رواتب.")

    with tab2:
        conn = get_conn()
        df_t2 = pd.read_sql_query("SELECT * FROM teachers WHERE active=1 ORDER BY name", conn)
        conn.close()
        if df_t2.empty:
            st.warning("أضف معلمات أولاً.")
        else:
            with st.form("sal_form", clear_on_submit=True):
                sc1,sc2 = st.columns(2)
                with sc1:
                    tname = st.selectbox("المعلمة", df_t2['name'].tolist())
                    month = st.selectbox("الشهر", MONTHS)
                    year  = st.number_input("السنة", value=2026, min_value=2024, max_value=2030)
                    sdate = st.date_input("تاريخ الصرف", value=date.today())
                with sc2:
                    hours = st.number_input("عدد الساعات", min_value=0.0, step=0.5)
                    hrate = st.number_input("أجر الساعة ($)", min_value=0.0, value=4.0, step=0.5)
                    fixed = st.number_input("الراتب الثابت ($)", min_value=0.0, step=10.0)
                    adv_v = st.number_input("السلف المقتطعة ($)", min_value=0.0, step=10.0)
                total_d = hours*hrate + fixed
                net_s   = max(total_d - adv_v, 0)
                paid_s  = st.number_input("المبلغ المدفوع الآن ($)", min_value=0.0, step=10.0, value=net_s)
                rem_s   = max(net_s - paid_s, 0)
                nt_s    = st.text_input("ملاحظات")
                st.markdown(f'<div style="background:#f0f4ff;padding:10px;border-radius:8px;direction:rtl;"><b>المستحق:</b> ${total_d:,.2f} | <b>بعد السلف:</b> ${net_s:,.2f} | <b>المتبقي:</b> ${rem_s:,.2f}</div>', unsafe_allow_html=True)
                if st.form_submit_button("✅ حفظ وترحيل للصندوق", type="primary", use_container_width=True):
                    tid3 = int(df_t2[df_t2['name']==tname]['id'].iloc[0])
                    conn = get_conn()
                    conn.execute("INSERT INTO salary_records (teacher_id,month,year,hours,hourly_rate,fixed_salary,total_due,advances,net_salary,paid,remaining,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (tid3,month,int(year),hours,hrate,fixed,total_d,adv_v,net_s,paid_s,rem_s,nt_s))
                    conn.commit(); conn.close()
                    if paid_s>0:
                        add_treasury(str(sdate), f"راتب: {tname} - {month} {year}", 'رواتب', 'USD', 0, paid_s, nt_s)
                    st.success(f"✅ تمّ حفظ راتب {tname}!"); st.rerun()

    with tab3:
        conn = get_conn()
        df_t3 = pd.read_sql_query("SELECT * FROM teachers WHERE active=1 ORDER BY name", conn)
        conn.close()
        if df_t3.empty: st.warning("أضف معلمات أولاً.")
        else:
            with st.form("adv_form", clear_on_submit=True):
                ta = st.selectbox("المعلمة", df_t3['name'].tolist())
                aa = st.number_input("مبلغ السلفة ($)", min_value=1.0, step=10.0)
                ad = st.date_input("التاريخ", value=date.today())
                an = st.text_input("ملاحظة")
                if st.form_submit_button("💸 تسجيل السلفة", type="primary", use_container_width=True):
                    tid4 = int(df_t3[df_t3['name']==ta]['id'].iloc[0])
                    conn = get_conn()
                    conn.execute("INSERT INTO advances (teacher_id,advance_date,amount,notes) VALUES (?,?,?,?)", (tid4,str(ad),aa,an))
                    conn.commit(); conn.close()
                    add_treasury(str(ad), f"سلفة: {ta}", 'سلف معلمات', 'USD', 0, aa, an)
                    st.success(f"✅ سلفة ${aa:,.0f} لـ {ta} - تمّ الترحيل!"); st.rerun()
            conn = get_conn()
            df_adv = pd.read_sql_query("SELECT t.name,a.advance_date,a.amount,a.notes FROM advances a JOIN teachers t ON a.teacher_id=t.id ORDER BY a.advance_date DESC", conn)
            conn.close()
            if not df_adv.empty:
                df_adv.columns=['المعلمة','التاريخ','المبلغ','ملاحظات']
                st.dataframe(df_adv, use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("إضافة معلمة")
        with st.form("add_t", clear_on_submit=True):
            tc1,tc2,tc3 = st.columns(3)
            with tc1: tn = st.text_input("الاسم *")
            with tc2: tr = st.number_input("أجر الساعة ($)", value=4.0, step=0.5)
            with tc3: tf2 = st.number_input("الراتب الثابت ($)", value=0.0, step=50.0)
            if st.form_submit_button("➕ إضافة", type="primary", use_container_width=True):
                if not tn.strip(): st.error("يرجى إدخال الاسم.")
                else:
                    conn = get_conn()
                    try:
                        conn.execute("INSERT INTO teachers (name,hourly_rate,fixed_salary) VALUES (?,?,?)", (tn.strip(),tr,tf2))
                        conn.commit(); st.success(f"✅ تمّ إضافة '{tn}'!")
                    except: st.warning("هذه المعلمة موجودة مسبقاً.")
                    finally: conn.close()
                    st.rerun()
        conn = get_conn()
        df_tall = pd.read_sql_query("SELECT name,hourly_rate,fixed_salary FROM teachers WHERE active=1 ORDER BY name", conn)
        conn.close()
        if not df_tall.empty:
            df_tall.columns=['الاسم','أجر الساعة','الراتب الثابت']
            st.dataframe(df_tall, use_container_width=True, hide_index=True)
