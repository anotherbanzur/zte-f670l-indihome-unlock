# 02 — Protokol /webFac (factory mode)

Gerbang diagnostik tersembunyi ZTE F670L: `/webFac` (challenge) dan
`/webFacEntry` (pertukaran terenkripsi). Handler di `httpd` (`source/web_fac.c`,
fungsi `start_parse_webFac` → `do_handle_webFacSq`, `do_handle_webFacCheckClientInfo`).

## Alur lengkap

```
1. POST /webFac  body "SendSq.gch"                  -> HTTP 400 (reset sesi)
2. POST /webFac  body "RequestFactoryMode.gch"      -> koneksi diputus (normal)
3. POST /webFac  body "SendSq.gch?rand=<0..59>\r\n" -> HTTP 200
   respon: "newrand=<n>"  (varian lain: "re_rand=<n>&<seed>&<mac-bytes>")
4. key AES = KEY_POOL[index : index+24] XOR 0xA5   (AES-128/192-ECB)
   index = ((0x1000193 * rand) & 0x3F ^ newrand) % 60
5. POST /webFacEntry  AES(SendInfo.gch?info=<N>|<payload>)
   payload = bukti MAC: kata-kata kecil yang dipetakan balik oleh
   do_check_client menjadi MAC lokal & MAC gateway (pow(x, e, m) & 0xff)
6. POST /webFacEntry  AES("CheckLoginAuth.gch?version50&user=<U>&pass=<P>")
   <U>/<P> = KREDENSIAL WEB ADMIN (IGD.AU1)  -> sukses: HTTP 200
   (varian lama: "?time<N>&version61")
7. POST /webFacEntry  AES("FactoryMode.gch?mode=2&user=notused")
   respon: "FactoryModeAuth.gch?user=<tempuser>&pass=<temppass>"
   -> telnet port 23 aktif; login memakai kredensial sementara itu
```

## Temuan penting

- **Auth webFac = kredensial web admin.** `doWebCheckAuth` membandingkan input
  dengan `CmDevGetAuthInfo("IGD.AU1")` → `user=%s&pass=%s`. Jalur alternatif
  `user=factorymode&pass=<WebRepKey>` hanya aktif bila tag flash `0xb01 == "1"`
  (tidak pernah di-set di unit yang diamati).
- KEY_POOL bersifat per-build firmware (94 byte; dipakai 24 byte per sesi).
  Dua pool yang dikenal tercantum di `scripts/factory_unlock.py`.
- Setelah `mode=2`, daemon telnet berjalan dengan kredensial sementara.
  `TelnetCfg` (TS_Enable/Lan_Enable/Lan_EnableAfterOlt) bisa dikunci via
  `sendcmd 1 DB set ...` + `save`, namun pada build P1N84A daemon tetap tidak
  autostart saat boot — start dipicu oleh elevasi mode=2 (CMAPI `CmTsStart`).

## Contoh isi DB via telnet root

```
sendcmd 1 DB p DevAuthInfo   # akun web (User/Pass ter-mask di output)
sendcmd 1 DB p MgtServer     # konfigurasi ACS: URL, PeriodicInformInterval, dll.
sendcmd 1 DB set MgtServer 0 Tr069Enable 0
sendcmd 1 DB save
```
