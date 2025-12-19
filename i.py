#!/usr/bin/env python3
import json, base64, hashlib, time, sys, re, os, shutil, asyncio, aiohttp, threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import nacl.signing
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import hmac
import ssl
import signal

# ============== KONFIGURASI TAMPILAN ==============
class Colors:
    # Warna yang lebih modern
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Warna utama
    PRIMARY = '\033[38;5;117m'      # Biru muda
    SECONDARY = '\033[38;5;141m'    # Ungu
    SUCCESS = '\033[38;5;84m'       # Hijau muda
    WARNING = '\033[38;5;221m'      # Kuning
    ERROR = '\033[38;5;203m'        # Merah muda
    INFO = '\033[38;5;110m'         # Biru abu
    
    # Background
    BG_DARK = '\033[48;5;236m'      # Abu-abu gelap
    BG_LIGHT = '\033[48;5;240m'     # Abu-abu terang
    
    # Element khusus
    ACCENT = '\033[38;5;215m'       # Oranye
    HIGHLIGHT = '\033[38;5;228m'    # Kuning terang

C = Colors()

# ============== KONFIGURASI UTAMA ==============
class Config:
    WIDTH = 100
    HEIGHT = 30
    REFRESH_INTERVAL = 5  # detik
    MAX_HISTORY = 20

cfg = Config()

# ============== VARIABEL GLOBAL ==============
priv, addr, rpc = None, None, None
sk, pub = None, None
b58 = re.compile(r"^oct[1-9A-HJ-NP-Za-km-z]{44}$")
μ = 1_000_000
h = []
cb, cn, lu, lh = None, None, 0, 0
session = None
executor = ThreadPoolExecutor(max_workers=1)
stop_flag = threading.Event()
spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
spinner_idx = 0

# ============== FUNGSI UTILITAS ==============
def clear():
    """Bersihkan layar"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_terminal_size():
    """Dapatkan ukuran terminal"""
    return shutil.get_terminal_size((cfg.WIDTH, cfg.HEIGHT))

def print_at(x, y, text, color=C.RESET):
    """Cetak teks di posisi tertentu"""
    print(f"\033[{y};{x}H{color}{text}{C.RESET}", end='', flush=True)

def get_input(x, y, prompt=""):
    """Dapatkan input dari user"""
    print_at(x, y, prompt)
    print(f"\033[{y};{x + len(prompt)}H", end='', flush=True)
    try:
        return input()
    except KeyboardInterrupt:
        stop_flag.set()
        return ""

async def async_get_input(x, y, prompt=""):
    """Dapatkan input secara asynchronous"""
    print_at(x, y, prompt)
    print(f"\033[{y};{x + len(prompt)}H", end='', flush=True)
    try:
        return await asyncio.get_event_loop().run_in_executor(executor, input)
    except:
        stop_flag.set()
        return ""

def draw_box(x, y, width, height, title=""):
    """Gambar kotak dengan border"""
    # Border atas
    print_at(x, y, "╭" + "─" * (width - 2) + "╮", C.INFO)
    
    # Judul (jika ada)
    if title:
        title_text = f" {title} "
        title_pos = x + (width - len(title_text)) // 2
        print_at(title_pos, y, title_text, C.BOLD + C.PRIMARY)
    
    # Sisi
    for i in range(1, height - 1):
        print_at(x, y + i, "│", C.INFO)
        print_at(x + width - 1, y + i, "│", C.INFO)
    
    # Border bawah
    print_at(x, y + height - 1, "╰" + "─" * (width - 2) + "╯", C.INFO)

def draw_line(x, y, length, char="─"):
    """Gambar garis horizontal"""
    print_at(x, y, char * length, C.DIM + C.INFO)

def load_wallet():
    """Muat wallet dari file"""
    global priv, addr, rpc, sk, pub
    try:
        # Cari file wallet
        paths = [
            os.path.expanduser("~/.octra/wallet.json"),
            "wallet.json",
            "./wallet.json"
        ]
        
        wallet_path = None
        for path in paths:
            if os.path.exists(path):
                wallet_path = path
                break
        
        if not wallet_path:
            return False
        
        with open(wallet_path, 'r') as f:
            data = json.load(f)
        
        priv = data.get('priv')
        addr = data.get('addr')
        rpc = data.get('rpc', 'http://localhost:8080')
        
        if not priv or not addr:
            return False
        
        # Peringatan untuk HTTP
        if not rpc.startswith('https://') and 'localhost' not in rpc:
            print(f"{C.WARNING}⚠️  WARNING: Using insecure HTTP connection!{C.RESET}")
            time.sleep(1)
        
        # Inisialisasi kunci
        sk = nacl.signing.SigningKey(base64.b64decode(priv))
        pub = base64.b64encode(sk.verify_key.encode()).decode()
        
        return True
    except Exception as e:
        print(f"{C.ERROR}Error loading wallet: {e}{C.RESET}")
        return False

async def spinner(x, y, message):
    """Tampilkan spinner animasi"""
    global spinner_idx
    try:
        while True:
            print_at(x, y, f"{spinner_frames[spinner_idx]} {message}", C.PRIMARY)
            spinner_idx = (spinner_idx + 1) % len(spinner_frames)
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print_at(x, y, " " * (len(message) + 3), "")

# ============== FUNGSI CRYPTO ==============
def derive_encryption_key(privkey_b64):
    """Derive encryption key dari private key"""
    privkey_bytes = base64.b64decode(privkey_b64)
    salt = b"octra_encrypted_balance_v2"
    return hashlib.sha256(salt + privkey_bytes).digest()[:32]

def encrypt_client_balance(balance, privkey_b64):
    """Enkripsi balance"""
    key = derive_encryption_key(privkey_b64)
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    plaintext = str(balance).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return "v2|" + base64.b64encode(nonce + ciphertext).decode()

def decrypt_client_balance(encrypted_data, privkey_b64):
    """Dekripsi balance"""
    if encrypted_data == "0" or not encrypted_data:
        return 0
    
    if not encrypted_data.startswith("v2|"):
        # Legacy format
        privkey_bytes = base64.b64decode(privkey_b64)
        salt = b"octra_encrypted_balance_v1"
        key = hashlib.sha256(salt + privkey_bytes).digest() + hashlib.sha256(privkey_bytes + salt).digest()
        key = key[:32]
        
        try:
            data = base64.b64decode(encrypted_data)
            if len(data) < 32:
                return 0
            
            nonce = data[:16]
            tag = data[16:32]
            encrypted = data[32:]
            
            expected_tag = hashlib.sha256(nonce + encrypted + key).digest()[:16]
            if not hmac.compare_digest(tag, expected_tag):
                return 0
            
            decrypted = bytearray()
            key_hash = hashlib.sha256(key + nonce).digest()
            for i, byte in enumerate(encrypted):
                decrypted.append(byte ^ key_hash[i % 32])
            
            return int(decrypted.decode())
        except:
            return 0
    
    try:
        # V2 format
        b64_data = encrypted_data[3:]
        raw = base64.b64decode(b64_data)
        
        if len(raw) < 28:
            return 0
        
        nonce = raw[:12]
        ciphertext = raw[12:]
        
        key = derive_encryption_key(privkey_b64)
        aesgcm = AESGCM(key)
        
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return int(plaintext.decode())
    except:
        return 0

# ============== FUNGSI NETWORK ==============
async def create_session():
    """Buat session HTTP"""
    global session
    if not session:
        ssl_context = ssl.create_default_context()
        connector = aiohttp.TCPConnector(ssl=ssl_context, force_close=True)
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            connector=connector,
            json_serialize=json.dumps
        )
    return session

async def api_request(method, endpoint, data=None, timeout=10):
    """Kirim request ke API"""
    await create_session()
    
    try:
        url = f"{rpc}{endpoint}"
        
        kwargs = {}
        if method == 'POST' and data:
            kwargs['json'] = data
        
        async with getattr(session, method.lower())(url, **kwargs) as resp:
            text = await resp.text()
            
            try:
                json_data = json.loads(text) if text.strip() else None
            except:
                json_data = None
            
            return resp.status, text, json_data
    except asyncio.TimeoutError:
        return 0, "timeout", None
    except Exception as e:
        return 0, str(e), None

async def get_status():
    """Dapatkan status wallet"""
    global cb, cn, lu
    
    now = time.time()
    if cb is not None and (now - lu) < 30:
        return cn, cb
    
    # Dapatkan balance dan nonce
    status, _, data = await api_request('GET', f'/balance/{addr}')
    
    if status == 200 and data:
        cn = int(data.get('nonce', 0))
        cb = float(data.get('balance', 0))
        lu = now
    elif status == 404:
        cn, cb, lu = 0, 0.0, now
    
    return cn, cb

async def get_transaction_history():
    """Dapatkan riwayat transaksi"""
    global h, lh
    
    now = time.time()
    if now - lh < 60 and h:
        return
    
    status, _, data = await api_request('GET', f'/address/{addr}?limit={cfg.MAX_HISTORY}')
    
    if status == 200 and data and 'recent_transactions' in data:
        new_transactions = []
        for tx_ref in data.get('recent_transactions', []):
            tx_hash = tx_ref["hash"]
            
            # Dapatkan detail transaksi
            tx_status, _, tx_data = await api_request('GET', f'/tx/{tx_hash}', timeout=5)
            
            if tx_status == 200 and tx_data and 'parsed_tx' in tx_data:
                parsed = tx_data['parsed_tx']
                
                transaction = {
                    'hash': tx_hash,
                    'time': datetime.fromtimestamp(parsed.get('timestamp', 0)),
                    'amount': float(parsed.get('amount', 0)) / μ,
                    'to': parsed.get('to'),
                    'from': parsed.get('from'),
                    'type': 'in' if parsed.get('to') == addr else 'out',
                    'nonce': parsed.get('nonce', 0),
                    'epoch': tx_ref.get('epoch', 0),
                    'message': None
                }
                
                # Ekstrak pesan jika ada
                if 'data' in tx_data:
                    try:
                        msg_data = json.loads(tx_data['data'])
                        transaction['message'] = msg_data.get('message')
                    except:
                        pass
                
                new_transactions.append(transaction)
        
        # Gabungkan dan urutkan
        h = sorted(new_transactions + h[:10], 
                  key=lambda x: x['time'], 
                  reverse=True)[:cfg.MAX_HISTORY]
        lh = now

# ============== TAMPILAN UTAMA ==============
async def draw_header():
    """Gambar header aplikasi"""
    width, _ = get_terminal_size()
    
    # Baris judul
    title = f"⚡ OCTRA WALLET v0.1.0"
    timestamp = datetime.now().strftime('%H:%M:%S')
    header_text = f"{title} │ {timestamp}"
    
    print_at(2, 1, "═" * (width - 4), C.PRIMARY)
    print_at((width - len(header_text)) // 2, 2, header_text, C.BOLD + C.PRIMARY)
    print_at(2, 3, "═" * (width - 4), C.PRIMARY)

async def draw_wallet_info():
    """Gambar informasi wallet"""
    # Dapatkan data wallet
    nonce, balance = await get_status()
    await get_transaction_history()
    
    width, height = get_terminal_size()
    
    # Panel Wallet Info (kiri)
    draw_box(2, 5, 35, 12, "WALLET INFO")
    
    print_at(4, 6, "Address:", C.INFO)
    print_at(13, 6, f"{addr[:16]}...{addr[-8:]}", C.SECONDARY)
    
    print_at(4, 7, "Balance:", C.INFO)
    print_at(13, 7, f"{balance:.6f} OCT", C.SUCCESS)
    
    print_at(4, 8, "Nonce:", C.INFO)
    print_at(13, 8, str(nonce), C.WARNING)
    
    draw_line(4, 9, 31)
    
    # Info tambahan
    print_at(4, 10, "Network:", C.INFO)
    network_status = "✅ Connected" if rpc else "❌ Disconnected"
    print_at(13, 10, network_status, C.SUCCESS if rpc else C.ERROR)
    
    print_at(4, 11, "RPC:", C.INFO)
    print_at(9, 11, rpc[:25] + "..." if len(rpc) > 25 else rpc, C.DIM + C.INFO)
    
    print_at(4, 12, "Public Key:", C.INFO)
    print_at(15, 12, f"{pub[:16]}...", C.SECONDARY)

async def draw_balance_details():
    """Gambar detail balance (encrypted/private)"""
    width, height = get_terminal_size()
    
    # Panel Balance Details (tengah)
    draw_box(39, 5, 35, 12, "BALANCE DETAILS")
    
    try:
        # Coba dapatkan encrypted balance
        status, _, data = await api_request('GET', f'/view_encrypted_balance/{addr}')
        
        if status == 200 and data:
            public_bal = float(data.get('public_balance', '0').split()[0])
            encrypted_bal = float(data.get('encrypted_balance', '0').split()[0])
            total_bal = float(data.get('total_balance', '0').split()[0])
            
            print_at(41, 6, "Public:", C.INFO)
            print_at(49, 6, f"{public_bal:.6f} OCT", C.SUCCESS)
            
            print_at(41, 7, "Encrypted:", C.INFO)
            print_at(52, 7, f"{encrypted_bal:.6f} OCT", C.ACCENT)
            
            print_at(41, 8, "Total:", C.INFO)
            print_at(48, 8, f"{total_bal:.6f} OCT", C.BOLD + C.HIGHLIGHT)
            
            draw_line(41, 9, 31)
            
            # Pending transfers
            status, _, pending_data = await api_request('GET', 
                f'/pending_private_transfers?address={addr}')
            
            if status == 200 and pending_data:
                pending_count = len(pending_data.get('pending_transfers', []))
                print_at(41, 10, "Pending Claims:", C.INFO)
                print_at(57, 10, str(pending_count), C.WARNING)
        else:
            print_at(41, 6, "Standard Wallet Mode", C.DIM + C.INFO)
            print_at(41, 7, "Private features not available", C.DIM + C.WARNING)
            
    except:
        print_at(41, 6, "Unable to load balance details", C.DIM + C.ERROR)

async def draw_recent_transactions():
    """Gambar riwayat transaksi terbaru"""
    width, height = get_terminal_size()
    
    # Panel Recent Transactions (kanan atas)
    draw_box(76, 5, width - 78, 12, "RECENT TRANSACTIONS")
    
    if not h:
        print_at(78, 8, "No transactions yet", C.DIM + C.INFO)
        return
    
    # Header tabel
    print_at(78, 6, "TIME     TYPE    AMOUNT", C.DIM + C.INFO)
    print_at(78, 7, "════════ ════ ═════════", C.DIM + C.INFO)
    
    # Tampilkan transaksi terbaru
    for i, tx in enumerate(h[:5]):  # Maks 5 transaksi
        y_pos = 8 + i
        if y_pos >= 15:  # Batas panel
            break
        
        # Waktu
        time_str = tx['time'].strftime('%H:%M')
        print_at(78, y_pos, time_str, C.DIM + C.INFO)
        
        # Tipe
        tx_type = "IN " if tx['type'] == 'in' else "OUT"
        tx_color = C.SUCCESS if tx['type'] == 'in' else C.ERROR
        print_at(87, y_pos, tx_type, tx_color)
        
        # Amount
        amount_str = f"{tx['amount']:>8.4f}"
        print_at(92, y_pos, amount_str, C.WARNING)
        
        # Indicator untuk transaksi dengan pesan
        if tx.get('message'):
            print_at(101, y_pos, "💬", C.ACCENT)

async def draw_quick_actions():
    """Gambar panel aksi cepat"""
    width, height = get_terminal_size()
    
    # Panel Quick Actions (bawah kiri)
    draw_box(2, 18, 35, 10, "QUICK ACTIONS")
    
    actions = [
        ("[1]", "Send Transaction"),
        ("[2]", "Private Transfer"),
        ("[3]", "Encrypt Balance"),
        ("[4]", "Claim Transfers"),
        ("[5]", "Multi Send"),
        ("[6]", "Wallet Tools")
    ]
    
    for i, (key, action) in enumerate(actions):
        y_pos = 19 + i
        print_at(4, y_pos, key, C.ACCENT + C.BOLD)
        print_at(8, y_pos, action, C.INFO)

async def draw_commands():
    """Gambar panel perintah"""
    width, height = get_terminal_size()
    
    # Panel Commands (bawah kanan)
    draw_box(39, 18, width - 40, 10, "COMMANDS")
    
    commands = [
        ("[R]", "Refresh", "Update all data"),
        ("[H]", "History", "View full history"),
        ("[E]", "Export", "Export wallet info"),
        ("[C]", "Clear", "Clear transaction history"),
        ("[Q]", "Quit", "Exit application")
    ]
    
    for i, (key, cmd, desc) in enumerate(commands):
        y_pos = 19 + i
        print_at(41, y_pos, key, C.WARNING + C.BOLD)
        print_at(45, y_pos, cmd, C.INFO)
        print_at(55, y_pos, desc, C.DIM + C.INFO)

async def draw_footer():
    """Gambar footer dengan status"""
    width, height = get_terminal_size()
    
    # Status bar
    print_at(2, height - 2, "═" * (width - 4), C.PRIMARY)
    
    status_text = "🟢 READY"
    last_update = f"Updated: {datetime.now().strftime('%H:%M:%S')}"
    
    print_at(2, height - 1, status_text, C.SUCCESS + C.BOLD)
    print_at(width - len(last_update) - 2, height - 1, last_update, C.DIM + C.INFO)

async def draw_main_screen():
    """Gambar seluruh tampilan utama"""
    clear()
    await draw_header()
    await draw_wallet_info()
    await draw_balance_details()
    await draw_recent_transactions()
    await draw_quick_actions()
    await draw_commands()
    await draw_footer()

# ============== FUNGSI INTERAKTIF ==============
async def send_transaction():
    """Kirim transaksi"""
    await draw_main_screen()
    
    width, height = get_terminal_size()
    draw_box(25, 10, 50, 8, "SEND TRANSACTION")
    
    # Input penerima
    print_at(27, 12, "To Address:", C.INFO)
    recipient = await async_get_input(39, 12, "")
    
    if not recipient or recipient.lower() == 'cancel':
        return
    
    # Validasi alamat
    if not b58.match(recipient):
        print_at(27, 14, "Invalid address format!", C.ERROR)
        await asyncio.sleep(2)
        return
    
    # Input amount
    print_at(27, 13, "Amount (OCT):", C.INFO)
    amount_str = await async_get_input(41, 13, "")
    
    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except:
        print_at(27, 15, "Invalid amount!", C.ERROR)
        await asyncio.sleep(2)
        return
    
    # Konfirmasi
    print_at(27, 15, f"Send {amount:.6f} OCT to:", C.WARNING)
    print_at(27, 16, recipient[:32] + "...", C.SECONDARY)
    print_at(27, 17, "Confirm? [Y/N]:", C.ACCENT)
    
    confirm = await async_get_input(44, 17, "")
    
    if confirm.lower() != 'y':
        return
    
    # Kirim transaksi
    spinner_task = asyncio.create_task(spinner(27, 19, "Sending transaction..."))
    
    try:
        # Dapatkan nonce terbaru
        nonce, balance = await get_status()
        
        if balance < amount:
            raise Exception("Insufficient balance")
        
        # Buat transaksi
        tx_data = {
            "from": addr,
            "to_": recipient,
            "amount": str(int(amount * μ)),
            "nonce": nonce + 1,
            "ou": str(10_000),
            "timestamp": time.time()
        }
        
        # Sign transaksi
        tx_json = json.dumps({k: v for k, v in tx_data.items()}, separators=(",", ":"))
        signature = base64.b64encode(sk.sign(tx_json.encode()).signature).decode()
        tx_data.update(signature=signature, public_key=pub)
        
        # Kirim ke node
        status, response, data = await api_request('POST', '/send-tx', tx_data)
        
        if status == 200:
            print_at(27, 19, "✅ Transaction sent successfully!", C.SUCCESS)
            if data and 'tx_hash' in data:
                print_at(27, 20, f"Hash: {data['tx_hash'][:32]}...", C.INFO)
        else:
            error_msg = data.get('error', response) if data else response
            print_at(27, 19, f"❌ Failed: {error_msg[:40]}", C.ERROR)
            
    except Exception as e:
        print_at(27, 19, f"❌ Error: {str(e)}", C.ERROR)
    finally:
        spinner_task.cancel()
        await asyncio.sleep(3)

async def show_menu():
    """Tampilkan menu utama"""
    await draw_main_screen()
    
    width, height = get_terminal_size()
    
    # Input prompt
    print_at(2, height - 3, "➤ Select option [1-6, R, H, E, C, Q]:", C.PRIMARY + C.BOLD)
    
    return await async_get_input(36, height - 3, "")

# ============== MAIN LOOP ==============
async def main_loop():
    """Loop utama aplikasi"""
    if not load_wallet():
        print(f"{C.ERROR}Failed to load wallet. Make sure wallet.json exists.{C.RESET}")
        return
    
    print(f"{C.SUCCESS}Wallet loaded successfully!{C.RESET}")
    await asyncio.sleep(1)
    
    while not stop_flag.is_set():
        try:
            command = await show_menu()
            command = command.strip().lower()
            
            if command == 'q' or command == '0':
                break
            elif command == '1':
                await send_transaction()
            elif command == 'r' or command == '2':
                continue  # Refresh otomatis di main screen
            elif command == 'h':
                # TODO: Implement history view
                pass
            elif command == 'e':
                # TODO: Implement export
                pass
            elif command == 'c':
                h.clear()
                lh = 0
            else:
                # Feedback untuk input tidak valid
                width, height = get_terminal_size()
                print_at(2, height - 4, "Invalid option. Press any key...", C.ERROR)
                await async_get_input(35, height - 4, "")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"{C.ERROR}Error: {e}{C.RESET}")
            await asyncio.sleep(1)

# ============== HANDLER SIGNAL ==============
def signal_handler(sig, frame):
    """Handle interrupt signals"""
    stop_flag.set()
    if session:
        asyncio.create_task(session.close())
    clear()
    print(f"{C.SUCCESS}Goodbye!{C.RESET}")
    sys.exit(0)

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Jalankan aplikasi
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
    finally:
        clear()
        print(f"{C.RESET}")
        if session:
            asyncio.run(session.close())
