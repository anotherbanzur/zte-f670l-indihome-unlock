# ZTE ZXHN F670L — Factory/Telnet Unlock & ISP-ACS Control (IndiHome V9.0.11P1N-series)

Toolkit hasil reverse-engineering firmware ZTE F670L seri `V9.0.11P1N*` (IndiHome/Telkomsel)
untuk **mengelola router milik sendiri**: memulihkan akses superadmin, membuka telnet root
lewat gerbang factory mode (`/webFac`), dan mengambil kendali penuh atas TR-069 (ACS).

> **Disclaimer — gunakan hanya pada perangkat milik Anda sendiri.**
> Modifikasi ONT ISP dapat melanggar ketentuan layanan dan berisiko kehilangan
> provisioning (VoIP, firmware OTA). Seluruh risiko ditanggung pengguna.
> Terverifikasi pada firmware `V9.0.11P1N84A` (F670L, IndiHome/Telkomsel, 2024).

---

##  Tujuan utama toolkit

### 1. Memulihkan akses superadmin yang diambil alih ISP
Sejak IndiHome dikelola Telkomsel, password akun `admin` di ONT **di-randomize per-unit
oleh ACS (TR-069)**. Pemilik tidak bisa masuk sebagai superadmin, sehingga fitur seperti
bridge mode, port forwarding, dan DNS kustom tidak bisa diatur. Toolkit ini memulihkan
akses itu lewat **factory reset + pengujian kandidat password pabrik** secara otomatis.

### 2. Membuka telnet root lewat gerbang factory mode (`/webFac`)
Temuan kunci reverse-engineering ini: **gerbang `/webFac` melakukan otentikasi memakai
KREDENSIAL WEB ADMIN** (`IGD.AU1`), bukan kredensial terpisah. Artinya, begitu password
admin diketahui (mis. setelah factory reset), telnet root bisa dibuka kapan pun —
tanpa membongkar flash atau firmware.

### 3. Mengambil kendali atas TR-069 (ACS) agar perubahan ISP berhenti
ACS mengubah password admin secara periodik (teramati `PeriodicInformInterval ≈ 83268
detik ≈ 23 jam`) dan dapat menimpa konfigurasi. Toolkit ini menyediakan cara untuk
**mematikan TR-069** (URL → `127.0.0.1`, client off, periodic-inform off) sehingga
password dan konfigurasi yang Anda set menjadi permanen — dengan perintah pembalik
yang terdokumentasi bila suatu saat provisioning ISP dibutuhkan lagi.

---

##  Alur kerja end-to-end

```
                       ┌──────────────────────────────┐
                       │  Factory reset (tombol 10s)  │
                       └──────────────┬───────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │ reset_recover.cjs            │  ← uji kandidat password pabrik
                       │ login web admin sukses       │     (Telkomdso123, Web@0063, ...)
                       └──────────────┬───────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │ factory_unlock.py            │  ← handshake /webFac + CheckLoginAuth
                       │ kredensial telnet sementara  │     memakai KREDENSIAL WEB ADMIN
                       └──────────────┬───────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │ telnet port 23 (root shell)  │
                       │ telnet_session.py            │  ← jalankan sendcmd bebas
                       └──────────────┬───────────────┘
                                      ▼
              ┌────────────────────────┴───────────────────────┐
              ▼                                                ▼
   ┌─────────────────────────┐                   ┌────────────────────────────┐
   │ tr069_control.py        │                   │ sendcmd lainnya            │
   │ --disable-tr069         │                   │ ganti password, lihat DB,  │
   │ → password permanen     │                   │ WAN, dsb. (docs/03)        │
   └─────────────────────────┘                   └────────────────────────────┘

   (opsional, sepanjang proses)  syslog_listener.py  ← pantau log router real-time
```

---

##  Detail setiap service

### `scripts/factory_unlock.py` — Pembuka gerbang factory mode
- **Tujuan**: mengubah kredensial web admin menjadi **kredensial telnet root sementara**.
- **Input**: `--host` (default `192.168.1.1`), `--user`, `--password` (password **web** admin), `--verbose`.
- **Output**: baris `FactoryModeAuth.gch?user=XXXXXX&pass=YYYYYY` — kredensial login telnet,
  sekaligus menandakan daemon telnet di port 23 sudah aktif.
- **Cara kerja** (7 langkah, lihat `docs/02-webfac-protocol.md` untuk bedah lengkap):
  1. Reset sesi factory (`SendSq.gch`, harapkan HTTP 400)
  2. Minta mode factory (`RequestFactoryMode.gch`)
  3. Ambil challenge (`SendSq.gch?rand=N` → `newrand`)
  4. Turunkan key AES dari `KEY_POOL` (spesifik per-build firmware; dua pool dikenal,
     diuji otomatis bergantian)
  5. Kirim bukti MAC terenkripsi (`SendInfo.gch` — verifikasi `do_check_client`)
  6. Kirim `CheckLoginAuth.gch?version50&user=<admin>&pass=<password>` — **di sinilah
     kredensial web admin divalidasi**
  7. Elevasi `FactoryMode.gch?mode=2` → telnet aktif
- **Kapan dipakai**: setiap kali butuh shell root. Bisa diulang kapan pun selama
  password web admin diketahui.
- **Kegagalan umum**: `Auth=401` = password web salah; `SendInfo != 200` = pool firmware
  berbeda (tambahkan pool build Anda sendiri).

### `scripts/telnet_session.py` — Klien telnet root generik
- **Tujuan**: menjalankan perintah di shell root tanpa interaksi manual.
- **Input**: `--user`/`--password` (kredensial sementara dari `factory_unlock.py`),
  `--cmd` (boleh diulang untuk banyak perintah).
- **Cara kerja**: socket telnet mentah dengan pembersihan byte negosiasi IAC,
  login otomatis, eksekusi berurutan, output mentah ke stdout.
- **Contoh**:
  ```bash
  python scripts/telnet_session.py --user <tempuser> --password <temppass> \
      --cmd "sendcmd 1 DB p DevAuthInfo" \
      --cmd "sendcmd 1 DB p MgtServer"
  ```

### `scripts/tr069_control.py` — Kendali TR-069 (ACS) & password admin
- **Tujuan utama**: membuat akses superadmin **permanen** dengan menghentikan
  campur tangan ACS, atau membaliknya bila provisioning ISP dibutuhkan.
- **Mode-mode**:
  | Mode | Yang dilakukan | Efek |
  |---|---|---|
  | `--disable-tr069` | `MgtServer URL→127.0.0.1`, `Tr069Enable=0`, `PeriodicInformEnable=0`, `save` | ACS buta total; password & config Anda tidak pernah ditimpa; internet tetap jalan |
  | `--enable-tr069` | kembalikan URL ACS (`--acs-url`, default `acs.telkom.net:9090/web/tr069`) + enable | provisioning ISP masuk lagi (firmware OTA, VoIP) |
  | `--set-admin-pass` | `DevAuthInfo 0 Pass <baru>` + `save` | ganti password superadmin langsung dari root |
  | `--show` | tampilkan `MgtServer` + `DevAuthInfo` | inspeksi status |
- **Konsekuensi yang perlu dipahami**: dengan TR-069 mati, update firmware dan
  perubahan provisioning dari ISP tidak masuk otomatis. Ini pilihan sadar —
  pembaliknya satu perintah.
- **Catatan**: `WANC` (koneksi WAN) tidak disentuh — mematikan TR-069 **tidak**
  memutus internet.

### `scripts/syslog_listener.py` — Penyadap log router (monitoring)
- **Tujuan**: memantau aktivitas router secara real-time dari PC — terutama untuk
  **mendeteksi kapan ACS bertindak** (perubahan config, event TR-069) dan mengaudit
  perubahan yang terjadi (log mencatat event seperti perubahan SSID/PSK).
- **Cara kerja**: UDP listener di port 514; router diarahkan ke PC lewat web UI
  (*Management & Diagnosis → System Log → Target: Remote, Server: <IP PC>*) atau
  via `sendcmd` (`SysLogServer`, `SysLogTarget=1`, `SysLogEnable=1`).
- **Catatan Windows**: butuh rule firewall inbound UDP 514:
  ```powershell
  netsh advfirewall firewall add rule name="ZTE Syslog" dir=in action=allow protocol=UDP localport=514
  ```

### `scripts/reset_recover.cjs` — Pemulihan password pasca factory reset
- **Tujuan**: setelah factory reset, menguji otomatis **kandidat password pabrik yang
  terdokumentasi publik** (Telkomdso123, Web@0063, user/user, dst.) sampai login web
  sukses — langkah pertama dalam seluruh rantai.
- **Cara kerja**: replikasi persis alur login web ZTE (sess_token → login_token →
  POST `SHA256(password + token)`), dengan penanganan lockout otomatis
  (3 gagal → lock ±60 detik, skrip menunggu dan melanjutkan).
- **Batasan**: hanya kandidat publik; unit yang di-provision ACS memerlukan reset
  dulu agar kembali ke password pabrik.

### `docs/` — Dokumentasi reverse-engineering
| Dokumen | Isi |
|---|---|
| `01-analisis-firmware.md` | Derivasi key `hardcodefile` (SHA256 dari slice `/etc/hardcode`), dekripsi `db_default_<region>_cfg.xml` (AES 2 lapis + zlib), **formula password pabrik per-flag** (`dbDefAuthUserInfoProduct`: flag 66 → `superadmin`+ROS, 61 → SN hex, 68 → `Mega_<SN>`, dll.), model hak akses dmenu |
| `02-webfac-protocol.md` | Bedah lengkap protokol `/webFac` + `/webFacEntry`, lokasi handler di `httpd`, dan bukti bahwa auth memakai kredensial web admin |
| `03-sendcmd-cheatsheet.md` | Perintah `sendcmd 1 DB ...` yang relevan: inspeksi, password, TR-069 on/off, telnet, dengan peringatan soal `WANC` |

---

##  Skenario pemakaian umum

**A. "Password superadmin saya tidak tahu (diacak ISP)"**
1. Factory reset (tombol ±10 detik) → password kembali ke pabrik
2. `node scripts/reset_recover.cjs` → dapat kredensial admin
3. `python scripts/factory_unlock.py --user admin --password "<hasil langkah 2>"`
4. `python scripts/tr069_control.py --user <temp> --password <temp> --disable-tr069`
5. Selesai — superadmin permanen; login web dengan kredensial langkah 2

**B. "Sudah punya password admin, mau telnet root"**
Langkah 3 saja.

**C. "Sudah selesai di-reset dan ingin mencegah ACS menimpa lagi"**
Langkah 4 saja (diulang setiap kali router ter-reset).

---

##  Catatan penting

- `TelnetCfg` bisa dikunci via `sendcmd` (`TS_Enable=1`, `Lan_Enable=1`,
  `Lan_EnableAfterOlt=1`), namun pada build P1N84A daemon telnet **tidak autostart
  saat boot** — ia di-start oleh elevasi factory mode (`mode=2`). Konsekuensinya:
  akses telnet selalu bisa dibuka ulang selama password web admin diketahui.
- **Jangan factory reset setelah TR-069 dimatikan** — reset mengembalikan
  konfigurasi ACS ke default (aktif) dan siklus pengacakan password dimulai lagi.
  Jika terjadi, ulangi skenario A.
- Halaman web *User Configuration Management* (backup `config.bin`) dihapus dari
  menu pada build IndiHome — arsip konfigurasi bisa diganti dengan dump
  `sendcmd 1 DB p <Tabel>` per tabel.

##  Referensi

- [rendlavenu/zte-f670l-toolkit](https://github.com/rendlavenu/zte-f670l-toolkit) — implementasi challenge `/webFac` (MIT)
- [LogDict — kumpulan perintah telnet ZTE](https://www.logdict.com/archives/zhong-xing-guang-mao-telnetpei-zhi-ming-ling-hui-zong)
- [right.com.cn — pola "固化" + disable TR-069](https://www.right.com.cn/forum/thread-8481756-1-1.html)

##  Lisensi

MIT — lihat [LICENSE](LICENSE).
