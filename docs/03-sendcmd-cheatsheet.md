# 03 — Cheatsheet `sendcmd` (telnet root)

Sumber utama: [LogDict — perintah telnet ZTE](https://www.logdict.com/archives/zhong-xing-guang-mao-telnetpei-zhi-ming-ling-hui-zong),
[right.com.cn thread 8481756](https://www.right.com.cn/forum/thread-8481756-1-1.html).
Terverifikasi pada F670L V9.0.11P1N84A (kecuali ditandai).

## Inspeksi

```sh
sendcmd 1 DB p DevAuthInfo     # akun web (User/Pass ditampilkan ter-mask)
sendcmd 1 DB p MgtServer       # konfigurasi ACS/TR-069
sendcmd 1 DB p TelnetCfg       # konfigurasi telnet
sendcmd 1 DB p WANC            # koneksi WAN
sendcmd 1 DB pUserInfo         # varian beberapa build
```

## Password akun web

```sh
sendcmd 1 DB set DevAuthInfo 0 Pass <passwordbaru>   # row 0 = admin (IGD.AU1)
sendcmd 1 DB set DevAuthInfo 1 Pass <passwordbaru>   # row 1 = user  (IGD.AU2)
sendcmd 1 DB save
```

## Nonaktifkan TR-069 / ACS (hentikan ISP mengubah password)

```sh
sendcmd 1 DB set MgtServer 0 URL http://127.0.0.1
sendcmd 1 DB set MgtServer 0 Tr069Enable 0
sendcmd 1 DB set MgtServer 0 PeriodicInformEnable 0
sendcmd 1 DB save
```

Aktifkan kembali (provision ulang oleh ISP):

```sh
sendcmd 1 DB set MgtServer 0 URL http://acs.telkom.net:9090/web/tr069
sendcmd 1 DB set MgtServer 0 Tr069Enable 1
sendcmd 1 DB set MgtServer 0 PeriodicInformEnable 1
sendcmd 1 DB save
reboot
```

> Jangan sentuh `WANC` (koneksi WAN) kalau tidak paham — row 0 bisa jadi
> koneksi internet, bukan hanya TR-069.

## Telnet

```sh
sendcmd 1 DB set TelnetCfg 0 TS_Enable 1
sendcmd 1 DB set TelnetCfg 0 Lan_Enable 1
sendcmd 1 DB set TelnetCfg 0 Lan_EnableAfterOlt 1
sendcmd 1 DB set TelnetCfg 0 Max_Con_Num 99
sendcmd 1 DB set TelnetCfg 0 TS_UName root
sendcmd 1 DB set TelnetCfg 0 TS_UPwd <password>
sendcmd 1 DB set TelnetCfg 0 TSLan_UName root
sendcmd 1 DB set TelnetCfg 0 TSLan_UPwd <password>
sendcmd 1 DB save
```

Catatan F670L P1N84A: konfigurasi tersimpan, tetapi daemon telnet tetap tidak
autostart saat boot — start dipicu elevasi factory mode (`FactoryMode mode=2`).

## Lain-lain

```sh
sendcmd 1 DB p CltLmt                       # batasi jumlah klien login web
sendcmd 1 DB set CltLmt 8 Enable 0          # lepaskan batas
sendcmd 1 DB save
reboot
```
