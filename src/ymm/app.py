"""Streamlit sarmalayıcı (Faz 6) — çekirdeğe DOKUNMAZ, yalnız çağırır.

Çalıştırma: ``py -3.12 -m streamlit run src/ymm/app.py``

KVKK:
- Bu dosya `anthropic` IMPORT ETMEZ (bekçi: tests/test_kvkk.py); LLM'e giden
  tek yol yine `llm/gateway.py`'dir (rapor üretimi üzerinden).
- Mizan yükleme akışı CLI ile aynı ilkeyi izler: mizan_oku -> kimlik_ayir ->
  depo TEK fonksiyonda (`_mizan_yukle_akisi`) — maskeleme atlanamaz.
- Beyanname PDF'i önce ÖNİZLENİR; "Onayla ve kaydet" düğmesi olmadan DB'ye
  yazılmaz (R3 azaltımı, CLI --onayla akışının UI karşılığı).
- TASLAK damgası her sayfanın üstünde sabittir.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from ymm.cli import _BEYANNAME_PARSERLAR, _beyanname_donem_coz
from ymm.db.depo import Depo
from ymm.kontrol.motor import konfig_yukle, kontrolleri_calistir
from ymm.maskeleme.ayirici import kimlik_ayir
from ymm.maskeleme.dogrulayici import MaskeIhlali
from ymm.modeller import Donem
from ymm.parsers.mizan import mizan_oku
from ymm.rapor.uretici import DAMGA, taslak_uret, tutar_bicimle
from ymm.risk.seviye import GECERLI_SEVIYELER
from ymm.risk.tarayici import risk_konfig_yukle, riskleri_tara

# "Defter & Mühür" paleti: kağıt #F5F6F2, mürekkep #1C2B33, kurum petrol
# "Yaldızlı Defter" paleti (karanlık): derin mürekkep-yeşili zemin #0C1214,
# yaldız/altın varak #D4A853 (vurgu), fildişi metin #E6EBE8, kaşe kırmızısı
# #E05545 (yalnız damga + yüksek seviye). Eski defter-i kebir cilt estetiği.
_SEVIYE_RENKLERI = {
    "yuksek": "background-color: rgba(224,85,69,0.18); color: #FF9A8B; font-weight: 600",
    "orta": "background-color: rgba(212,168,83,0.16); color: #E8C77E; font-weight: 600",
    "dusuk": "background-color: rgba(255,255,255,0.06); color: #9FB0AA",
}

_OZEL_STIL = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

html, body, [data-testid="stAppViewContainer"] * {
    font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
}
/* Material ikon fontu global override'dan İSTİSNA — aksi halde ikon
   ligatürleri ("upload" vb.) düz İngilizce metin olarak görünür */
[data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded' !important;
}

/* NOT — Türkçe büyük harf: CSS `text-transform: uppercase` yerel ayar
   bilmez, "i" -> "I" (noktasız) üretir. Bu stilde text-transform
   KULLANILMAZ; büyük harf gereken metin Python tarafında yazılır. */

/* Atmosfer: derin mürekkep zemini üzerine köşelerden yaldız ve yeşil ışıma */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1100px 560px at 12% -8%, rgba(212,168,83,0.10), transparent 60%),
        radial-gradient(900px 520px at 95% -4%, rgba(63,110,98,0.14), transparent 55%),
        #0C1214;
}

/* Tipografi: Fraunces (yaldızlı cilt serif'i) başlıklarda */
h1, h2, h3 { font-family: 'Fraunces', Georgia, serif !important; }
h1 {
    font-size: 3rem; font-weight: 600; letter-spacing: -0.015em;
    background: linear-gradient(175deg, #F7E6B8 15%, #D2A557 85%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    padding-bottom: 0.1em;
}
h2, h3 { color: #E9DFC8 !important; font-weight: 600; }

/* Üst bant: eyebrow — teknik mono etiket, yaldız çizgiyle */
.ymm-eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem; font-weight: 600;
    letter-spacing: 0.28em;
    color: #D4A853; margin-bottom: -0.3rem;
    display: flex; align-items: center; gap: 0.9rem;
}
.ymm-eyebrow::after {
    content: ""; flex: 1; max-width: 180px; height: 1px;
    background: linear-gradient(90deg, rgba(212,168,83,0.6), transparent);
}

/* Streamlit kromu gizle (Deploy menüsü, araç çubukları) */
[data-testid="stToolbar"], #MainMenu, footer { visibility: hidden; }
[data-testid="stElementToolbar"] { display: none; }

/* İmza öğesi — TASLAK kaşesi: karanlıkta hafif ışıyan mühür */
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {
    background: rgba(224,85,69,0.05) !important;
    border: 2.5px dashed #E05545;
    outline: 1.5px solid rgba(224,85,69,0.75);
    outline-offset: 3px;
    border-radius: 4px;
    transform: rotate(-0.4deg);
    width: fit-content;
    padding: 0.15rem 1.1rem;
    box-shadow: 0 0 26px rgba(224,85,69,0.14);
}
[data-testid="stAlertContentWarning"],
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
    background: transparent !important;
}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) p {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 700; letter-spacing: 0.13em;
    font-size: 0.84rem;
    color: #FF8073 !important;
}

/* Dosya yükleyici: koyu cam kuyu + Türkçe metinler */
[data-testid="stFileUploaderDropzoneInstructions"] { display: none; }
[data-testid="stFileUploaderDropzone"] {
    border: 1.5px dashed rgba(212,168,83,0.35);
    border-radius: 12px;
    background: rgba(255,255,255,0.03);
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: rgba(212,168,83,0.65);
    background: rgba(212,168,83,0.05);
}
[data-testid="stFileUploaderDropzone"]::before {
    content: "Dosyayı buraya sürükleyin (sınır: 200 MB)";
    color: #8FA0A6; font-size: 0.85rem;
    margin-right: auto; padding-left: 0.4rem;
}
[data-testid="stFileUploaderDropzone"] button {
    border-radius: 9px; padding: 0.45rem 1rem;
    border: 1px solid rgba(212,168,83,0.5);
}
[data-testid="stFileUploaderDropzone"] button p { display: none; }
[data-testid="stFileUploaderDropzone"] button::after {
    content: "Dosya seç";
    font-size: 0.875rem; line-height: 1.4; font-weight: 600;
}

/* Metrik kartları: cam üzerine yaldız çerçeve, ışıyan mono rakamlar */
[data-testid="stMetric"] {
    background: linear-gradient(165deg, rgba(255,255,255,0.055), rgba(255,255,255,0.015));
    border: 1px solid rgba(212,168,83,0.22);
    border-radius: 14px;
    padding: 1rem 1.1rem 0.8rem 1.1rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.07), 0 10px 28px rgba(0,0,0,0.35);
    backdrop-filter: blur(6px);
    transition: transform 140ms ease, border-color 140ms ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    border-color: rgba(212,168,83,0.55);
}
[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600; color: #F3E7CC;
    text-shadow: 0 0 22px rgba(212,168,83,0.28);
}
[data-testid="stMetricLabel"] {
    font-size: 0.73rem; letter-spacing: 0.07em; color: #97A6A0;
}

/* Sekmeler: hap (pill) gezinme; aktif sekme yaldız dolgu.
   Streamlit 1.59: sekme DOM'u react-aria — [data-testid="stTab"] +
   [role="tablist"] (eski data-baseweb seçicileri eşleşmez). */
.stTabs [role="tablist"] {
    gap: 0.35rem; border-bottom: none !important;
    background: rgba(255,255,255,0.04);
    padding: 0.3rem; border-radius: 12px;
    width: fit-content;
    border: 1px solid rgba(255,255,255,0.06);
}
.stTabs [data-testid="stTab"] {
    font-weight: 600; letter-spacing: 0.02em;
    padding: 0.45rem 1.05rem !important;
    height: auto !important;
    border-radius: 9px;
    color: #AEBBB6;
}
.stTabs [data-testid="stTab"] p { margin: 0; line-height: 1.5; }
.stTabs [data-testid="stTab"][aria-selected="true"] {
    background: linear-gradient(180deg, #E2BC72, #C79A50);
}
.stTabs [data-testid="stTab"][aria-selected="true"] p,
.stTabs [data-testid="stTab"][aria-selected="true"] [data-testid="stMarkdownContainer"] * {
    color: #141B16 !important;
}

/* Düğmeler: yaldız çerçeve, hover'da dolgu */
.stButton > button, .stDownloadButton > button {
    border-radius: 9px; font-weight: 600; letter-spacing: 0.02em;
    border: 1px solid rgba(212,168,83,0.5);
    background: rgba(212,168,83,0.07);
    color: #E8C77E;
    transition: background 140ms ease, color 140ms ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: linear-gradient(180deg, #E2BC72, #C79A50);
    color: #141B16; border-color: transparent;
}

/* Kenar çubuğu: cilt kapağı — daha koyu, yaldız ayraçlı */
[data-testid="stSidebar"] {
    background: #10181B;
    border-right: 1px solid rgba(212,168,83,0.18);
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
    -webkit-text-fill-color: #E9DFC8; background: none;
    font-size: 1.15rem;
}

/* Tablolar */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(212,168,83,0.2); border-radius: 12px;
}

hr { border-color: rgba(212,168,83,0.15); }

@media (prefers-reduced-motion: reduce) {
    [data-testid="stMetric"], .stButton > button, .stDownloadButton > button {
        transition: none;
    }
    [data-testid="stMetric"]:hover { transform: none; }
    [data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { transform: none; }
}
</style>
"""


def _mizan_yukle_akisi(
    dosya_yolu: Path, harita_yolu: Path, mukellef: str, yil: int,
    veri_db: Path, kimlik_db: Path,
) -> int:
    """CLI `yukle mizan` ile birebir aynı akış — TEK fonksiyonda
    mizan_oku -> kimlik_ayir -> depo; maskesiz ara çıktı yok."""
    harita = yaml.safe_load(harita_yolu.read_text(encoding="utf-8"))
    satirlar = mizan_oku(dosya_yolu, harita)
    maskeli = kimlik_ayir(satirlar, kimlik_db)

    depo = Depo(veri_db)
    mukellef_id = depo.mukellef_bul(mukellef)
    if mukellef_id is None:
        mukellef_id = depo.mukellef_ekle(mukellef)

    donem_id = depo.donem_bul(mukellef_id, yil, "YILLIK")
    if donem_id is None:
        donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    else:
        depo.mizan_sil(donem_id)
    depo.mizan_yaz(donem_id, maskeli)
    return len(maskeli)


def _bulgu_df(bulgular) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Kaynak": b.kaynak,
                "Kontrol Kodu": b.kontrol_kodu,
                "Seviye": b.seviye,
                "Tutar Fark": "-" if b.tutar_fark is None else tutar_bicimle(b.tutar_fark),
                "Yüzde Fark": (
                    "-" if b.yuzde_fark is None
                    else "%" + f"{b.yuzde_fark:.2f}".replace(".", ",")
                ),
                "Detay": str(b.detay.get("aciklama") or b.detay.get("not") or "")[:70],
            }
            for b in bulgular
        ]
    )


def _seviyeli_stil(df: pd.DataFrame):
    return df.style.map(
        lambda seviye: _SEVIYE_RENKLERI.get(seviye, ""), subset=["Seviye"]
    )


st.set_page_config(
    page_title="YMM Tasdik Asistanı (TASLAK aracı)", page_icon="📕", layout="wide"
)
st.markdown(_OZEL_STIL, unsafe_allow_html=True)
st.markdown(
    # Büyük harf Python tarafında, doğru Türkçe karakterlerle (İ noktalı) —
    # CSS uppercase kullanılamaz (bkz. _OZEL_STIL nota).
    '<p class="ymm-eyebrow">YEMİNLİ MALİ MÜŞAVİR · TAM TASDİK DENETİMİ</p>',
    unsafe_allow_html=True,
)
st.title("Tasdik Asistanı")
st.warning(DAMGA)

with st.sidebar:
    st.header("Ayarlar")
    veri_db_yolu = Path(st.text_input("veri.db yolu", value="data/veri.db", key="veri_db"))
    kimlik_db_yolu = Path(
        st.text_input("kimlik.db yolu", value="data/kimlik.db", key="kimlik_db")
    )
    cikti_dizini = Path(st.text_input("Çıktı dizini", value="output", key="cikti"))
    mukellef = st.text_input("Mükellef takma kodu", value="MUK-001", key="mukellef")
    yil = int(st.number_input("Yıl", value=2025, step=1, key="yil"))

depo = Depo(veri_db_yolu)
mukellef_id = depo.mukellef_bul(mukellef)

ozet_tab, yukleme_tab, kontrol_tab, bulgular_tab, rapor_tab = st.tabs(
    ["🏠 Özet", "📥 Yükleme", "🔍 Kontrol & Tarama", "📋 Bulgular", "📄 Rapor"]
)

with ozet_tab:
    st.subheader(f"Durum — {mukellef} / {yil}")

    if mukellef_id is None:
        st.info("Henüz veri yok. Aşağıdaki adımlarla başlayın.")
    else:
        bulgular_ozet = depo.bulgular(mukellef_id, yil)
        seviye_sayilari = {s: 0 for s in GECERLI_SEVIYELER}
        for b in bulgular_ozet:
            seviye_sayilari[b.seviye] = seviye_sayilari.get(b.seviye, 0) + 1

        yillik_id = depo.donem_bul(mukellef_id, yil, "YILLIK")
        mizan_sayisi = len(depo.mizan_oku(yillik_id)) if yillik_id is not None else 0
        beyanname_sayisi = sum(
            len(depo.beyanname_oku(mukellef_id, tip, yil))
            for tip in _BEYANNAME_PARSERLAR
        )

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Mizan Satırı", str(mizan_sayisi))
        c2.metric("Beyanname", str(beyanname_sayisi))
        c3.metric("Toplam Bulgu", str(len(bulgular_ozet)))
        c4.metric("Yüksek", str(seviye_sayilari.get("yuksek", 0)))
        c5.metric("Orta", str(seviye_sayilari.get("orta", 0)))
        c6.metric("Düşük", str(seviye_sayilari.get("dusuk", 0)))

        if bulgular_ozet:
            st.bar_chart(
                pd.DataFrame(
                    {
                        "Bulgu Sayısı": [
                            seviye_sayilari.get("yuksek", 0),
                            seviye_sayilari.get("orta", 0),
                            seviye_sayilari.get("dusuk", 0),
                        ]
                    },
                    index=["yüksek", "orta", "düşük"],
                ),
                color="#D4A853",
            )

    st.divider()
    st.markdown(
        """
**Kullanım akışı (soldan sağa sekmeler):**

1. **📥 Yükleme** — mükellefin mizan Excel'ini yükleyin (kimlikler otomatik
   maskelenir); beyanname PDF'lerini *önizleyip onaylayarak* kaydedin.
2. **🔍 Kontrol & Tarama** — Modül A (mizan↔beyanname çapraz kontrol) ve
   Modül B (riskli hesap taraması) düğmelerine basın.
3. **📋 Bulgular** — tespit edilen farkları seviye renkleriyle inceleyin.
4. **📄 Rapor** — TASLAK damgalı Word taslağını üretip indirin.

Bu araç yalnız **TASLAK** üretir — nihai tasdik raporu ve tüm mesleki
görüşler YMM'ye aittir.
"""
    )

with yukleme_tab:
    st.subheader("Mizan (xlsx)")
    mizan_dosya = st.file_uploader("Mizan Excel dosyası", type=["xlsx"], key="mizan_up")
    if mizan_dosya is not None and st.button("Mizanı yükle", key="mizan_btn"):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(mizan_dosya.getvalue())
            tmp_yol = Path(tmp.name)
        try:
            sayi = _mizan_yukle_akisi(
                tmp_yol, Path("config/kolon_haritasi.yaml"),
                mukellef, yil, veri_db_yolu, kimlik_db_yolu,
            )
            st.success(f"{sayi} mizan satırı yüklendi (kimlikler maskelendi).")
        except Exception as exc:
            st.error(f"Mizan yüklenemedi: {exc}")
        finally:
            tmp_yol.unlink(missing_ok=True)

    st.divider()
    st.subheader("Beyanname (PDF) — önizle, sonra onayla")
    pdf_dosya = st.file_uploader("Beyanname PDF", type=["pdf"], key="pdf_up")
    tip = st.selectbox("Beyanname tipi", list(_BEYANNAME_PARSERLAR), key="tip")
    donem = st.text_input(
        "Dönem (KDV1/MUHSGK: YYYY-MM, GECICI: YYYY-QN, KV: YYYY)",
        value=f"{yil}-01", key="donem",
    )
    if pdf_dosya is not None and st.button("Önizle", key="onizle_btn"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_dosya.getvalue())
            tmp_yol = Path(tmp.name)
        try:
            alanlar = _BEYANNAME_PARSERLAR[tip](tmp_yol)
            st.session_state["beyanname_onizleme"] = {
                "tip": tip, "donem": donem, "alanlar": alanlar,
            }
        except ValueError as exc:
            st.error(f"PDF ayrıştırma hatası: {exc}")
        finally:
            tmp_yol.unlink(missing_ok=True)

    onizleme = st.session_state.get("beyanname_onizleme")
    if onizleme is not None:
        st.dataframe(
            pd.DataFrame(
                [
                    {"Alan": alan, "Değer": "BULUNAMADI" if deger is None else str(deger)}
                    for alan, deger in onizleme["alanlar"].items()
                ]
            )
        )
        st.caption("İncelendi mi? DB'ye yazmak için onaylayın (R3 azaltımı).")
        if st.button("Onayla ve kaydet", key="onay_btn"):
            try:
                o_yil, donem_tip, sira = _beyanname_donem_coz(
                    onizleme["tip"], onizleme["donem"]
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                m_id = depo.mukellef_bul(mukellef) or depo.mukellef_ekle(mukellef)
                d_id = depo.donem_bul(m_id, o_yil, donem_tip, sira=sira)
                if d_id is None:
                    d_id = depo.donem_ekle(m_id, Donem(yil=o_yil, tip=donem_tip, sira=sira))
                depo.beyanname_yaz(
                    d_id,
                    onizleme["tip"],
                    {a: str(d) for a, d in onizleme["alanlar"].items() if d is not None},
                )
                st.success(f"{onizleme['tip']} beyannamesi kaydedildi.")
                del st.session_state["beyanname_onizleme"]

with kontrol_tab:
    if mukellef_id is None:
        st.info("Önce mizan/beyanname yükleyin — mükellef kaydı bulunamadı.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Çapraz kontrolleri çalıştır (Modül A)", key="kontrol_btn"):
                try:
                    konfig = konfig_yukle(Path("config/kontrol_kurallari.yaml"))
                except ValueError as exc:
                    st.error(f"Kontrol konfig hatası: {exc}")
                else:
                    depo.bulgu_sil(mukellef_id, yil, "A")
                    bulgular = kontrolleri_calistir(depo, mukellef_id, yil, konfig)
                    depo.bulgu_yaz(bulgular)
                    st.success(f"Modül A tamam: {len(bulgular)} bulgu.")
        with col2:
            if st.button("Risk taraması çalıştır (Modül B)", key="tara_btn"):
                try:
                    konfig = risk_konfig_yukle(Path("config/risk_hesaplari.yaml"))
                except ValueError as exc:
                    st.error(f"Risk konfig hatası: {exc}")
                else:
                    depo.bulgu_sil(mukellef_id, yil, "B")
                    bulgular = riskleri_tara(depo, mukellef_id, yil, konfig)
                    depo.bulgu_yaz(bulgular)
                    st.success(f"Modül B tamam: {len(bulgular)} bulgu.")

with bulgular_tab:
    if mukellef_id is None:
        st.info("Mükellef kaydı bulunamadı.")
    else:
        seviye_filtre = st.selectbox(
            "Seviye filtresi", ["(tümü)", *GECERLI_SEVIYELER], key="seviye_filtre"
        )
        bulgular = depo.bulgular(mukellef_id, yil)
        if seviye_filtre != "(tümü)":
            bulgular = [b for b in bulgular if b.seviye == seviye_filtre]
        sira = {"yuksek": 0, "orta": 1, "dusuk": 2}
        bulgular = sorted(bulgular, key=lambda b: sira.get(b.seviye, 99))
        if not bulgular:
            st.info("Bulgu yok.")
        else:
            st.dataframe(_seviyeli_stil(_bulgu_df(bulgular)), width="stretch")

with rapor_tab:
    if os.environ.get("ANTHROPIC_API_KEY"):
        st.caption(
            "LLM redaksiyonu aktif ✓ — çıktı her zaman TASLAK damgalıdır."
        )
    else:
        st.info(
            "ANTHROPIC_API_KEY tanımlı değil — rapor üretimi çalışmaz. "
            "Anahtarı kendi terminalinizde `setx ANTHROPIC_API_KEY \"...\"` "
            "ile tanımlayıp uygulamayı yeniden başlatın."
        )
    if mukellef_id is None:
        st.info("Mükellef kaydı bulunamadı.")
    elif st.button("TASLAK rapor üret", key="rapor_btn"):
        try:
            yol = taslak_uret(
                depo, mukellef_id, yil,
                kimlik_db=kimlik_db_yolu, takma_kod=mukellef,
                cikti_dizini=cikti_dizini,
            )
        except MaskeIhlali as exc:
            st.error(f"KVKK sızıntı koruması devreye girdi: {exc}")
        except RuntimeError as exc:
            st.error(str(exc))
        else:
            st.success(f"Rapor taslağı üretildi: {yol}")
            st.download_button(
                "TASLAK raporu indir (docx)",
                data=yol.read_bytes(),
                file_name=yol.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="indir_btn",
            )
