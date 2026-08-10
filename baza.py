import sqlite3
from datetime import datetime, timedelta

# ============================================================
# KONSTANTE & PODEŠAVANJA
# ============================================================

DB_FILE = "termini.db"
DB_VERSION = 2

def get_connection():
    return sqlite3.connect(DB_FILE)

# ============================================================
# INICIJALIZACIJA BAZA I STRUKTURE
# ============================================================

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    c.execute("SELECT value FROM app_meta WHERE key='db_version'")
    rezultat = c.fetchone()
    trenutna_verzija = int(rezultat[0]) if rezultat else 0

    if trenutna_verzija != DB_VERSION:
        c.execute("DROP TABLE IF EXISTS rezervacije")
        c.execute("DROP TABLE IF EXISTS cenovnik")

        c.execute("""
            CREATE TABLE rezervacije (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usluga TEXT,
                datum TEXT NOT NULL,
                vreme TEXT NOT NULL,
                ime TEXT,
                telefon TEXT,
                cena INTEGER,
                status TEXT DEFAULT 'zakazan',
                payment_method TEXT
            )
        """)

        c.execute("""
            CREATE TABLE cenovnik (
                usluga TEXT PRIMARY KEY,
                cena INTEGER NOT NULL,
                trajanje INTEGER NOT NULL
            )
        """)

        usluge = [
            ("💇 Šišanje", 1500, 60),
            ("💇 Šišanje + pranje kose", 1900, 60),
            ("💇 Šišanje + brada", 2000, 60),
            ("💇 Šišanje + brada + pranje kose", 2400, 90),
            ("💇 Šišanje + brada + pranje kose + obrve", 2800, 90),
            ("🧔 Brada (samo)", 1000, 30),
            ("✨ Obrve (samo)", 400, 30)
        ]

        c.executemany("""
            INSERT INTO cenovnik (usluga, cena, trajanje)
            VALUES (?, ?, ?)
        """, usluge)

        c.execute("""
            INSERT OR REPLACE INTO app_meta (key, value)
            VALUES ('db_version', ?)
        """, (str(DB_VERSION),))

    conn.commit()
    conn.close()

# ============================================================
# POMOĆNE FUNKCIJE ZA DATUME I SLOTOVE
# ============================================================

def formatiraj_datum(datum):
    if isinstance(datum, str):
        datum = datetime.strptime(datum, "%Y-%m-%d").date()
    return datum.strftime("%d.%m.%Y.")

def generisi_datume():
    danas = datetime.now().date()
    return [danas + timedelta(days=i) for i in range(7)]

def generisi_slotove_za_dan(datum):
    datum_str = datum if isinstance(datum, str) else datum.strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()

    trenutno = datetime.strptime("09:00", "%H:%M")
    kraj = datetime.strptime("20:00", "%H:%M")

    while trenutno < kraj:
        vreme = trenutno.strftime("%H:%M")

        if "13:00" <= vreme < "14:00":
            trenutno += timedelta(minutes=30)
            continue

        c.execute("SELECT id FROM rezervacije WHERE datum=? AND vreme=?", (datum_str, vreme))
        if not c.fetchone():
            c.execute("INSERT INTO rezervacije (datum, vreme, status) VALUES (?, ?, 'zakazan')", (datum_str, vreme))

        trenutno += timedelta(minutes=30)

    conn.commit()
    conn.close()

def osvezi_termine():
    for datum in generisi_datume():
        generisi_slotove_za_dan(datum)

def get_usluge():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT usluga, cena, trajanje FROM cenovnik ORDER BY trajanje ASC, cena ASC")
    usluge = c.fetchall()
    conn.close()
    return usluge

# ============================================================
# LOGIKA PROVERE I ZAKAZIVANJA TERMINA
# ============================================================

def proveri_slotove_za_uslugu(datum, vreme, trajanje):
    datum_str = datum if isinstance(datum, str) else datum.strftime("%Y-%m-%d")
    broj_slotova = trajanje // 30
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT vreme, ime FROM rezervacije WHERE datum=? ORDER BY vreme ASC", (datum_str,))
    svi_slotovi = c.fetchall()
    conn.close()

    start_index = None
    for i, (slot_vreme, ime) in enumerate(svi_slotovi):
        if slot_vreme == vreme:
            start_index = i
            break

    if start_index is None or (start_index + broj_slotova > len(svi_slotovi)):
        return None

    potrebni_slotovi = []
    prethodno_vreme = None

    for i in range(broj_slotova):
        slot_vreme, ime = svi_slotovi[start_index + i]
        if ime is not None:
            return None

        if prethodno_vreme:
            t1 = datetime.strptime(prethodno_vreme, "%H:%M")
            t2 = datetime.strptime(slot_vreme, "%H:%M")
            if int((t2 - t1).total_seconds() / 60) != 30:
                return None

        potrebni_slotovi.append(slot_vreme)
        prethodno_vreme = slot_vreme

    return potrebni_slotovi

def rezervisi_slotove(datum, slotovi, ime, telefon, usluga_ime, usluga_cena):
    datum_str = datum if isinstance(datum, str) else datum.strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()

    try:
        placeholders = ",".join(["?"] * len(slotovi))
        c.execute(f"SELECT id FROM rezervacije WHERE datum=? AND vreme IN ({placeholders}) AND ime IS NOT NULL", [datum_str] + slotovi)

        if c.fetchone():
            conn.rollback()
            conn.close()
            return False

        for index, slot_vreme in enumerate(slotovi):
            cena = usluga_cena if index == 0 else 0
            c.execute("""
                UPDATE rezervacije
                SET ime=?, telefon=?, usluga=?, cena=?, status='zakazan', payment_method=NULL
                WHERE datum=? AND vreme=?
            """, (ime.strip(), telefon.strip(), usluga_ime, cena, datum_str, slot_vreme))

        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.rollback()
        conn.close()
        return False

def otkazi_termin(rezervacija_ids):
    if not isinstance(rezervacija_ids, list):
        rezervacija_ids = [rezervacija_ids]

    conn = get_connection()
    c = conn.cursor()
    placeholders = ",".join(["?"] * len(rezervacija_ids))

    c.execute(f"""
        UPDATE rezervacije
        SET ime=NULL, telefon=NULL, usluga=NULL, cena=NULL, status='zakazan', payment_method=NULL
        WHERE id IN ({placeholders})
    """, rezervacija_ids)

    conn.commit()
    conn.close()

def naplati_termin(rezervacija_ids, payment_method):
    if not isinstance(rezervacija_ids, list):
        rezervacija_ids = [rezervacija_ids]

    conn = get_connection()
    c = conn.cursor()
    placeholders = ",".join(["?"] * len(rezervacija_ids))

    c.execute(f"""
        UPDATE rezervacije
        SET status='naplacen', payment_method=?
        WHERE id IN ({placeholders})
    """, [payment_method] + rezervacija_ids)

    conn.commit()
    conn.close()

# ============================================================
# METRIKE I PROMET
# ============================================================

def get_unique_clients_count_for_date(datum):
    conn = get_connection()
    c = conn.cursor()
    datum_str = datum.strftime("%Y-%m-%d") if not isinstance(datum, str) else datum
    c.execute("""
        SELECT COUNT(DISTINCT ime || '|' || telefon || '|' || usluga)
        FROM rezervacije
        WHERE datum=? AND ime IS NOT NULL AND status='zakazan'
    """, (datum_str,))
    rezultat = c.fetchone()
    conn.close()
    return rezultat[0] if rezultat else 0

def get_unique_clients_count_next_7_days():
    danas = datetime.now().date()
    kraj = danas + timedelta(days=6)
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(DISTINCT ime || '|' || telefon || '|' || usluga)
        FROM rezervacije
        WHERE datum BETWEEN ? AND ? AND ime IS NOT NULL AND status='zakazan'
    """, (danas.strftime("%Y-%m-%d"), kraj.strftime("%Y-%m-%d")))
    rezultat = c.fetchone()
    conn.close()
    return rezultat[0] if rezultat else 0

def get_earnings_breakdown_for_date(datum):
    datum_str = datum.strftime("%Y-%m-%d") if not isinstance(datum, str) else datum
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT payment_method, SUM(cena)
        FROM rezervacije
        WHERE datum=? AND status='naplacen' AND cena > 0
        GROUP BY payment_method
    """, (datum_str,))
    rezultati = c.fetchall()
    conn.close()

    kes, kartica = 0, 0
    for method, total in rezultati:
        if method == "Keš": kes = total or 0
        elif method == "Kartica": kartica = total or 0
    return kes + kartica, kes, kartica

def get_monthly_earnings_breakdown():
    danas = datetime.now().date()
    prvi_dan = danas.replace(day=1)
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT payment_method, SUM(cena)
        FROM rezervacije
        WHERE datum BETWEEN ? AND ? AND status='naplacen' AND cena > 0
        GROUP BY payment_method
    """, (prvi_dan.strftime("%Y-%m-%d"), danas.strftime("%Y-%m-%d")))
    rezultati = c.fetchall()
    conn.close()

    kes, kartica = 0, 0
    for method, total in rezultati:
        if method == "Keš": kes = total or 0
        elif method == "Kartica": kartica = total or 0
    return kes + kartica, kes, kartica

def get_yearly_earnings_breakdown():
    danas = datetime.now().date()
    prvi_dan = danas.replace(month=1, day=1)
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT payment_method, SUM(cena)
        FROM rezervacije
        WHERE datum BETWEEN ? AND ? AND status='naplacen' AND cena > 0
        GROUP BY payment_method
    """, (prvi_dan.strftime("%Y-%m-%d"), danas.strftime("%Y-%m-%d")))
    rezultati = c.fetchall()
    conn.close()

    kes, kartica = 0, 0
    for method, total in rezultati:
        if method == "Keš": kes = total or 0
        elif method == "Kartica": kartica = total or 0
    return kes + kartica, kes, kartica
