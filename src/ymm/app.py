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
from ymm.rapor.uretici import DAMGA, taslak_uret
from ymm.risk.seviye import GECERLI_SEVIYELER
from ymm.risk.tarayici import risk_konfig_yukle, riskleri_tara

_SEVIYE_RENKLERI = {
    "yuksek": "background-color: #ffb3b3",
    "orta": "background-color: #ffe0b3",
    "dusuk": "background-color: #e6e6e6",
}


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
                "Tutar Fark": "-" if b.tutar_fark is None else str(b.tutar_fark),
                "Yüzde Fark": "-" if b.yuzde_fark is None else f"{b.yuzde_fark:.2f}",
                "Detay": str(b.detay.get("aciklama") or b.detay.get("not") or "")[:70],
            }
            for b in bulgular
        ]
    )


def _seviyeli_stil(df: pd.DataFrame):
    return df.style.map(
        lambda seviye: _SEVIYE_RENKLERI.get(seviye, ""), subset=["Seviye"]
    )


st.set_page_config(page_title="YMM Tasdik Asistanı (TASLAK aracı)", layout="wide")
st.warning(DAMGA)
st.title("YMM Tam Tasdik Raporu Asistanı")

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

yukleme_tab, kontrol_tab, bulgular_tab, rapor_tab = st.tabs(
    ["📥 Yükleme", "🔍 Kontrol & Tarama", "📋 Bulgular", "📄 Rapor"]
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
    st.caption(
        "Rapor LLM redaksiyonu kullanır (ANTHROPIC_API_KEY gerekir); çıktı "
        "her zaman TASLAK damgalıdır."
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
