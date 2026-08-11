import streamlit as st
from datetime import datetime, timedelta
from PIL import Image
from streamlit_autorefresh import st_autorefresh
from baza import (
    init_db, osvezi_termine, formatiraj_datum, generisi_datume,
    generisi_slotove_za_dan, get_usluge, proveri_slotove_za_uslugu,
    rezervisi_slotove, otkazi_termin, naplati_termin,
    get_unique_clients_count_for_date, get_unique_clients_count_next_7_days,
    get_earnings_breakdown_for_date, get_monthly_earnings_breakdown,
    get_yearly_earnings_breakdown, get_connection
)

# ============================================================
# PODEŠAVANJE STRANICE & OPŠTI STILOVI
# ============================================================

st.set_page_config(
    page_title="Kod Kubanca",
    page_icon="✂️",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #1e1e1e;
    color: white;
}
.stMarkdown p, h1, h2, h3, h4 {
    color: white !important;
}

/* Opšte pravilo za glavna dugmad van tabele */
.stButton > button {
    background-color: #2b2b2b;
    color: #d4af37;
    border: 2px solid #d4af37;
    border-radius: 8px;
    font-weight: 600;
}
.stButton > button:hover {
    background-color: #d4af37;
    color: black;
}

div[data-baseweb="input"], div[data-baseweb="select"] {
    background-color: #2b2b2b;
}
input {
    color: white !important;
    background-color: #2b2b2b !important;
}
[data-testid="stDateInput"] * {
    color: white !important;
}
div[data-testid="stMetric"] {
    background-color: #2b2b2b;
    border: 2px solid #d4af37;
    padding: 15px;
    border-radius: 15px;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# LOGO SLIKA NA VRHU
# ============================================================
try:
    image = Image.open('IMG-c75b1bbded411581450ad9e3374dbc68-V.jpg')
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(image, use_container_width=True)
except Exception:
    pass

# ============================================================
# INICIJALIZACIJA & SESSION STATE
# ============================================================

init_db()
osvezi_termine()

st_autorefresh(interval=10000, key="auto_refresh")

if "izabrana_usluga" not in st.session_state:
    st.session_state["izabrana_usluga"] = None
if "izabrani_termin" not in st.session_state:
    st.session_state["izabrani_termin"] = None
if "booking_success" not in st.session_state:
    st.session_state["booking_success"] = False
if "booking_details" not in st.session_state:
    st.session_state["booking_details"] = None
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False
if "admin_password" not in st.session_state:
    st.session_state["admin_password"] = "admin123"

# ============================================================
# KLIJENTSKE POGLED FUNKCIJE
# ============================================================

def prikazi_usluge():
    usluge = get_usluge()
    st.write("### 💈 Korak 1: Odaberite uslugu")
    st.write("---")
    kolone = st.columns(2)

    for i, usluga in enumerate(usluge):
        ime_usluge, cena, trajanje = usluga
        with kolone[i % 2]:
            st.markdown(f"**{ime_usluge}**")
            st.caption(f"{trajanje} min • {cena} din")
            if st.button("Izaberi", key=f"usluga_{i}", use_container_width=True):
                st.session_state["izabrana_usluga"] = {"ime": ime_usluge, "cena": cena, "trajanje": trajanje}
                st.session_state["izabrani_termin"] = None
                st.rerun()
            st.write("---")

def prikazi_slotove(datum):
    datum_str = datum.strftime("%Y-%m-%d")
    generisi_slotove_za_dan(datum)

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT vreme, ime FROM rezervacije WHERE datum=? ORDER BY vreme", (datum_str,))
    slotovi = c.fetchall()
    conn.close()

    st.write("### ⏰ Korak 2: Odaberite vreme")

    for i in range(0, len(slotovi), 3):
        kolone = st.columns(3)
        for j in range(3):
            index = i + j
            if index >= len(slotovi): continue
            vreme, ime = slotovi[index]

            with kolone[j]:
                if "13:00" <= vreme < "14:00":
                    st.button("🚫 PAUZA", disabled=True, use_container_width=True, key=f"pauza_{datum_str}_{vreme}")
                elif ime is not None:
                    st.button(f"🔴 {vreme}", disabled=True, use_container_width=True, key=f"zauzet_{datum_str}_{vreme}")
                else:
                    if st.button(f"🟢 {vreme}", key=f"slobodan_{datum_str}_{vreme}", use_container_width=True):
                        st.session_state["izabrani_termin"] = vreme
                        st.rerun()

# ============================================================
# ADMIN FUNKCIJE
# ============================================================

def admin_rucno_zakazi():
    with st.expander("➕ Ručno zakazivanje", expanded=False):
        with st.form("admin_zakazi_form"):
            ime = st.text_input("Ime i prezime *")
            telefon = st.text_input("Telefon *")
            datum = st.date_input("Datum", value=datetime.now().date(), min_value=datetime.now().date())

            usluge = get_usluge()
            opcije = [f"{u[0]} ({u[2]} min, {u[1]} din)" for u in usluge]
            izabrana = st.selectbox("Usluga", opcije)

            index = opcije.index(izabrana)
            usluga_ime, usluga_cena, usluga_trajanje = usluge[index][0], usluge[index][1], usluge[index][2]

            generisi_slotove_za_dan(datum)

            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT vreme FROM rezervacije WHERE datum=? AND ime IS NULL ORDER BY vreme", (datum.strftime("%Y-%m-%d"),))
            slobodni = [r[0] for r in c.fetchall()]
            conn.close()

            vreme = st.selectbox("Termin", slobodni) if slobodni else None
            if not slobodni:
                st.warning("Nema slobodnih termina.")

            potvrdi = st.form_submit_button("✅ Zakaži", use_container_width=True)

            if potvrdi:
                if not ime.strip() or not telefon.strip():
                    st.warning("⚠️ Popunite ime i telefon.")
                elif vreme is None:
                    st.error("Nema slobodnog termina.")
                else:
                    slotovi = proveri_slotove_za_uslugu(datum, vreme, usluga_trajanje)
                    if slotovi is None:
                        st.error("❌ Nema dovoljno uzastopnih slobodnih slotova.")
                    else:
                        if rezervisi_slotove(datum, slotovi, ime, telefon, usluga_ime, usluga_cena):
                            st.success("✅ Termin je uspešno zakazan.")
                            st.rerun()
                        else:
                            st.error("❌ Termin više nije slobodan.")

import pandas as pd

def prikaz_nedeljnog_kalendara():
    st.subheader("📅 Nedeljni pregled (7 dana)")
    
    danas = datetime.now().date()
    dani = [danas + timedelta(days=i) for i in range(7)]
    
    for d in dani:
        generisi_slotove_za_dan(d)
        
    conn = get_connection()
    c = conn.cursor()
    
    datum_od = dani[0].strftime("%Y-%m-%d")
    datum_do = dani[-1].strftime("%Y-%m-%d")
    
    c.execute("""
        SELECT id, datum, vreme, ime, telefon, usluga, cena, status, payment_method 
        FROM rezervacije 
        WHERE datum BETWEEN ? AND ? 
        ORDER BY vreme ASC, datum ASC
    """, (datum_od, datum_do))
    
    sve_rezervacije = c.fetchall()
    conn.close()
    
    mapa_slotova = {}
    sve_satnice = sorted(list(set(r[2] for r in sve_rezervacije)))
    
    for r in sve_rezervacije:
        mapa_slotova[(r[2], r[1])] = {
            "id": r[0], "ime": r[3], "telefon": r[4], 
            "usluga": r[5], "cena": r[6], "status": r[7], "payment_method": r[8]
        }

    # Pravljenje prave matrice podataka za stabilan prikaz
    zaglavlja = ["Sat"] + [d.strftime('%a %d.%m.') for d in dani]
    matrica = []

    for vreme in sve_satnice:
        red = [vreme]
        for d in dani:
            datum_str = d.strftime("%Y-%m-%d")
            slot = mapa_slotova.get((vreme, datum_str))
            
            if "13:00" <= vreme < "14:00":
                red.append("🚫 Pauza")
            elif slot and slot["ime"]:
                status_icon = "🟢" if slot["status"] == "naplacen" else "🔴"
                prvo_ime = slot["ime"].split()[0]
                red.append(f"{status_icon} {prvo_ime}")
            else:
                red.append("⚪ Slobodno")
        matrica.append(red)

    # DataFrame drži tabelu uvek u jednom komadu bez vertikalnog slaganja
    df = pd.DataFrame(matrica, columns=zaglavlja)
    
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        height=400
    )

    # Brze akcije / upravljanje odabranim terminom ispod tabele
    st.markdown("---")
    st.caption("💡 *Izaberite datum i vreme ispod za detalje ili zakazivanje:*")
    
    col_d, col_v = st.columns(2)
    with col_d:
        izabrani_d = st.selectbox("Datum za izmenu", dani, format_func=lambda x: x.strftime('%a %d.%m.'))
    with col_v:
        izabrano_v = st.selectbox("Satnica", sve_satnice)
        
    datum_str_sel = izabrani_d.strftime("%Y-%m-%d")
    slot_sel = mapa_slotova.get((izabrano_v, datum_str_sel))
    
    if slot_sel and slot_sel["ime"]:
        st.info(f"👤 **{slot_sel['ime']}** | 📞 {slot_sel['telefon']} | ✂️ {slot_sel['usluga']} ({slot_sel['cena']} din)")
        if slot_sel["status"] == "zakazan":
            c1, c2 = st.columns(2)
            with c1:
                if st.button("❌ Otkaži termin", key="admin_otk"):
                    otkazi_termin([slot_sel['id']])
                    st.rerun()
            with c2:
                nacin = st.radio("Način plaćanja", ["Keš", "Kartica"], horizontal=True, key="admin_nac")
                if st.button("💰 Naplati", key="admin_nap"):
                    naplati_termin([slot_sel['id']], nacin)
                    st.rerun()

# ============================================================
# GLAVNI TABOVI
# ============================================================

tab1, tab2 = st.tabs(["📅 Zakazivanje", "🔑 Admin Panel"])

# TAB 1 - KLIJENT
with tab1:
    if st.session_state["booking_success"]:
        detalji = st.session_state["booking_details"]
        st.success("✅ Uspešno ste zakazali termin!")
        st.markdown(f"""
        <div style="background-color:#2b2b2b; padding:20px; border-radius:15px; border:2px solid #d4af37; margin-top:15px;">
        <h2 style="color:#d4af37 !important;">✂️ Termin je zakazan</h2>
        <p><b>Klijent:</b> {detalji["ime"]}</p>
        <p><b>Usluga:</b> {detalji["usluga"]}</p>
        <p><b>Datum:</b> {formatiraj_datum(detalji["datum"])}</p>
        <p><b>Vreme:</b> {detalji["vreme"]}</p>
        <p><b>Trajanje:</b> {detalji["trajanje"]} min</p>
        <p><b>Cena:</b> {detalji["cena"]} din</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("📅 Zakaži novi termin", use_container_width=True):
            st.session_state["booking_success"] = False
            st.session_state["izabrana_usluga"] = None
            st.session_state["izabrani_termin"] = None
            st.rerun()
    else:
        datumi = generisi_datume()
        datum = st.selectbox("📅 Datum", datumi, format_func=formatiraj_datum, key="klijent_datum")
        st.info(f"📅 Termini za {formatiraj_datum(datum)}")

        prikazi_usluge()

        if st.session_state["izabrana_usluga"] is not None:
            prikazi_slotove(datum)

        if st.session_state["izabrani_termin"] is not None:
            termin = st.session_state["izabrani_termin"]
            usluga = st.session_state["izabrana_usluga"]

            st.write("### 📝 Korak 3: Unesite podatke")
            slotovi = proveri_slotove_za_uslugu(datum, termin, usluga["trajanje"])

            if slotovi is None:
                st.error("❌ Ovaj termin više nije dostupan.")
                st.session_state["izabrani_termin"] = None
            else:
                with st.form("klijent_form"):
                    ime = st.text_input("Ime i prezime *")
                    telefon = st.text_input("Telefon *")

                    st.write(f"**Usluga:** {usluga['ime']}")
                    st.write(f"**Vreme:** {termin}")
                    st.write(f"**Trajanje:** {usluga['trajanje']} min")
                    st.write(f"**Cena:** {usluga['cena']} din")

                    potvrdi = st.form_submit_button("✅ Zakaži termin", use_container_width=True)

                    if potvrdi:
                        if not ime.strip() or not telefon.strip():
                            st.warning("⚠️ Popunite ime i telefon.")
                        else:
                            provereni_slotovi = proveri_slotove_za_uslugu(datum, termin, usluga["trajanje"])
                            if provereni_slotovi is None:
                                st.error("❌ Termin je u međuvremenu zauzet.")
                            else:
                                if rezervisi_slotove(datum, provereni_slotovi, ime, telefon, usluga["ime"], usluga["cena"]):
                                    st.session_state["booking_success"] = True
                                    st.session_state["booking_details"] = {
                                        "ime": ime, "usluga": usluga["ime"], "datum": datum,
                                        "vreme": termin, "trajanje": usluga["trajanje"], "cena": usluga["cena"]
                                    }
                                    st.session_state["izabrana_usluga"] = None
                                    st.session_state["izabrani_termin"] = None
                                    st.rerun()
                                else:
                                    st.error("❌ Greška pri rezervaciji.")

# TAB 2 - ADMIN
with tab2:
    if not st.session_state["admin_authenticated"]:
        st.write("### 🔐 Admin pristup")
        password = st.text_input("Unesite lozinku", type="password")
        if st.button("Potvrdi", use_container_width=True):
            if password == st.session_state["admin_password"]:
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Pogrešna lozinka.")
    else:
        st.success("🔓 Admin panel")

        with st.expander("🔑 Promeni lozinku"):
            old = st.text_input("Stara lozinka", type="password", key="old_pass")
            new = st.text_input("Nova lozinka", type="password", key="new_pass")
            confirm = st.text_input("Potvrdi novu lozinku", type="password", key="confirm_pass")

            if st.button("Promeni lozinku"):
                if old != st.session_state["admin_password"]:
                    st.error("Stara lozinka nije tačna.")
                elif not new or new != confirm:
                    st.error("Nove lozinke se ne poklapaju.")
                else:
                    st.session_state["admin_password"] = new
                    st.success("Lozinka je promenjena.")

        admin_rucno_zakazi()
        st.markdown("---")

        admin_datumi = generisi_datume()
        admin_datum = st.selectbox("Izaberite datum za finansijski pregled", admin_datumi, format_func=formatiraj_datum, index=0)

        # METRIKE
        st.markdown("---")
        st.write(f"## 📊 Finansijski pregled — {formatiraj_datum(admin_datum)}")

        m1, m2 = st.columns(2)
        with m1:
            st.metric("📅 Zakazano danas", get_unique_clients_count_for_date(admin_datum))
        with m2:
            st.metric("📆 Narednih 7 dana", get_unique_clients_count_next_7_days())

        p1, p2 = st.columns(2)
        with p1:
            uk, ke, ka = get_monthly_earnings_breakdown()
            st.write("### 💰 Mesečni pazar")
            st.write(f"Keš: **{ke:,.0f} din**")
            st.write(f"Kartica: **{ka:,.0f} din**")
            st.write(f"Ukupno: **{uk:,.0f} din**")

        with p2:
            uk, ke, ka = get_yearly_earnings_breakdown()
            st.write("### 📈 Godišnji pazar")
            st.write(f"Keš: **{ke:,.0f} din**")
            st.write(f"Kartica: **{ka:,.0f} din**")
            st.write(f"Ukupno: **{uk:,.0f} din**")

        # DNEVNI PAZAR
        st.markdown("---")
        ukupno, kes, kartica = get_earnings_breakdown_for_date(admin_datum)
        st.markdown(f"""
        <div style="background-color:#1e1e1e; padding:20px; border-radius:12px; border:2px solid #d4af37; text-align:center;">
        <h3 style="color:#d4af37 !important;">💵 Pazar za {formatiraj_datum(admin_datum)}</h3>
        <p>Keš: <b>{kes:,.0f} din</b> &nbsp;&nbsp;&nbsp; Kartica: <b>{kartica:,.0f} din</b></p>
        <h2 style="color:#d4af37 !important;">Ukupno: {ukupno:,.0f} din</h2>
        </div>
        """, unsafe_allow_html=True)

        # TABELA TERMINA - NEDELJNI MREŽASTI PRIKAZ
        st.markdown("---")
        prikaz_nedeljnog_kalendara()
