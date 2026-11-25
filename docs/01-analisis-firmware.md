# 01 — Analisis Firmware V9.0.11P1N (catatan RE)

Catatan reverse-engineering firmware ZTE F670L `V9.0.11P1N*` (diekstrak dari
image `.bin` publik; partisi jffs2 pada offset `0x20000`, diekstrak dengan jefferson).

## Dekripsi `/etc/hardcodefile/*`

File di `etc/hardcodefile/` (webpri, dataprotocol, gponcfg, tr069, oss, wlan)
terenkripsi AES-CBC dengan key/IV yang diturunkan dari isi `/etc/hardcode`
(satu baris hex + suffix, mis. `...670lv9.0_normal`).

Derivasi (bedah `CspHardCodeParamGet` di `libhardcode.so`):

```
key_phrase = hardcode[5:21]  masing-masing byte +3  + hardcode[64:]
iv_phrase  = hardcode[7:39]  masing-masing byte +1
key        = SHA256(key_phrase)
iv         = SHA256(iv_phrase)[:16]
```

Format file: magic `01020304`, header 60 byte, lalu record 12 byte big-endian
`(plen, clen, has_next)` — blob `clen` byte didekripsi, dipotong `plen`.
(Kernel `AESCBCDecry`: key = SHA256(key_phrase), IV = SHA256(iv_phrase)[:16].)

Isi penting `webpri` (nilai default per build):

```
WebRepKey=nE%jA@5b
DefAESCBCKey=f680v9.0        DefAESCBCIV=ZTE%FN$GponNJ025
DefAdNewPass=Web@0063        DefUsNewPass=Web@0763
DefAdNewPass100=admin        DefAdNewPass187=Fs@1500879
...
```

`oss` berisi kredensial service: `TS_UPwd_198=Zte521`, `SSH_UserName_2009=admin`,
`SSH_PassWord_2009=Web@0063`, `TS_UPwd_39=Telkom135`, dll.

## Dekripsi `db_default_<region>_cfg.xml`

Struktur: header 0x48 (magic `01020304`, type 5) → payload AES-256-CBC
(key = SHA256("f680v9.0"), IV = SHA256("ZTE%FN$GponNJ025")[:16]) → menghasilkan
kontainer kedua (magic `01020304`, header 0x3c) → zlib @0x48 → XML.

XML memuat seluruh default DB, termasuk `DevAuthInfo` (admin/user) dan profil WAN.

## Formula password pabrik per-flag (`dbDefAuthUserInfoProduct`)

Saat factory reset, `cspd` membaca `/userconfig/flag_type` key `current` lalu
menjalankan dispatch `strcmp` terhadap daftar flag. Cabang-cabang yang
teridentifikasi (dari build P1N40B):

| flag | username | password |
|---|---|---|
| 66 | `superadmin` | `base64(SHA256("ZTE" + rosSN))` — rosSN = ASCII-hex(vendor tag 0x880) + hex(GPON SN tag 0x881) |
| 61 | admin | hex SN dari flash (`getSNfromTag`) |
| 68 | `Mega_gpon` | `Mega_<SN[4..]>` |
| 14/100/118/124/150/187 | admin | nilai `DefAdNewPass<flag>` dari webpri |
| lainnya | admin | `DefAdNewPass` (default `Web@0063`) |

Contoh perhitungan flag-66 untuk vendor `ZTEG` + SN hex `A1B2C3D4` (contoh fiktif):
`ConvertStr2AscII("ZTEG") = "5A544547"` → rosSN `5A544547A1B2C3D4` →
password = `base64(SHA256("ZTE5A544547A1B2C3D4"))`.

Catatan: pada unit yang sudah di-provision ACS, password admin TIDAK mengikuti
formula pabrik (di-set remote) — factory reset + timing adalah kuncinya.

## Model hak akses web (dmenu)

`isRightsMeeted(userRight, resourceRight)`:
`resourceRight == 0 → true`, else `(resourceRight * 0.5^(userRight-1)) % 2 >= 1`.
Dengan sesi user `Right=2`: halaman right 0/2/3 lolos, right 1 tidak.
Build IndiHome menghapus halaman `usrCfgMgr` (config backup), `usbbackup`,
`remoteMgr` (TR-069), dan `telnet` dari menu — fungsional backend masih ada
tapi tak terjangkau tanpa akses admin.
