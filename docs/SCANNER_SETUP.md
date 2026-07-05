# Scanner Setup — Brother MFC-L2700W → Vaultec

Goal: press **Scan** on the Brother and have the page land in Vaultec's **Validation Inbox** automatically.

How it works: the scanner pushes the file (over your WiFi/LAN) into Vaultec's `incoming` folder. The Vaultec API watches that folder, encrypts each new file, and creates a **pending** document you approve in the Inbox. The Brother is already on WiFi — you just need a **drop target** on the server for it to send to. The MFC-L2700W supports **Scan to FTP** from its panel, which is the simplest reliable path.

---

## Step 1 — Start the FTP drop-target on the server

Vaultec ships an optional FTP service that writes straight into the folder the app watches.

1. Add these to your server `.env` (pick a real password; set the host to the server's LAN IP):
   ```
   SCANNER_FTP_USER=scanner
   SCANNER_FTP_PASS=<choose-a-strong-password>
   SCANNER_FTP_PUBLICHOST=192.168.1.50      # <-- your Vaultec server's LAN IP
   ```
2. Start it (only this service; it's behind a compose profile so it doesn't run by default):
   ```
   docker compose --profile scanner up -d scanner-ftp
   ```
3. Make sure the server firewall allows TCP **21** and **30000-30009** (passive FTP data ports) on the LAN.

Find the server IP with `hostname -I` (Linux). That IP is what the scanner will connect to.

---

## Step 2 — Configure "Scan to FTP" on the Brother

Do this once, from the printer's built-in web page (easiest):

1. Find the **printer's** IP: on the Brother panel → **Menu → Network → WLAN → TCP/IP → IP Address** (or print a Network Config page).
2. In a browser on the same LAN, open `http://<printer-ip>/` (Web Based Management).
3. Log in (default admin password is usually `initpass` or the one printed on the label).
4. Go to the **Scan** tab → **Scan to FTP/Network** → **Scan to FTP** → edit **Profile 1**:
   - **Host Address**: the **server** IP (`SCANNER_FTP_PUBLICHOST`, e.g. `192.168.1.50`)
   - **Port**: `21`
   - **Username**: `scanner` (your `SCANNER_FTP_USER`)
   - **Password**: your `SCANNER_FTP_PASS`
   - **Passive Mode**: **On**
   - **Store Directory**: leave blank / `/` (the FTP home already IS the incoming folder)
   - **File Type**: PDF (recommended) — multi-page PDF is ideal for documents
   - **File Name / Quality**: your preference
   - Save.

---

## Step 3 — Scan

1. Put the document in the Brother.
2. Panel → **Scan → Scan to FTP** → choose **Profile 1** → **Start**.
3. Within a few seconds the page appears in Vaultec under **📥 Inbox** (the vault must be **unlocked** — the watcher only ingests while unlocked; files wait safely in the folder until you unlock).
4. In the Inbox: preview it, set the **title / category / owner**, then **Approve** (moves it into the household vault) or **Reject**.

---

## Alternatives

- **Scan to Network Folder (SMB)** — some L2700 variants also support SMB. If you prefer SMB over FTP, run a Samba container mapped to the same `vaultincoming` volume and configure "Scan to Network" on the printer instead. FTP is recommended because it's supported on this model's panel with the least fuss.
- **Scan to USB, then upload** — no server setup: scan to a USB stick, then drag the PDF into Vaultec's **Upload** panel in the browser. Good as a fallback or for one-offs.

---

## Troubleshooting

- **Nothing shows in the Inbox**: is the vault **unlocked**? The watcher ignores files while locked. Also check the file actually arrived: `docker compose exec api ls -la /vault/incoming` (and `/vault/incoming/failed` for ingest errors).
- **Scanner can't connect / times out**: verify the **server** IP (not the printer's) in the profile, Passive Mode is **On**, and ports 21 + 30000-30009 are open on the server firewall.
- **`SCANNER_FTP_PUBLICHOST` matters**: passive FTP tells the client which IP to use for the data channel — it must be the server's reachable LAN IP, or transfers stall after login.
- **Auth fails**: the `scanner` user/password in the printer profile must match `.env`. Restart the service after changing `.env`: `docker compose --profile scanner up -d scanner-ftp`.
