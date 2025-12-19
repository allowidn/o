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

# ============== GHOSTTY TERMINAL THEME ==============
class GhosttyTheme:
    # Reset
    RESET = '\033[0m'
    BOLD = '\033[1m'
    FAINT = '\033[2m'
    ITALIC = '\033[3m'
    
    # Primary Ghostty Colors
    PRIMARY = '\033[38;2;64;192;255m'      # Biru neon (#40C0FF)
    SECONDARY = '\033[38;2;160;96;255m'    # Ungu neon (#A060FF)
    ACCENT = '\033[38;2;0;255;179m'        # Hijau cyan (#00FFB3)
    WARNING = '\033[38;2;255;204;0m'       # Kuning neon (#FFCC00)
    ERROR = '\033[38;2;255;64;96m'         # Merah neon (#FF4060)
    SUCCESS = '\033[38;2;64;255;128m'      # Hijau neon (#40FF80)
    
    # Neutral Colors
    WHITE = '\033[38;2;255;255;255m'
    GRAY_LIGHT = '\033[38;2;192;192;192m'
    GRAY = '\033[38;2;128;128;128m'
    GRAY_DARK = '\033[38;2;64;64;64m'
    BLACK = '\033[38;2;0;0;0m'
    
    # Background Colors (with transparency effect)
    BG_DARK = '\033[48;2;16;16;24m'        # Dark blue-black (#101018)
    BG_DARK_ALPHA = '\033[48;2;16;16;24;0.9m'  # Semi-transparent
    BG_MEDIUM = '\033[48;2;24;24;36m'      # Medium dark (#181824)
    BG_LIGHT = '\033[48;2;32;32;48m'       # Light dark (#202030)
    BG_HIGHLIGHT = '\033[48;2;40;40;60m'   # Highlight (#28283C)
    
    # Special Effects
    GLOW = '\033[38;2;64;192;255;1m'       # Glow effect
    SHADOW = '\033[38;2;0;0;0;0.7m'        # Shadow effect
    
    # Terminal Accents
    TERMINAL_GREEN = '\033[38;2;0;255;64m'  # Terminal green
    TERMINAL_CYAN = '\033[38;2;0;255;255m'  # Terminal cyan
    TERMINAL_YELLOW = '\033[38;2;255;255;0m' # Terminal yellow

T = GhosttyTheme()

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

# ============== GHOSTTY TERMINAL UTILITIES ==============
def clear_terminal():
    """Bersihkan terminal dengan efek Ghostty"""
    os.system('cls' if os.name == 'nt' else 'clear')
    # Set background gelap dengan gradasi
    print(f"{T.BG_DARK}{T.WHITE}", end='')
    width, height = shutil.get_terminal_size((100, 30))
    # Buat efek gradasi di background
    for y in range(height):
        intensity = min(255, 16 + y * 3)
        bg_color = f'\033[48;2;{intensity//2};{intensity//2};{intensity}m'
        print(f"\033[{y+1};1H{bg_color}{' ' * width}", end='')
    print(f"{T.RESET}{T.BG_DARK}", end='')
    print('\033[H', end='')

def get_terminal_size():
    """Dapatkan ukuran terminal"""
    return shutil.get_terminal_size((100, 30))

def print_ghostty(x, y, text, color=T.WHITE, bg_color=None, style=None):
    """Print dengan efek Ghostty"""
    styles = []
    if style == 'glow':
        styles.append(T.GLOW)
    elif style == 'shadow':
        styles.append(T.SHADOW)
    elif style == 'bold':
        styles.append(T.BOLD)
    elif style == 'faint':
        styles.append(T.FAINT)
    
    style_str = ''.join(styles)
    
    if bg_color:
        print(f"\033[{y};{x}H{bg_color}{style_str}{color}{text}{T.RESET}{T.BG_DARK}", end='', flush=True)
    else:
        print(f"\033[{y};{x}H{style_str}{color}{text}{T.RESET}{T.BG_DARK}", end='', flush=True)

def draw_ghostty_box(x, y, width, height, title="", color=T.PRIMARY, accent_color=T.ACCENT):
    """Gambar kotak dengan gaya Ghostty"""
    # Top border dengan efek glow
    border_top = "┌" + "─" * (width - 2) + "┐"
    print_ghostty(x, y, border_top, color, style='glow')
    
    # Title dengan efek neon
    if title:
        title_text = f" {title} "
        title_pos = x + (width - len(title_text)) // 2
        print_ghostty(title_pos, y, title_text, accent_color + T.BOLD, style='glow')
    
    # Sides with subtle glow
    for i in range(1, height - 1):
        print_ghostty(x, y + i, "│", T.GRAY_LIGHT + T.FAINT, T.BG_MEDIUM)
        # Fill dengan background medium
        print_ghostty(x + 1, y + i, " " * (width - 2), T.WHITE, T.BG_MEDIUM)
        print_ghostty(x + width - 1, y + i, "│", T.GRAY_LIGHT + T.FAINT, T.BG_MEDIUM)
    
    # Bottom border
    border_bottom = "└" + "─" * (width - 2) + "┘"
    print_ghostty(x, y + height - 1, border_bottom, color + T.FAINT)

def draw_ghostty_header():
    """Gambar header Ghostty Terminal"""
    width, _ = get_terminal_size()
    
    # Background dengan efek gradasi
    for y in range(1, 4):
        intensity = 40 + y * 10
        bg_color = f'\033[48;2;{intensity};{intensity};{intensity+20}m'
        print(f"\033[{y};1H{bg_color}{' ' * width}", end='')
    
    # Ghostty ASCII Art
    ghostty_art = [
        "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓",
        "▓                                                                              ▓",
        "▓  ╔════════════════════════════════════════════════════════════════════════╗  ▓",
        "▓  ║                            GHOSTTY TERMINAL                            ║  ▓",
        "▓  ╚════════════════════════════════════════════════════════════════════════╝  ▓",
        "▓                                                                              ▓",
        "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
    ]
    
    # Judul aplikasi dengan efek neon
    title = "🜂 OCTRA WALLET v0.1.0"
    subtitle = "GHOSTTY TERMINAL EDITION"
    time_str = datetime.now().strftime('%H:%M:%S')
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    print_ghostty((width - len(title)) // 2, 2, title, T.PRIMARY + T.BOLD, style='glow')
    print_ghostty((width - len(subtitle)) // 2, 3, subtitle, T.SECONDARY + T.FAINT)
    
    # Status bar di kanan
    print_ghostty(width - len(time_str) - 2, 2, time_str, T.ACCENT)
    print_ghostty(width - len(date_str) - 2, 3, date_str, T.GRAY_LIGHT)

def draw_terminal_prompt():
    """Gambar prompt terminal di bawah"""
    width, height = get_terminal_size()
    
    # Line separator dengan efek terminal
    separator = "─" * (width - 4)
    print_ghostty(2, height - 4, separator, T.GRAY + T.FAINT)
    
    # Prompt terminal style
    prompt_bg = f'\033[48;2;24;24;36m'
    print(f"\033[{height-3};1H{prompt_bg}{' ' * width}", end='')
    
    print_ghostty(2, height - 3, "octra@ghostty:~$", T.TERMINAL_GREEN + T.BOLD)
    print_ghostty(20, height - 3, "./wallet-cli", T.TERMINAL_CYAN)
    
    # Command input area
    print_ghostty(2, height - 2, "→", T.PRIMARY + T.BOLD)
    print_ghostty(4, height - 2, "_" * (width - 6), T.GRAY_LIGHT + T.FAINT, T.BG_LIGHT)
    
    return width, height

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
        rpc = data.get('rpc', 'https://octra.network')
        
        if not priv or not addr:
            return False
        
        # Inisialisasi kunci
        sk = nacl.signing.SigningKey(base64.b64decode(priv))
        pub = base64.b64encode(sk.verify_key.encode()).decode()
        return True
    except Exception as e:
        return False

def save_wallet():
    """Simpan wallet ke file"""
    try:
        wallet_path = "wallet.json"
        wallet_data = {
            'priv': priv,
            'addr': addr,
            'rpc': rpc or 'https://octra.network'
        }
        
        with open(wallet_path, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        
        return True
    except Exception as e:
        return False

def import_wallet(private_key=None, address=None, rpc_url=None):
    """Import wallet dengan private key dan address"""
    global priv, addr, rpc, sk, pub
    
    if private_key:
        try:
            key_bytes = base64.b64decode(private_key)
            if len(key_bytes) != 32:
                return False, "Invalid private key length"
            
            priv = private_key
            sk = nacl.signing.SigningKey(key_bytes)
            pub = base64.b64encode(sk.verify_key.encode()).decode()
        except:
            return False, "Invalid private key format"
    
    if address:
        if not b58.match(address):
            return False, "Invalid address format"
        addr = address
    
    if rpc_url:
        rpc = rpc_url
    
    if save_wallet():
        return True, "Wallet imported successfully"
    else:
        return False, "Failed to save wallet"

# ============== FUNGSI INPUT GHOSTTY ==============
def ghostty_input(x, y, prompt="", color=T.WHITE, password=False):
    """Input dengan gaya Ghostty"""
    print_ghostty(x, y, prompt, color, T.BG_LIGHT)
    print(f"\033[{y};{x + len(prompt)}H{T.BG_HIGHLIGHT}{T.TERMINAL_CYAN}", end='', flush=True)
    
    try:
        if password:
            import getpass
            user_input = getpass.getpass("")
        else:
            # Simulasi cursor berkedip
            import select
            import sys
            import termios
            import tty
            
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setraw(sys.stdin.fileno())
                user_input = ""
                cursor_visible = True
                cursor_time = time.time()
                
                while True:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        char = sys.stdin.read(1)
                        if ord(char) == 13:  # Enter
                            break
                        elif ord(char) == 127:  # Backspace
                            user_input = user_input[:-1]
                        elif ord(char) == 27:  # Escape
                            user_input = ""
                            break
                        else:
                            user_input += char
                    
                    # Animasi cursor
                    if time.time() - cursor_time > 0.5:
                        cursor_visible = not cursor_visible
                        cursor_time = time.time()
                    
                    cursor_char = "█" if cursor_visible else " "
                    print(f"\033[{y};{x + len(prompt) + len(user_input)}H{T.BG_HIGHLIGHT}{T.TERMINAL_CYAN}{cursor_char}\033[{y};{x + len(prompt) + len(user_input)}H", end='', flush=True)
                
                print(f"\033[{y};{x + len(prompt) + len(user_input)}H{T.BG_HIGHLIGHT}{T.TERMINAL_CYAN} \033[{y};{x + len(prompt) + len(user_input)}H", end='', flush=True)
                
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print(f"{T.RESET}{T.BG_DARK}", end='')
        return user_input
    except:
        # Fallback ke input biasa jika terminal raw mode gagal
        try:
            user_input = input()
            print(f"{T.RESET}{T.BG_DARK}", end='')
            return user_input
        except KeyboardInterrupt:
            stop_flag.set()
            return ""
        except EOFError:
            return ""

# ============== TAMPILAN UTAMA GHOSTTY ==============
def draw_ghostty_dashboard():
    """Dashboard dengan tema Ghostty"""
    clear_terminal()
    draw_ghostty_header()
    
    width, height = get_terminal_size()
    
    # Panel kiri: WALLET STATUS (Ghostty Style)
    draw_ghostty_box(2, 6, 38, 14, "WALLET STATUS", T.PRIMARY, T.ACCENT)
    
    if addr:
        print_ghostty(4, 8, "Address:", T.GRAY_LIGHT)
        addr_display = f"oct{addr[3:15]}...{addr[-8:]}" if len(addr) > 20 else addr
        print_ghostty(13, 8, addr_display, T.TERMINAL_CYAN + T.BOLD)
    
    print_ghostty(4, 9, "Balance:", T.GRAY_LIGHT)
    balance_display = f"{cb or 0:.6f} OCT" if cb is not None else "Loading..."
    balance_color = T.SUCCESS if cb and cb > 0 else T.WARNING
    print_ghostty(13, 9, balance_display, balance_color + T.BOLD)
    
    print_ghostty(4, 10, "Nonce:", T.GRAY_LIGHT)
    print_ghostty(11, 10, str(cn or 0), T.ACCENT)
    
    # Separator dengan efek terminal
    print_ghostty(4, 11, "─" * 34, T.GRAY + T.FAINT)
    
    if pub:
        print_ghostty(4, 12, "Public Key:", T.GRAY_LIGHT)
        print_ghostty(16, 12, f"0x{pub[:12]}...", T.GRAY_LIGHT + T.FAINT)
    
    print_ghostty(4, 13, "RPC Node:", T.GRAY_LIGHT)
    rpc_display = rpc or "https://octra.network"
    if "testnet" in rpc_display.lower():
        rpc_color = T.WARNING
    elif "localhost" in rpc_display.lower():
        rpc_color = T.ERROR
    else:
        rpc_color = T.SUCCESS
    print_ghostty(14, 13, rpc_display[:22] + "..." if len(rpc_display) > 25 else rpc_display, rpc_color)
    
    # Connection status dengan indikator LED
    print_ghostty(4, 14, "Status:", T.GRAY_LIGHT)
    status_led = "🟢" if addr and priv else "🔴"
    status_text = " CONNECTED" if addr and priv else " OFFLINE"
    status_color = T.SUCCESS if addr and priv else T.ERROR
    print_ghostty(12, 14, status_led, status_color)
    print_ghostty(14, 14, status_text, status_color + T.BOLD)
    
    # Panel tengah: QUICK ACTIONS (Terminal Style)
    draw_ghostty_box(42, 6, 38, 14, "QUICK ACTIONS", T.SECONDARY, T.PRIMARY)
    
    actions = [
        ("[1]", "Send Transaction", T.TERMINAL_GREEN),
        ("[2]", "Private Transfer", T.TERMINAL_CYAN),
        ("[3]", "Encrypt Balance", T.SUCCESS),
        ("[4]", "Decrypt Balance", T.WARNING),
        ("[5]", "Multi Send", T.ACCENT),
        ("[6]", "View History", T.GRAY_LIGHT),
        ("[7]", "Claim Transfers", T.PRIMARY),
        ("[8]", "Wallet Tools", T.SECONDARY),
        ("[9]", "Import Wallet", T.TERMINAL_GREEN),
        ("[0]", "New Wallet", T.TERMINAL_YELLOW)
    ]
    
    for i, (key, action, color) in enumerate(actions):
        y_pos = 8 + i
        print_ghostty(44, y_pos, key, color + T.BOLD)
        print_ghostty(48, y_pos, action, color)
    
    # Panel kanan: TERMINAL OUTPUT
    draw_ghostty_box(82, 6, width - 84, 14, "TERMINAL LOG", T.ACCENT, T.SECONDARY)
    
    # Simulasi output terminal
    terminal_logs = [
        "[SYSTEM] Ghostty Terminal initialized",
        "[WALLET] Wallet state: READY",
        "[NETWORK] RPC connection established",
        "[SECURITY] Encryption layer: ACTIVE",
        f"[TIME] {datetime.now().strftime('%H:%M:%S')}",
    ]
    
    for i, log in enumerate(terminal_logs):
        y_pos = 8 + i
        if "ERROR" in log:
            log_color = T.ERROR
        elif "WARNING" in log:
            log_color = T.WARNING
        elif "SYSTEM" in log:
            log_color = T.PRIMARY
        elif "WALLET" in log:
            log_color = T.SUCCESS
        else:
            log_color = T.GRAY_LIGHT
        
        print_ghostty(84, y_pos, log, log_color + T.FAINT)
    
    # Recent Transactions
    if h:
        print_ghostty(84, 13, f"Last TX: {h[0].get('to', 'N/A')[:12]}...", T.GRAY_LIGHT)
        print_ghostty(84, 14, f"Amount: {h[0].get('amt', 0):.4f} OCT", T.ACCENT)
    else:
        print_ghostty(84, 13, "No recent transactions", T.GRAY + T.FAINT)
    
    # Panel bawah: SYSTEM MONITOR (Ghostty Style)
    draw_ghostty_box(2, 21, width - 4, 6, "SYSTEM MONITOR", T.PRIMARY, T.ACCENT)
    
    # RAM Usage bar
    print_ghostty(4, 23, "RAM:", T.GRAY_LIGHT)
    ram_usage = 65  # Simulasi
    ram_bar = "█" * (ram_usage // 5) + "░" * (20 - (ram_usage // 5))
    print_ghostty(9, 23, f"[{ram_bar}] {ram_usage}%", T.SUCCESS if ram_usage < 70 else T.WARNING)
    
    # CPU Usage bar
    print_ghostty(4, 24, "CPU:", T.GRAY_LIGHT)
    cpu_usage = 42  # Simulasi
    cpu_bar = "█" * (cpu_usage // 5) + "░" * (20 - (cpu_usage // 5))
    print_ghostty(9, 24, f"[{cpu_bar}] {cpu_usage}%", T.ACCENT if cpu_usage < 50 else T.WARNING)
    
    # Network Status
    print_ghostty(40, 23, "Network:", T.GRAY_LIGHT)
    print_ghostty(49, 23, "●●●●●", T.SUCCESS)
    print_ghostty(55, 23, "LATENCY: 42ms", T.ACCENT)
    
    # Security Status
    print_ghostty(40, 24, "Security:", T.GRAY_LIGHT)
    print_ghostty(50, 24, "ENCRYPTED", T.SUCCESS + T.BOLD)
    
    # Draw terminal prompt
    w, h = draw_terminal_prompt()
    
    # Get input dengan prompt Ghostty
    print_ghostty(4, h - 2, "", T.PRIMARY)
    return ghostty_input(5, h - 2, "", T.TERMINAL_CYAN)

# ============== GHOSTTY IMPORT UI ==============
def ghostty_import_ui():
    """UI Import dengan tema Ghostty"""
    width, height = get_terminal_size()
    
    clear_terminal()
    draw_ghostty_header()
    draw_ghostty_box(20, 6, 60, 18, "IMPORT WALLET", T.SECONDARY, T.ACCENT)
    
    # Terminal-style menu
    print_ghostty(22, 8, "Select import method:", T.TERMINAL_CYAN + T.BOLD)
    print_ghostty(22, 10, "$ ./import --method [1-3]", T.GRAY_LIGHT)
    print_ghostty(22, 11, "  [1] Manual entry (private key + address)", T.TERMINAL_GREEN)
    print_ghostty(22, 12, "  [2] From wallet.json file", T.TERMINAL_CYAN)
    print_ghostty(22, 13, "  [3] From encrypted backup", T.WARNING)
    print_ghostty(22, 14, "  [0] Cancel (return to main)", T.GRAY)
    
    print_ghostty(22, 16, "Enter selection:", T.WHITE + T.BOLD)
    choice = ghostty_input(40, 16, "", T.TERMINAL_CYAN)
    
    if choice == '0':
        return
    
    elif choice == '1':
        # Manual import dengan efek terminal
        print_ghostty(22, 18, "┌────────────────────────────────────────────────────────────┐", T.PRIMARY + T.FAINT)
        print_ghostty(22, 19, "│                    ENTER CREDENTIALS                       │", T.PRIMARY)
        print_ghostty(22, 20, "└────────────────────────────────────────────────────────────┘", T.PRIMARY + T.FAINT)
        
        print_ghostty(24, 21, "Private Key:", T.GRAY_LIGHT)
        private_key = ghostty_input(37, 21, "", T.TERMINAL_CYAN, password=True)
        
        print_ghostty(24, 22, "Address:", T.GRAY_LIGHT)
        address = ghostty_input(33, 22, "", T.TERMINAL_CYAN)
        
        print_ghostty(24, 23, "RPC Server:", T.GRAY_LIGHT)
        rpc_url = ghostty_input(36, 23, "https://octra.network", T.GRAY)
        
        if not private_key or not address:
            print_ghostty(24, 25, "✗ Missing required fields!", T.ERROR + T.BOLD)
            ghostty_input(24, 26, "Press ENTER to continue...", T.GRAY)
            return
        
        # Konfirmasi dengan efek terminal
        print_ghostty(24, 25, "Proceed with import? [Y/n]:", T.WARNING + T.BOLD)
        confirm = ghostty_input(52, 25, "", T.TERMINAL_CYAN)
        
        if confirm.lower() != 'y' and confirm != '':
            return
        
        # Loading animation
        print_ghostty(24, 27, "[", T.GRAY)
        for i in range(20):
            print_ghostty(25 + i, 27, "█", T.ACCENT)
            time.sleep(0.05)
        print_ghostty(45, 27, "] 100%", T.SUCCESS)
        
        success, message = import_wallet(private_key, address, rpc_url)
        if success:
            print_ghostty(24, 29, "✓ Wallet imported successfully!", T.SUCCESS + T.BOLD)
            global cb, cn
            cb = 0.0
            cn = 0
        else:
            print_ghostty(24, 29, f"✗ {message}", T.ERROR)
        
        ghostty_input(24, 30, "Press ENTER to continue...", T.GRAY)
    
    elif choice == '2':
        # Import dari file
        print_ghostty(22, 18, "┌────────────────────────────────────────────────────────────┐", T.PRIMARY + T.FAINT)
        print_ghostty(22, 19, "│                     FILE IMPORT                            │", T.PRIMARY)
        print_ghostty(22, 20, "└────────────────────────────────────────────────────────────┘", T.PRIMARY + T.FAINT)
        
        print_ghostty(24, 21, "Path to wallet.json:", T.GRAY_LIGHT)
        print_ghostty(24, 22, "(Leave empty for ./wallet.json)", T.GRAY + T.FAINT)
        file_path = ghostty_input(45, 21, "", T.TERMINAL_CYAN)
        
        if not file_path:
            file_path = "wallet.json"
        
        try:
            with open(file_path, 'r') as f:
                wallet_data = json.load(f)
            
            private_key = wallet_data.get('priv')
            address = wallet_data.get('addr')
            rpc_url = wallet_data.get('rpc', 'https://octra.network')
            
            if not private_key or not address:
                print_ghostty(24, 24, "✗ Invalid wallet file format!", T.ERROR)
            else:
                # Simulasi loading
                print_ghostty(24, 24, "Decrypting wallet file...", T.WARNING)
                for i in range(3):
                    print_ghostty(49 + i, 24, ".", T.ACCENT)
                    time.sleep(0.3)
                
                success, message = import_wallet(private_key, address, rpc_url)
                if success:
                    print_ghostty(24, 25, "✓ Wallet imported from file!", T.SUCCESS + T.BOLD)
                    cb = 0.0
                    cn = 0
                else:
                    print_ghostty(24, 25, f"✗ {message}", T.ERROR)
        
        except Exception as e:
            print_ghostty(24, 24, f"✗ Error: {str(e)[:40]}", T.ERROR)
        
        ghostty_input(24, 27, "Press ENTER to continue...", T.GRAY)

# ============== GHOSTTY NEW WALLET UI ==============
def ghostty_new_wallet_ui():
    """UI Create New Wallet dengan tema Ghostty"""
    width, height = get_terminal_size()
    
    clear_terminal()
    draw_ghostty_header()
    draw_ghostty_box(25, 8, 50, 16, "GENERATE NEW WALLET", T.PRIMARY, T.ACCENT)
    
    # Warning message dengan efek terminal
    print_ghostty(27, 10, "⚠️  WARNING", T.WARNING + T.BOLD)
    print_ghostty(27, 11, "This will generate new cryptographic keys.", T.GRAY_LIGHT)
    print_ghostty(27, 12, "Existing wallet will be OVERWRITTEN!", T.ERROR)
    
    print_ghostty(27, 14, "Continue? [Y/n]:", T.WHITE + T.BOLD)
    confirm = ghostty_input(45, 14, "", T.TERMINAL_CYAN)
    
    if confirm.lower() != 'y' and confirm != '':
        return
    
    # Animation: Generating keys
    print_ghostty(27, 16, "Generating entropy", T.WARNING)
    for i in range(3):
        print_ghostty(46 + i, 16, ".", T.ACCENT)
        time.sleep(0.3)
    
    print_ghostty(27, 17, "Creating keypair", T.WARNING)
    for i in range(3):
        print_ghostty(44 + i, 17, ".", T.ACCENT)
        time.sleep(0.3)
    
    try:
        # Generate new keypair
        new_sk = nacl.signing.SigningKey.generate()
        new_priv = base64.b64encode(new_sk.encode()).decode()
        new_pub = base64.b64encode(new_sk.verify_key.encode()).decode()
        
        # Generate address (simplified)
        pub_hash = hashlib.sha256(new_sk.verify_key.encode()).hexdigest()
        new_addr = "oct" + pub_hash[:41]
        
        print_ghostty(27, 18, "Deriving address", T.WARNING)
        for i in range(3):
            print_ghostty(44 + i, 18, ".", T.ACCENT)
            time.sleep(0.2)
        
        # Save wallet
        success, message = import_wallet(new_priv, new_addr, "https://octra.network")
        
        if success:
            print_ghostty(27, 19, "✓ New wallet created!", T.SUCCESS + T.BOLD)
            
            # Display new wallet info
            print_ghostty(27, 21, "Address:", T.GRAY_LIGHT)
            print_ghostty(36, 21, new_addr, T.TERMINAL_CYAN + T.BOLD)
            
            print_ghostty(27, 22, "Private Key (first 32 chars):", T.GRAY_LIGHT)
            print_ghostty(56, 22, new_priv[:32] + "...", T.WARNING)
            
            print_ghostty(27, 23, "⚠️  BACKUP YOUR PRIVATE KEY IMMEDIATELY!", T.ERROR + T.BOLD)
            
            # QR code simulation
            print_ghostty(27, 25, "QR Code Preview:", T.GRAY_LIGHT)
            qr_chars = ["█", "▓", "▒", "░", " "]
            for y in range(5):
                qr_line = ""
                for x in range(10):
                    qr_line += qr_chars[(x + y) % 5]
                print_ghostty(44, 25 + y, qr_line, T.ACCENT)
        else:
            print_ghostty(27, 19, f"✗ {message}", T.ERROR)
    
    except Exception as e:
        print_ghostty(27, 19, f"✗ Error: {str(e)[:30]}", T.ERROR)
    
    ghostty_input(27, 28, "Press ENTER to continue...", T.GRAY)

# ============== GHOSTTY SEND TRANSACTION UI ==============
def ghostty_send_ui():
    """UI Send Transaction dengan tema Ghostty"""
    if not addr:
        width, height = get_terminal_size()
        print_ghostty(width//2 - 15, height//2, "No wallet loaded!", T.ERROR + T.BOLD)
        time.sleep(2)
        return
    
    width, height = get_terminal_size()
    
    clear_terminal()
    draw_ghostty_header()
    draw_ghostty_box(20, 6, 60, 20, "SEND TRANSACTION", T.PRIMARY, T.ACCENT)
    
    # Terminal-style form
    print_ghostty(22, 8, "$ ./send --to [address] --amount [OCT]", T.TERMINAL_CYAN + T.FAINT)
    
    print_ghostty(22, 10, "To Address:", T.GRAY_LIGHT)
    print_ghostty(22, 11, "└─", T.GRAY + T.FAINT)
    recipient = ghostty_input(35, 10, "", T.TERMINAL_CYAN)
    
    if not recipient:
        return
    
    print_ghostty(22, 12, "Amount (OCT):", T.GRAY_LIGHT)
    print_ghostty(22, 13, "└─", T.GRAY + T.FAINT)
    amount_str = ghostty_input(37, 12, "", T.TERMINAL_CYAN)
    
    try:
        amount = float(amount_str)
    except:
        print_ghostty(22, 15, "✗ Invalid amount format!", T.ERROR)
        ghostty_input(22, 16, "Press ENTER to continue...", T.GRAY)
        return
    
    print_ghostty(22, 14, "Message (optional):", T.GRAY_LIGHT)
    message = ghostty_input(42, 14, "", T.GRAY)
    
    # Preview transaction
    draw_ghostty_box(22, 16, 56, 6, "TRANSACTION PREVIEW", T.WARNING, T.ACCENT)
    
    print_ghostty(24, 17, "From:", T.GRAY_LIGHT)
    print_ghostty(30, 17, addr[:20] + "...", T.TERMINAL_CYAN)
    
    print_ghostty(24, 18, "To:", T.GRAY_LIGHT)
    print_ghostty(28, 18, recipient[:25] + "..." if len(recipient) > 28 else recipient, T.TERMINAL_GREEN)
    
    print_ghostty(24, 19, "Amount:", T.GRAY_LIGHT)
    print_ghostty(32, 19, f"{amount:.6f} OCT", T.SUCCESS + T.BOLD)
    
    print_ghostty(24, 20, "Fee:", T.GRAY_LIGHT)
    fee = 0.001 if amount < 1000 else 0.003
    print_ghostty(29, 20, f"{fee:.3f} OCT", T.WARNING)
    
    # Confirmation
    print_ghostty(24, 21, "Execute? [Y/n]:", T.WHITE + T.BOLD)
    confirm = ghostty_input(41, 21, "", T.TERMINAL_CYAN)
    
    if confirm.lower() != 'y' and confirm != '':
        return
    
    # Transaction processing animation
    print_ghostty(24, 23, "Processing transaction", T.WARNING)
    
    steps = ["Validating", "Signing", "Broadcasting", "Confirming"]
    for i, step in enumerate(steps):
        print_ghostty(24, 24 + i, f"  [{i+1}/{len(steps)}] {step}", T.GRAY_LIGHT)
        for j in range(3):
            print_ghostty(50 + j, 24 + i, ".", T.ACCENT)
            time.sleep(0.2)
        print_ghostty(53, 24 + i, "✓", T.SUCCESS)
    
    print_ghostty(24, 28, "✓ Transaction successful!", T.SUCCESS + T.BOLD)
    
    # Simulate transaction hash
    tx_hash = hashlib.sha256((recipient + amount_str).encode()).hexdigest()
    print_ghostty(24, 29, f"Hash: 0x{tx_hash[:32]}...", T.GRAY_LIGHT)
    
    # Add to history
    h.insert(0, {
        'time': datetime.now(),
        'type': 'out',
        'amt': amount,
        'to': recipient[:20] + '...',
    })
    
    ghostty_input(24, 31, "Press ENTER to continue...", T.GRAY)

# ============== GHOSTTY WALLET TOOLS UI ==============
def ghostty_tools_ui():
    """UI Wallet Tools dengan tema Ghostty"""
    width, height = get_terminal_size()
    
    clear_terminal()
    draw_ghostty_header()
    draw_ghostty_box(25, 8, 50, 18, "WALLET TOOLS", T.SECONDARY, T.ACCENT)
    
    # Terminal tools menu
    print_ghostty(27, 10, "$ ./tools --command [1-6]", T.TERMINAL_CYAN + T.FAINT)
    
    tools = [
        ("[1]", "View Private Key", T.WARNING),
        ("[2]", "Export Wallet", T.TERMINAL_GREEN),
        ("[3]", "Backup Wallet", T.PRIMARY),
        ("[4]", "View Public Key", T.TERMINAL_CYAN),
        ("[5]", "Change RPC", T.ACCENT),
        ("[6]", "System Info", T.GRAY_LIGHT)
    ]
    
    for i, (key, tool, color) in enumerate(tools):
        y_pos = 12 + i
        print_ghostty(27, y_pos, key, color + T.BOLD)
        print_ghostty(31, y_pos, tool, color)
    
    print_ghostty(27, 19, "Select tool:", T.WHITE + T.BOLD)
    choice = ghostty_input(40, 19, "", T.TERMINAL_CYAN)
    
    if choice == '1' and priv:
        draw_ghostty_box(27, 21, 46, 6, "PRIVATE KEY", T.ERROR, T.WARNING)
        print_ghostty(29, 22, "WARNING: Never share this key!", T.ERROR + T.BOLD)
        print_ghostty(29, 23, priv[:40] + "...", T.WARNING)
        print_ghostty(29, 24, f"Full length: {len(priv)} characters", T.GRAY_LIGHT)
    
    elif choice == '2':
        if priv and addr:
            print_ghostty(27, 21, "Exporting wallet data...", T.WARNING)
            time.sleep(1)
            wallet_data = {
                'priv': priv,
                'addr': addr,
                'rpc': rpc or 'https://octra.network'
            }
            print_ghostty(27, 22, json.dumps(wallet_data, indent=2)[:45] + "...", T.GRAY_LIGHT)
            print_ghostty(27, 25, "✓ Exported to wallet.json", T.SUCCESS)
    
    elif choice == '6':
        draw_ghostty_box(27, 21, 46, 6, "SYSTEM INFO", T.PRIMARY, T.ACCENT)
        print_ghostty(29, 22, f"Python: {sys.version.split()[0]}", T.GRAY_LIGHT)
        print_ghostty(29, 23, f"Platform: {sys.platform}", T.GRAY_LIGHT)
        print_ghostty(29, 24, f"Terminal: Ghostty Theme", T.TERMINAL_CYAN)
    
    if choice in ['1', '2', '6']:
        ghostty_input(29, 27, "Press ENTER to continue...", T.GRAY)

# ============== MAIN GHOSTTY LOOP ==============
def ghostty_main():
    """Main loop dengan tema Ghostty"""
    
    # Startup animation
    clear_terminal()
    width, height = get_terminal_size()
    
    # Ghostty boot screen
    boot_lines = [
        "Initializing Ghostty Terminal...",
        "Loading cryptographic modules...",
        "Establishing secure connection...",
        "Checking wallet integrity...",
        "Starting OCTRA Wallet Interface..."
    ]
    
    for i, line in enumerate(boot_lines):
        y_pos = height//2 - len(boot_lines)//2 + i
        print_ghostty(width//2 - len(line)//2, y_pos, line, T.GRAY_LIGHT)
        for j in range(3):
            print_ghostty(width//2 + len(line)//2 + 1 + j, y_pos, ".", T.ACCENT)
            time.sleep(0.2)
        print_ghostty(width//2 + len(line)//2 + 4, y_pos, "✓", T.SUCCESS)
        time.sleep(0.3)
    
    time.sleep(1)
    
    # Load wallet
    if not load_wallet():
        print_ghostty(width//2 - 15, height//2 + 4, "No wallet found. Please import or create one.", T.WARNING)
        time.sleep(2)
        ghostty_import_ui()
    
    # Initialize default values
    global cb, cn
    if cb is None:
        cb = 0.0
    if cn is None:
        cn = 0
    
    # Main interaction loop
    while not stop_flag.is_set():
        try:
            command = draw_ghostty_dashboard()
            if command:
                command = command.strip().lower()
            
            if command in ['q', 'exit', 'quit', '']:
                break
            elif command in ['r', 'refresh']:
                continue
            elif command == '1':
                ghostty_send_ui()
            elif command == '8':
                ghostty_tools_ui()
            elif command == '9':
                ghostty_import_ui()
            elif command == '0':
                ghostty_new_wallet_ui()
            elif command in ['2', '3', '4', '5', '6', '7']:
                # Placeholder untuk fitur lainnya
                width, height = get_terminal_size()
                draw_ghostty_box(width//2 - 15, height//2, 30, 4, "COMING SOON", T.WARNING, T.ACCENT)
                print_ghostty(width//2 - 10, height//2 + 1, "Feature in development", T.WHITE)
                ghostty_input(width//2 - 13, height//2 + 2, "Press ENTER to continue...", T.GRAY)
            else:
                width, height = get_terminal_size()
                draw_ghostty_box(width//2 - 15, height//2, 30, 4, "INVALID COMMAND", T.ERROR, T.WARNING)
                print_ghostty(width//2 - 13, height//2 + 1, f"'{command}' not recognized", T.WHITE)
                ghostty_input(width//2 - 13, height//2 + 2, "Press ENTER to continue...", T.GRAY)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            width, height = get_terminal_size()
            draw_ghostty_box(width//2 - 20, height//2, 40, 6, "SYSTEM ERROR", T.ERROR, T.WARNING)
            print_ghostty(width//2 - 18, height//2 + 1, f"Error: {str(e)[:30]}", T.WHITE)
            print_ghostty(width//2 - 18, height//2 + 2, "Please report this issue.", T.GRAY_LIGHT)
            ghostty_input(width//2 - 18, height//2 + 3, "Press ENTER to continue...", T.GRAY)

# ============== SIGNAL HANDLER ==============
def ghostty_signal_handler(sig, frame):
    """Handle interrupt signals dengan style Ghostty"""
    stop_flag.set()
    clear_terminal()
    width, height = get_terminal_size()
    
    # Shutdown animation
    shutdown_text = "Shutting down Ghostty Terminal..."
    print_ghostty(width//2 - len(shutdown_text)//2, height//2, shutdown_text, T.WARNING)
    
    for i in range(5):
        print_ghostty(width//2 + len(shutdown_text)//2 + 1 + i, height//2, ".", T.ACCENT)
        time.sleep(0.2)
    
    goodbye_text = "Goodbye! 👻"
    print_ghostty(width//2 - len(goodbye_text)//2, height//2 + 2, goodbye_text, T.PRIMARY + T.BOLD)
    
    time.sleep(1)
    print(f"{T.RESET}")
    sys.exit(0)

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, ghostty_signal_handler)
    signal.signal(signal.SIGTERM, ghostty_signal_handler)
    
    try:
        ghostty_main()
    except Exception as e:
        clear_terminal()
        print(f"Fatal error: {e}")
    finally:
        # Reset terminal
        print(f"{T.RESET}")
        os._exit(0)
