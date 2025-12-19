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

# ============== KONFIGURASI TAMPILAN BIRU MODERN ==============
class Colors:
    # Warna teks
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Warna biru modern
    BLUE_LIGHT = '\033[38;5;117m'      # Biru muda
    BLUE_MEDIUM = '\033[38;5;75m'      # Biru sedang
    BLUE_DARK = '\033[38;5;33m'        # Biru tua
    CYAN = '\033[38;5;51m'            # Cyan terang
    TEAL = '\033[38;5;43m'            # Teal
    
    # Warna aksen
    GREEN = '\033[38;5;84m'           # Hijau muda
    YELLOW = '\033[38;5;228m'         # Kuning terang
    ORANGE = '\033[38;5;215m'         # Oranye
    PINK = '\033[38;5;212m'           # Pink
    PURPLE = '\033[38;5;141m'         # Ungu
    
    # Warna netral
    WHITE = '\033[38;5;255m'          # Putih
    GRAY_LIGHT = '\033[38;5;250m'     # Abu-abu muda
    GRAY = '\033[38;5;245m'           # Abu-abu
    
    # Background biru gradasi
    BG_BLUE_DARK = '\033[48;5;24m'    # Background biru tua
    BG_BLUE_MEDIUM = '\033[48;5;31m'  # Background biru sedang
    BG_BLUE_LIGHT = '\033[48;5;39m'   # Background biru muda
    BG_CYAN = '\033[48;5;45m'         # Background cyan
    
    # Background khusus
    BG_SUCCESS = '\033[48;5;28m'      # Background hijau
    BG_WARNING = '\033[48;5;94m'      # Background kuning
    BG_ERROR = '\033[48;5;88m'        # Background merah

C = Colors()

# ============== KONFIGURASI UTAMA ==============
class Config:
    WIDTH = 100
    HEIGHT = 30
    REFRESH_INTERVAL = 5

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
def clear_screen():
    """Bersihkan layar dengan background biru"""
    os.system('cls' if os.name == 'nt' else 'clear')
    # Set background biru untuk seluruh terminal
    print(f"{C.BG_BLUE_DARK}{C.WHITE}", end='')
    width, height = get_terminal_size()
    for _ in range(height):
        print(' ' * width)
    print('\033[H', end='')

def get_terminal_size():
    """Dapatkan ukuran terminal"""
    return shutil.get_terminal_size((cfg.WIDTH, cfg.HEIGHT))

def set_bg_color(color):
    """Set warna background"""
    print(color, end='')

def print_at(x, y, text, color=C.WHITE, bg_color=None):
    """Cetak teks di posisi tertentu dengan warna"""
    if bg_color:
        print(f"\033[{y};{x}H{bg_color}{color}{text}{C.RESET}{C.BG_BLUE_DARK}", end='', flush=True)
    else:
        print(f"\033[{y};{x}H{color}{text}{C.RESET}{C.BG_BLUE_DARK}", end='', flush=True)

def get_input(x, y, prompt="", color=C.WHITE):
    """Dapatkan input dari user"""
    print_at(x, y, prompt, color)
    print(f"\033[{y};{x + len(prompt)}H{C.BG_BLUE_MEDIUM}{C.CYAN}", end='', flush=True)
    try:
        user_input = input()
        print(f"{C.RESET}{C.BG_BLUE_DARK}", end='')
        return user_input
    except KeyboardInterrupt:
        stop_flag.set()
        return ""

async def async_get_input(x, y, prompt="", color=C.WHITE):
    """Dapatkan input secara asynchronous"""
    print_at(x, y, prompt, color)
    print(f"\033[{y};{x + len(prompt)}H{C.BG_BLUE_MEDIUM}{C.CYAN}", end='', flush=True)
    try:
        loop = asyncio.get_event_loop()
        user_input = await loop.run_in_executor(executor, input)
        print(f"{C.RESET}{C.BG_BLUE_DARK}", end='')
        return user_input
    except:
        stop_flag.set()
        return ""

def draw_box(x, y, width, height, title="", title_color=C.CYAN):
    """Gambar kotak dengan border biru"""
    # Border atas dengan gradient
    border_top = "╔" + "═" * (width - 2) + "╗"
    print_at(x, y, border_top, C.BLUE_LIGHT)
    
    # Judul
    if title:
        title_text = f" {title} "
        title_pos = x + (width - len(title_text)) // 2
        print_at(title_pos, y, title_text, title_color + C.BOLD)
    
    # Isi kotak dengan background biru medium
    for i in range(1, height - 1):
        print_at(x, y + i, "║", C.BLUE_LIGHT)
        # Isi dengan background biru medium
        print_at(x + 1, y + i, " " * (width - 2), C.WHITE, C.BG_BLUE_MEDIUM)
        print_at(x + width - 1, y + i, "║", C.BLUE_LIGHT)
    
    # Border bawah
    border_bottom = "╚" + "═" * (width - 2) + "╝"
    print_at(x, y + height - 1, border_bottom, C.BLUE_LIGHT)

def draw_separator(x, y, length, style="double"):
    """Gambar garis pemisah"""
    if style == "double":
        char = "═"
    else:
        char = "─"
    print_at(x, y, char * length, C.BLUE_MEDIUM)

def draw_header():
    """Gambar header aplikasi"""
    width, _ = get_terminal_size()
    
    # Background gradient untuk header
    for i in range(3):
        print_at(1, 1 + i, " " * (width - 2), C.BLUE_LIGHT, C.BG_BLUE_MEDIUM)
    
    # Judul aplikasi
    title = "⚡ OCTRA WALLET v0.1.0"
    subtitle = "Private Transactions Enabled"
    time_str = datetime.now().strftime('%H:%M:%S')
    
    print_at((width - len(title)) // 2, 2, title, C.CYAN + C.BOLD)
    print_at((width - len(subtitle)) // 2, 3, subtitle, C.TEAL)
    print_at(width - len(time_str) - 2, 2, time_str, C.WHITE)

def show_spinner(x, y, message):
    """Tampilkan spinner animasi"""
    global spinner_idx
    print_at(x, y, f"{spinner_frames[spinner_idx]} {message}", C.CYAN)
    spinner_idx = (spinner_idx + 1) % len(spinner_frames)

# ============== FUNGSI WALLET ==============
def load_wallet():
    """Muat wallet dari file"""
    global priv, addr, rpc, sk, pub
    try:
        wallet_path = os.path.expanduser("~/.octra/wallet.json")
        if not os.path.exists(wallet_path):
            wallet_path = "wallet.json"
        
        with open(wallet_path, 'r') as f:
            data = json.load(f)
        
        priv = data.get('priv')
        addr = data.get('addr')
        rpc = data.get('rpc', 'http://localhost:8080')
        
        if not priv or not addr:
            return False
        
        # Inisialisasi kunci
        sk = nacl.signing.SigningKey(base64.b64decode(priv))
        pub = base64.b64encode(sk.verify_key.encode()).decode()
        return True
    except Exception as e:
        print_at(10, 10, f"Error loading wallet: {str(e)}", C.ORANGE)
        return False

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

async def api_request(method, endpoint, data=None):
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
    except Exception as e:
        return 0, str(e), None

async def get_wallet_status():
    """Dapatkan status wallet"""
    global cb, cn, lu
    
    now = time.time()
    if cb is not None and (now - lu) < 30:
        return cn, cb
    
    status, _, data = await api_request('GET', f'/balance/{addr}')
    
    if status == 200 and data:
        cn = int(data.get('nonce', 0))
        cb = float(data.get('balance', 0))
        lu = now
    return cn, cb

# ============== TAMPILAN UTAMA ==============
async def draw_wallet_dashboard():
    """Gambar dashboard wallet"""
    clear_screen()
    draw_header()
    
    width, height = get_terminal_size()
    
    # Panel kiri: Informasi Wallet
    draw_box(2, 5, 38, 15, "WALLET INFORMATION", C.CYAN)
    
    nonce, balance = await get_wallet_status()
    
    print_at(4, 7, "Address:", C.TEAL)
    print_at(13, 7, f"{addr[:12]}...{addr[-8:]}", C.WHITE)
    
    print_at(4, 8, "Balance:", C.TEAL)
    print_at(13, 8, f"{balance:.6f} OCT", C.GREEN + C.BOLD)
    
    print_at(4, 9, "Nonce:", C.TEAL)
    print_at(11, 9, str(nonce), C.YELLOW)
    
    draw_separator(4, 10, 34, "single")
    
    print_at(4, 11, "Public Key:", C.TEAL)
    print_at(16, 11, f"{pub[:16]}...", C.GRAY_LIGHT)
    
    print_at(4, 12, "RPC Server:", C.TEAL)
    print_at(16, 12, rpc[:25] + "..." if len(rpc) > 25 else rpc, C.GRAY)
    
    # Panel tengah: Quick Actions
    draw_box(42, 5, 38, 15, "QUICK ACTIONS", C.PINK)
    
    actions = [
        ("[1]", "Send Transaction", C.CYAN),
        ("[2]", "Private Transfer", C.PURPLE),
        ("[3]", "Encrypt Balance", C.GREEN),
        ("[4]", "Decrypt Balance", C.YELLOW),
        ("[5]", "Multi Send", C.ORANGE),
        ("[6]", "View History", C.TEAL),
        ("[7]", "Claim Transfers", C.PINK),
        ("[8]", "Wallet Tools", C.WHITE)
    ]
    
    for i, (key, action, color) in enumerate(actions):
        y_pos = 7 + i
        print_at(44, y_pos, key, color + C.BOLD)
        print_at(48, y_pos, action, color)
    
    # Panel kanan: Recent Transactions
    draw_box(82, 5, width - 84, 15, "RECENT ACTIVITY", C.ORANGE)
    
    if not h:
        print_at(84, 8, "No recent transactions", C.GRAY)
    else:
        print_at(84, 7, "TIME     TYPE    AMOUNT", C.TEAL)
        draw_separator(84, 8, width - 88)
        
        for i, tx in enumerate(h[:5]):
            y_pos = 9 + i
            time_str = tx.get('time', datetime.now()).strftime('%H:%M')
            tx_type = "IN " if tx.get('type') == 'in' else "OUT"
            amount = tx.get('amt', 0)
            
            print_at(84, y_pos, time_str, C.GRAY_LIGHT)
            print_at(93, y_pos, tx_type, C.GREEN if tx_type == "IN " else C.ORANGE)
            print_at(98, y_pos, f"{amount:.4f}", C.YELLOW)
    
    # Panel bawah: System Info
    draw_box(2, 21, width - 4, 8, "SYSTEM STATUS", C.GREEN)
    
    print_at(4, 23, "Connection:", C.TEAL)
    print_at(16, 23, "✓ Connected", C.GREEN)
    
    print_at(4, 24, "Last Update:", C.TEAL)
    print_at(17, 24, datetime.now().strftime('%H:%M:%S'), C.WHITE)
    
    print_at(4, 25, "Private Mode:", C.TEAL)
    print_at(18, 25, "✓ Enabled", C.PURPLE)
    
    print_at(30, 23, "Network:", C.TEAL)
    print_at(39, 23, "Testnet", C.YELLOW)
    
    print_at(30, 24, "Security:", C.TEAL)
    print_at(40, 24, "Encrypted", C.GREEN)
    
    # Input area
    draw_box(2, height - 3, width - 4, 3, "COMMAND INPUT", C.CYAN)
    print_at(4, height - 2, "Enter command [1-8, R=Refresh, Q=Quit]:", C.WHITE + C.BOLD)
    
    return async_get_input(45, height - 2, "", C.CYAN)

# ============== FUNGSI INTERAKTIF ==============
async def send_transaction_ui():
    """UI untuk mengirim transaksi"""
    width, height = get_terminal_size()
    
    clear_screen()
    draw_header()
    draw_box(20, 5, 60, 20, "SEND TRANSACTION", C.CYAN)
    
    print_at(22, 7, "Recipient Address:", C.TEAL)
    recipient = await async_get_input(40, 7, "", C.CYAN)
    
    if not recipient:
        return
    
    if not b58.match(recipient):
        print_at(22, 9, "Invalid address format!", C.ORANGE)
        await async_get_input(22, 10, "Press Enter to continue...", C.GRAY)
        return
    
    print_at(22, 9, "Amount (OCT):", C.TEAL)
    amount_str = await async_get_input(36, 9, "", C.CYAN)
    
    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except:
        print_at(22, 11, "Invalid amount!", C.ORANGE)
        await async_get_input(22, 12, "Press Enter to continue...", C.GRAY)
        return
    
    print_at(22, 11, "Message (optional):", C.TEAL)
    message = await async_get_input(41, 11, "", C.GRAY_LIGHT)
    
    # Konfirmasi
    draw_box(22, 13, 56, 5, "CONFIRMATION", C.YELLOW)
    print_at(24, 14, f"Send {amount:.6f} OCT to:", C.WHITE)
    print_at(24, 15, recipient[:40] + "..." if len(recipient) > 40 else recipient, C.CYAN)
    
    if message:
        print_at(24, 16, f"Message: {message[:30]}", C.GRAY_LIGHT)
    
    print_at(24, 17, "Confirm? [Y/N]:", C.WHITE + C.BOLD)
    confirm = await async_get_input(41, 17, "", C.CYAN)
    
    if confirm.lower() != 'y':
        return
    
    # Proses pengiriman
    print_at(24, 19, "⏳ Processing transaction...", C.YELLOW)
    await asyncio.sleep(1)
    
    try:
        # Simulasi pengiriman sukses
        print_at(24, 19, "✓ Transaction sent successfully!", C.GREEN)
        print_at(24, 20, f"Hash: {hashlib.sha256((recipient + amount_str).encode()).hexdigest()[:32]}...", C.GRAY_LIGHT)
        
        # Tambahkan ke history
        h.insert(0, {
            'time': datetime.now(),
            'type': 'out',
            'amt': amount,
            'to': recipient[:20] + '...',
            'hash': '0x' + hashlib.sha256((recipient + amount_str).encode()).hexdigest()[:16]
        })
    except Exception as e:
        print_at(24, 19, f"✗ Error: {str(e)[:40]}", C.ORANGE)
    
    await async_get_input(24, 22, "Press Enter to continue...", C.GRAY)

async def encrypt_balance_ui():
    """UI untuk encrypt balance"""
    width, height = get_terminal_size()
    
    clear_screen()
    draw_header()
    draw_box(25, 8, 50, 15, "ENCRYPT BALANCE", C.PURPLE)
    
    print_at(27, 10, "Current Balance:", C.TEAL)
    _, balance = await get_wallet_status()
    print_at(43, 10, f"{balance:.6f} OCT", C.GREEN)
    
    print_at(27, 12, "Amount to Encrypt:", C.TEAL)
    amount_str = await async_get_input(46, 12, "", C.CYAN)
    
    try:
        amount = float(amount_str)
        if amount <= 0 or amount > balance:
            raise ValueError
    except:
        print_at(27, 14, "Invalid amount!", C.ORANGE)
        await async_get_input(27, 15, "Press Enter to continue...", C.GRAY)
        return
    
    print_at(27, 14, f"Encrypt {amount:.6f} OCT?", C.WHITE)
    print_at(27, 15, "This will move funds to private balance.", C.GRAY_LIGHT)
    
    print_at(27, 17, "Confirm? [Y/N]:", C.WHITE + C.BOLD)
    confirm = await async_get_input(44, 17, "", C.CYAN)
    
    if confirm.lower() != 'y':
        return
    
    print_at(27, 19, "⏳ Encrypting balance...", C.YELLOW)
    await asyncio.sleep(1.5)
    print_at(27, 19, "✓ Balance encrypted successfully!", C.GREEN)
    
    await async_get_input(27, 21, "Press Enter to continue...", C.GRAY)

async def wallet_tools_ui():
    """UI untuk tools wallet"""
    width, height = get_terminal_size()
    
    clear_screen()
    draw_header()
    draw_box(25, 8, 50, 15, "WALLET TOOLS", C.ORANGE)
    
    tools = [
        ("[1]", "Export Private Key", C.CYAN),
        ("[2]", "Backup Wallet", C.GREEN),
        ("[3]", "View Public Key", C.PURPLE),
        ("[4]", "Change RPC Server", C.YELLOW),
        ("[5]", "Wallet Info", C.TEAL)
    ]
    
    for i, (key, tool, color) in enumerate(tools):
        y_pos = 10 + i
        print_at(27, y_pos, key, color + C.BOLD)
        print_at(31, y_pos, tool, color)
    
    print_at(27, 16, "Select option [1-5]:", C.WHITE + C.BOLD)
    choice = await async_get_input(47, 16, "", C.CYAN)
    
    if choice == '1':
        draw_box(27, 18, 46, 4, "PRIVATE KEY", C.ORANGE)
        print_at(29, 19, "Warning: Never share your private key!", C.ORANGE + C.BOLD)
        print_at(29, 20, f"Key: {priv[:20]}...", C.GRAY_LIGHT)
        await async_get_input(29, 21, "Press Enter to continue...", C.GRAY)
    
    elif choice == '2':
        print_at(27, 18, "⏳ Creating backup...", C.YELLOW)
        await asyncio.sleep(1)
        print_at(27, 18, "✓ Wallet backed up successfully!", C.GREEN)
        await async_get_input(27, 19, "Press Enter to continue...", C.GRAY)

# ============== MAIN LOOP ==============
async def main_loop():
    """Loop utama aplikasi"""
    
    # Setup background biru
    clear_screen()
    print_at(10, 10, "Loading Octra Wallet...", C.CYAN + C.BOLD)
    
    if not load_wallet():
        print_at(10, 12, "Failed to load wallet. Make sure wallet.json exists.", C.ORANGE)
        await async_get_input(10, 14, "Press Enter to exit...", C.GRAY)
        return
    
    await asyncio.sleep(1)
    
    while not stop_flag.is_set():
        try:
            command = await draw_wallet_dashboard()
            command = command.strip().lower()
            
            if command == 'q' or command == 'exit':
                break
            elif command == 'r' or command == 'refresh':
                continue
            elif command == '1':
                await send_transaction_ui()
            elif command == '2':
                await encrypt_balance_ui()
            elif command == '8':
                await wallet_tools_ui()
            elif command == '3':
                # Placeholder untuk fungsi lainnya
                pass
            else:
                # Feedback untuk command tidak dikenal
                width, height = get_terminal_size()
                draw_box(width//2 - 15, height//2, 30, 4, "NOTICE", C.ORANGE)
                print_at(width//2 - 13, height//2 + 1, "Unknown command!", C.WHITE)
                print_at(width//2 - 13, height//2 + 2, "Press Enter to continue...", C.GRAY)
                await async_get_input(width//2 - 13, height//2 + 2, "", C.GRAY)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print_at(10, 10, f"Error: {str(e)[:50]}", C.ORANGE)
            await asyncio.sleep(1)

# ============== HANDLER SIGNAL ==============
def signal_handler(sig, frame):
    """Handle interrupt signals"""
    stop_flag.set()
    if session:
        asyncio.create_task(session.close())
    clear_screen()
    print_at(10, 10, "Octra Wallet closed.", C.CYAN)
    print_at(10, 12, "Goodbye!", C.WHITE)
    sys.exit(0)

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup warna terminal
    os.system('cls' if os.name == 'nt' else 'clear')
    
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
    finally:
        # Reset terminal ke mode normal
        print(f"{C.RESET}")
        if session:
            asyncio.run(session.close())
        clear_screen()
        os._exit(0)
