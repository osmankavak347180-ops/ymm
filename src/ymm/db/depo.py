"""Depo: veri.db için tüm SQL erişimi (repository)."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

from ymm.modeller import Bulgu, Donem, MizanSatiri

_SCHEMA_DOSYASI = Path(__file__).parent / "schema.sql"


class Depo:
    def __init__(self, veri_yolu: Path) -> None:
        self.baglanti = sqlite3.connect(veri_yolu)
        self.baglanti.execute("PRAGMA foreign_keys = ON")
        self.baglanti.executescript(_SCHEMA_DOSYASI.read_text(encoding="utf-8"))

    def mukellef_ekle(self, takma_kod: str) -> int:
        imlec = self.baglanti.execute(
            "INSERT INTO mukellef (takma_kod) VALUES (?)", (takma_kod,)
        )
        self.baglanti.commit()
        return imlec.lastrowid

    def mukellef_bul(self, takma_kod: str) -> int | None:
        """``takma_kod``'a sahip mükellefin id'sini döner; yoksa ``None``."""
        satir = self.baglanti.execute(
            "SELECT id FROM mukellef WHERE takma_kod = ?", (takma_kod,)
        ).fetchone()
        return satir[0] if satir is not None else None

    def donem_ekle(self, mukellef_id: int, donem: Donem) -> int:
        imlec = self.baglanti.execute(
            "INSERT INTO donem (mukellef_id, yil, tip, sira) VALUES (?, ?, ?, ?)",
            (mukellef_id, donem.yil, donem.tip, donem.sira),
        )
        self.baglanti.commit()
        return imlec.lastrowid

    def mizan_yaz(self, donem_id: int, satirlar: list[MizanSatiri]) -> None:
        self.baglanti.executemany(
            """
            INSERT INTO mizan (donem_id, hesap_kodu, hesap_adi, borc_toplam,
                                alacak_toplam, borc_bakiye, alacak_bakiye)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    donem_id,
                    satir.hesap_kodu,
                    satir.hesap_adi,
                    str(satir.borc_toplam),
                    str(satir.alacak_toplam),
                    str(satir.borc_bakiye),
                    str(satir.alacak_bakiye),
                )
                for satir in satirlar
            ],
        )
        self.baglanti.commit()

    def mizan_oku(self, donem_id: int) -> list[MizanSatiri]:
        satirlar = self.baglanti.execute(
            """
            SELECT hesap_kodu, hesap_adi, borc_toplam, alacak_toplam,
                   borc_bakiye, alacak_bakiye
            FROM mizan WHERE donem_id = ?
            ORDER BY id
            """,
            (donem_id,),
        ).fetchall()
        return [
            MizanSatiri(
                hesap_kodu=row[0],
                hesap_adi=row[1],
                borc_toplam=Decimal(row[2]),
                alacak_toplam=Decimal(row[3]),
                borc_bakiye=Decimal(row[4]),
                alacak_bakiye=Decimal(row[5]),
            )
            for row in satirlar
        ]

    def mizan_sil(self, donem_id: int) -> None:
        """``donem_id``'ye ait tüm mizan satırlarını siler (v1: yeniden yükleme
        akışında eski satırlar önce silinir, ardından yenisi ``mizan_yaz`` ile
        yazılır — bkz. CLI ``yukle mizan``)."""
        self.baglanti.execute("DELETE FROM mizan WHERE donem_id = ?", (donem_id,))
        self.baglanti.commit()

    def donem_bul(self, mukellef_id: int, yil: int, tip: str) -> int | None:
        """(mukellef_id, yil, tip) üçlüsüne uyan dönemin id'sini döner; yoksa None."""
        satir = self.baglanti.execute(
            "SELECT id FROM donem WHERE mukellef_id = ? AND yil = ? AND tip = ?",
            (mukellef_id, yil, tip),
        ).fetchone()
        return satir[0] if satir is not None else None

    def beyanname_oku_donemli(self, mukellef_id: int, tip: str, yil: int) -> list[dict]:
        """``beyanname_oku`` gibi ama her kayda ``donem_tip``/``sira`` da ekler
        (``kontrol.donem.yillik_kumulatif``'in beklediği biçim), sira'ya göre
        sıralı. Kayıt biçimi: ``{"donem_tip": ..., "sira": ..., "alanlar": {...}}``.
        """
        satirlar = self.baglanti.execute(
            """
            SELECT d.tip, d.sira, b.alanlar
            FROM beyanname b
            JOIN donem d ON d.id = b.donem_id
            WHERE d.mukellef_id = ? AND b.tip = ? AND d.yil = ?
            ORDER BY d.sira
            """,
            (mukellef_id, tip, yil),
        ).fetchall()
        return [
            {"donem_tip": satir[0], "sira": satir[1], "alanlar": json.loads(satir[2])}
            for satir in satirlar
        ]

    def beyanname_yaz(self, donem_id: int, tip: str, alanlar: dict) -> None:
        self.baglanti.execute(
            "INSERT INTO beyanname (donem_id, tip, alanlar) VALUES (?, ?, ?)",
            (donem_id, tip, json.dumps(alanlar, ensure_ascii=False, default=str)),
        )
        self.baglanti.commit()

    def beyanname_oku(self, mukellef_id: int, tip: str, yil: int) -> list[dict]:
        satirlar = self.baglanti.execute(
            """
            SELECT b.alanlar
            FROM beyanname b
            JOIN donem d ON d.id = b.donem_id
            WHERE d.mukellef_id = ? AND b.tip = ? AND d.yil = ?
            ORDER BY b.id
            """,
            (mukellef_id, tip, yil),
        ).fetchall()
        return [json.loads(row[0]) for row in satirlar]

    def bulgu_yaz(self, bulgular: list[Bulgu]) -> None:
        self.baglanti.executemany(
            """
            INSERT INTO bulgu (mukellef_id, yil, kaynak, kontrol_kodu, seviye,
                                tutar_fark, yuzde_fark, detay)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    bulgu.mukellef_id,
                    bulgu.yil,
                    bulgu.kaynak,
                    bulgu.kontrol_kodu,
                    bulgu.seviye,
                    None if bulgu.tutar_fark is None else str(bulgu.tutar_fark),
                    bulgu.yuzde_fark,
                    json.dumps(bulgu.detay, ensure_ascii=False, default=str),
                )
                for bulgu in bulgular
            ],
        )
        self.baglanti.commit()

    def bulgular(self, mukellef_id: int, yil: int) -> list[Bulgu]:
        satirlar = self.baglanti.execute(
            """
            SELECT kaynak, kontrol_kodu, seviye, tutar_fark, yuzde_fark, detay,
                   mukellef_id, yil
            FROM bulgu WHERE mukellef_id = ? AND yil = ?
            ORDER BY id
            """,
            (mukellef_id, yil),
        ).fetchall()
        return [
            Bulgu(
                kaynak=row[0],
                kontrol_kodu=row[1],
                seviye=row[2],
                tutar_fark=None if row[3] is None else Decimal(row[3]),
                yuzde_fark=row[4],
                detay=json.loads(row[5]),
                mukellef_id=row[6],
                yil=row[7],
            )
            for row in satirlar
        ]
