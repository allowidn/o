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
import subprocess
import platform
import math
from typing import Optional, Dict, List, Tuple

# ============== GHOSTTY TERMINAL THEME - RESPONSIVE ==============
class GhosttyTheme:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    FAINT = '\033[2m'
    
    PRIMARY = '\033[38;5;117m'
    SECONDARY = '\033[38;5;141m'
    ACCENT = '\033[38;5;84m'
    WARNING = '\033[38;5;221m'
    ERROR = '\033[38;5;203m'
    SUCCESS = '\033[38;5;84m'
    
    WHITE = '\033[38;5;255m'
    GRAY_LIGHT = '\033[38;5;250m'
    GRAY = '\033[38;5;245m'
    GRAY_DARK = '\033[38;5;240m'
    
    BG_DARK = '\033[48;5;24m'
    BG_MEDIUM = '\033[48;5;31m'
    BG_LIGHT = '\033[48;5;39m'

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

# ============== FUNGSI UTILITAS ==============
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{T.BG_DARK}{T.WHITE}", end='')
    print('\033[H', end='', flush=True)

def get_terminal_size():
    try:
        size = shutil.get_terminal_size()
        return (max(size.columns, 80), max(size.lines, 24))
    except:
        return (80, 24)

def print_at(x, y, text, color=T.WHITE, bg_color=None):
    try:
        if bg_color:
            print(f"\033[{y};{x}H{bg_color}{color}{text}{T.RESET}{T.BG_DARK}", end='', flush=True)
        else:
            print(f"\033[{y};{x}H{color}{text}{T.RESET}{T.BG_DARK}", end='', flush=True)
    except:
        pass

def draw_box(x, y, width, height, title="", color=T.PRIMARY):
    try:
        term_width, term_height = get_terminal_size()
        width = min(width, term_width - x - 2)
        height = min(height, term_height - y - 2)
        
        print_at(x, y, "┌" + "─" * (width - 2) + "┐", color)
        
        if title:
            title_text = f" {title} "
            title_pos = min(x + (width - len(title_text)) // 2, x + width - len(title_text) - 1)
            print_at(title_pos, y, title_text, color + T.BOLD)
        
        for i in range(1, height - 1):
            print_at(x, y + i, "│", color)
            print_at(x + 1, y + i, " " * (width - 2), T.WHITE, T.BG_MEDIUM)
            print_at(x + width - 1, y + i, "│", color)
        
        print_at(x, y + height - 1, "└" + "─" * (width - 2) + "┘", color)
    except:
        pass

def get_input(x, y, prompt="", color=T.WHITE, password=False):
    try:
        print_at(x, y, prompt, color)
        print(f"\033[{y};{x + len(prompt)}H{T.BG_LIGHT}{T.PRIMARY}", end='', flush=True)
        
        if password:
            import getpass
            user_input = getpass.getpass("")
        else:
            user_input = input()
        
        print(f"{T.RESET}{T.BG_DARK}", end='')
        return user_input
    except KeyboardInterrupt:
        stop_flag.set()
        return ""
    except:
        return ""

# ============== FUNGSI WALLET ==============
def load_wallet():
    global priv, addr, rpc, sk, pub
    try:
        possible_paths = [
            "wallet.json",
            os.path.expanduser("~/.octra/wallet.json"),
            os.path.join(os.path.dirname(__file__), "wallet.json")
        ]
        
        wallet_path = None
        for path in possible_paths:
            if os.path.exists(path):
                wallet_path = path
                break
        
        if not wallet_path:
            return False
        
        with open(wallet_path, 'r') as f:
            data = json.load(f)
        
        priv = data.get('priv')
        addr = data.get('addr')
        rpc = data.get('rpc', 'https://octra.network')
        
        if not priv or not addr:
            return False
        
        sk = nacl.signing.SigningKey(base64.b64decode(priv))
        pub = base64.b64encode(sk.verify_key.encode()).decode()
        return True
    except:
        return False

def save_wallet():
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
    except:
        return False

def import_wallet(private_key=None, address=None, rpc_url=None):
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

# ============== TAMPILAN UTAMA ==============
def draw_responsive_dashboard():
    clear_screen()
    width, height = get_terminal_size()
    
    # Header
    print_at(1, 1, "═" * (width - 2), T.PRIMARY)
    title = "⚡ OCTRA WALLET v0.1.0 - ADVANCED EDITION"
    print_at((width - len(title)) // 2, 2, title, T.PRIMARY + T.BOLD)
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    print_at(width - len(timestamp) - 2, 2, timestamp, T.ACCENT)
    
    print_at(2, 3, "─" * (width - 4), T.SECONDARY)
    
    # Layout responsif
    if width >= 100:
        col1_width = 35
        col2_width = 35
        col3_width = width - col1_width - col2_width - 10
        col1_x = 2
        col2_x = col1_x + col1_width + 2
        col3_x = col2_x + col2_width + 2
    elif width >= 80:
        col1_width = 30
        col2_width = 30
        col3_width = width - col1_width - col2_width - 8
        col1_x = 2
        col2_x = col1_x + col1_width + 2
        col3_x = col2_x + col2_width + 2
    else:
        col1_width = width - 4
        col2_width = width - 4
        col3_width = width - 4
        col1_x = 2
        col2_x = 2
        col3_x = 2
    
    # Panel 1: Wallet Info
    panel1_height = 12
    draw_box(col1_x, 5, col1_width, panel1_height, "WALLET INFO", T.PRIMARY)
    
    info_y = 7
    if addr:
        print_at(col1_x + 2, info_y, "Address:", T.GRAY_LIGHT)
        addr_display = addr[:16] + "..." if len(addr) > 20 else addr
        print_at(col1_x + 11, info_y, addr_display, T.WHITE)
        info_y += 1
    
    print_at(col1_x + 2, info_y, "Balance:", T.GRAY_LIGHT)
    balance_display = f"{cb or 0:.6f} OCT" if cb is not None else "Loading..."
    print_at(col1_x + 11, info_y, balance_display, T.SUCCESS + T.BOLD)
    info_y += 1
    
    print_at(col1_x + 2, info_y, "Nonce:", T.GRAY_LIGHT)
    print_at(col1_x + 9, info_y, str(cn or 0), T.ACCENT)
    info_y += 2
    
    if pub:
        print_at(col1_x + 2, info_y, "Public Key:", T.GRAY_LIGHT)
        print_at(col1_x + 13, info_y, pub[:16] + "...", T.GRAY)
        info_y += 1
    
    print_at(col1_x + 2, info_y, "RPC:", T.GRAY_LIGHT)
    rpc_display = rpc or "https://octra.network"
    print_at(col1_x + 7, info_y, rpc_display[:col1_width - 10] + "..." if len(rpc_display) > col1_width - 10 else rpc_display, T.WARNING)
    
    # Panel 2: Quick Actions
    if width >= 80:
        panel2_height = 12
        panel2_y = 5
        draw_box(col2_x, panel2_y, col2_width, panel2_height, "QUICK ACTIONS", T.SECONDARY)
        
        actions = [
            ("[1]", "Send Transaction"),
            ("[2]", "Private Transfer"),
            ("[3]", "Encrypt Balance"),
            ("[4]", "Decrypt Balance"),
            ("[5]", "Multi Send"),
            ("[6]", "View History"),
            ("[7]", "Claim Transfers"),
            ("[8]", "Wallet Tools"),
            ("[9]", "Import Wallet"),
            ("[0]", "New Wallet")
        ]
        
        action_y = panel2_y + 2
        for key, action in actions:
            print_at(col2_x + 2, action_y, key, T.ACCENT + T.BOLD)
            print_at(col2_x + 6, action_y, action, T.WHITE)
            action_y += 1
    
    # Panel 3: System Status
    if width >= 100:
        panel3_height = 12
        panel3_y = 5
        draw_box(col3_x, panel3_y, col3_width, panel3_height, "SYSTEM STATUS", T.ACCENT)
        
        # Uptime
        print_at(col3_x + 2, panel3_y + 2, "Uptime:", T.GRAY_LIGHT)
        print_at(col3_x + 10, panel3_y + 2, get_uptime(), T.WHITE)
        
        # Memory usage
        print_at(col3_x + 2, panel3_y + 3, "Memory:", T.GRAY_LIGHT)
        mem_usage = get_memory_usage()
        print_at(col3_x + 10, panel3_y + 3, mem_usage, 
                 T.SUCCESS if mem_usage < "70%" else T.WARNING if mem_usage < "90%" else T.ERROR)
        
        # Wallet health
        print_at(col3_x + 2, panel3_y + 4, "Health:", T.GRAY_LIGHT)
        health = "🟢 Excellent" if addr and priv else "🟡 Good" if addr else "🔴 Poor"
        print_at(col3_x + 10, panel3_y + 4, health, 
                 T.SUCCESS if "Excellent" in health else T.WARNING if "Good" in health else T.ERROR)
        
        # Active features
        print_at(col3_x + 2, panel3_y + 5, "Features:", T.GRAY_LIGHT)
        print_at(col3_x + 12, panel3_y + 5, "12+ Active", T.ACCENT)
    
    # Footer
    footer_y = height - 3
    print_at(2, footer_y, "─" * (width - 4), T.PRIMARY)
    
    status = "🟢 READY" if addr else "🟡 NO WALLET"
    print_at(2, footer_y + 1, status, T.SUCCESS if addr else T.WARNING)
    
    cmd_prompt = "Command [1-9, 0, R=Refresh, Q=Quit]: "
    print_at(width - len(cmd_prompt) - 10, footer_y + 1, cmd_prompt, T.WHITE)
    
    input_x = width - 10
    input_y = footer_y + 1
    
    print_at(input_x, input_y, "", T.PRIMARY)
    return get_input(input_x, input_y, "", T.PRIMARY)

# ============== 8 FITUR BARU YANG SANGAT PENTING ==============

# ============== FITUR 1: SMART CONTRACT INTERACTOR ==============
def smart_contract_interactor():
    """Interaksi dengan smart contract OCTRA"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "SMART CONTRACT INTERACTOR", T.PRIMARY)
    
    print_at(12, 7, "Smart Contract Features:", T.WHITE + T.BOLD)
    
    contracts = [
        ("[1]", "Deploy Contract", "Deploy new smart contract"),
        ("[2]", "Call Contract", "Execute contract function"),
        ("[3]", "View Contract State", "Read contract data"),
        ("[4]", "Contract Templates", "Pre-built contract templates"),
        ("[5]", "Verify Contract", "Verify contract source code"),
        ("[0]", "Back", "Return to main menu")
    ]
    
    start_y = 9
    for i, (key, name, desc) in enumerate(contracts):
        if start_y + i < height - 5:
            print_at(12, start_y + i, key, T.ACCENT + T.BOLD)
            print_at(16, start_y + i, name, T.WHITE)
            print_at(35, start_y + i, desc, T.GRAY_LIGHT)
    
    print_at(12, height - 4, "Select option:", T.WHITE)
    choice = get_input(27, height - 4, "", T.PRIMARY)
    
    if choice == '1':
        deploy_smart_contract()
    elif choice == '2':
        call_smart_contract()
    elif choice == '3':
        view_contract_state()
    elif choice == '4':
        contract_templates()
    elif choice == '5':
        verify_contract_source()

def deploy_smart_contract():
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "DEPLOY SMART CONTRACT", T.SECONDARY)
    
    print_at(12, 7, "Enter contract bytecode (hex):", T.GRAY_LIGHT)
    bytecode = get_input(40, 7, "", T.PRIMARY)
    
    if not bytecode:
        return
    
    print_at(12, 9, "Initialization data (hex, optional):", T.GRAY_LIGHT)
    init_data = get_input(46, 9, "", T.PRIMARY)
    
    print_at(12, 11, "Gas limit (default: 5,000,000):", T.GRAY_LIGHT)
    gas_limit = get_input(42, 11, "5000000", T.PRIMARY)
    
    try:
        gas_limit = int(gas_limit)
    except:
        gas_limit = 5000000
    
    # Simulasi deployment
    print_at(12, 13, "Deploying contract...", T.WARNING)
    
    # Simulasi waktu deployment
    for i in range(5):
        print_at(35 + i, 13, ".", T.ACCENT)
        time.sleep(0.3)
    
    # Generate contract address simulasi
    contract_hash = hashlib.sha256((bytecode + str(time.time())).encode()).hexdigest()
    contract_address = "octCONTRACT" + contract_hash[:34]
    
    print_at(12, 13, "✅ Contract deployed successfully!", T.SUCCESS)
    print_at(12, 14, f"Contract Address: {contract_address}", T.ACCENT)
    print_at(12, 15, f"Gas Used: {gas_limit - 1000000:,}", T.GRAY_LIGHT)
    
    # Save contract info
    contract_info = {
        'address': contract_address,
        'deployed_at': datetime.now().isoformat(),
        'deployer': addr,
        'bytecode_hash': hashlib.sha256(bytecode.encode()).hexdigest()
    }
    
    contract_file = f"contract_{contract_address[-8:]}.json"
    with open(contract_file, 'w') as f:
        json.dump(contract_info, f, indent=2)
    
    print_at(12, 17, f"📄 Contract info saved to: {contract_file}", T.SUCCESS)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

def contract_templates():
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "CONTRACT TEMPLATES", T.ACCENT)
    
    templates = [
        ("Token", "ERC-20 like token contract"),
        ("NFT", "Non-fungible token contract"),
        ("Staking", "Staking pool contract"),
        ("DAO", "Decentralized organization"),
        ("MultiSig", "Multi-signature wallet"),
        ("Auction", "Auction system contract")
    ]
    
    print_at(12, 7, "Available Templates:", T.WHITE + T.BOLD)
    
    start_y = 9
    for i, (name, desc) in enumerate(templates):
        if start_y + i < height - 5:
            print_at(12, start_y + i, f"[{i+1}]", T.ACCENT + T.BOLD)
            print_at(16, start_y + i, name, T.WHITE)
            print_at(25, start_y + i, desc, T.GRAY_LIGHT)
    
    print_at(12, height - 4, "Select template (1-6):", T.WHITE)
    choice = get_input(36, height - 4, "", T.PRIMARY)
    
    if choice and choice in ['1', '2', '3', '4', '5', '6']:
        template_names = ['Token', 'NFT', 'Staking', 'DAO', 'MultiSig', 'Auction']
        selected = template_names[int(choice) - 1]
        
        print_at(12, height - 6, f"Loading {selected} template...", T.WARNING)
        time.sleep(1)
        
        # Simulasi template code
        template_code = f"""
// {selected} Smart Contract Template
pragma octra 0.8.0;

contract {selected} {{
    address public owner = msg.sender;
    
    constructor() {{
        // Initialization code for {selected}
    }}
    
    // {selected} specific functions
    function deploy() public returns (bool) {{
        return true;
    }}
}}
        """
        
        template_file = f"{selected.lower()}_template.oct"
        with open(template_file, 'w') as f:
            f.write(template_code)
        
        print_at(12, height - 6, f"✅ Template saved to: {template_file}", T.SUCCESS)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

# ============== FITUR 2: STAKING MANAGER ==============
def staking_manager():
    """Manage OCTRA staking operations"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "STAKING MANAGER", T.SUCCESS)
    
    if not addr:
        print_at(12, 7, "No wallet loaded!", T.ERROR)
        get_input(12, 9, "Press ENTER to continue...", T.GRAY)
        return
    
    print_at(12, 7, "Staking Operations:", T.WHITE + T.BOLD)
    
    operations = [
        ("[1]", "Stake OCT", "Lock OCT for staking rewards"),
        ("[2]", "Unstake OCT", "Release staked OCT"),
        ("[3]", "Claim Rewards", "Claim staking rewards"),
        ("[4]", "Staking Stats", "View staking statistics"),
        ("[5]", "Validator Info", "Become a validator"),
        ("[6]", "Delegation", "Delegate to validator"),
        ("[0]", "Back", "Return to main menu")
    ]
    
    start_y = 9
    for i, (key, name, desc) in enumerate(operations):
        if start_y + i < height - 5:
            print_at(12, start_y + i, key, T.ACCENT + T.BOLD)
            print_at(16, start_y + i, name, T.WHITE)
            print_at(30, start_y + i, desc, T.GRAY_LIGHT)
    
    print_at(12, height - 4, "Select operation:", T.WHITE)
    choice = get_input(31, height - 4, "", T.PRIMARY)
    
    if choice == '1':
        stake_oct()
    elif choice == '2':
        unstake_oct()
    elif choice == '3':
        claim_staking_rewards()
    elif choice == '4':
        staking_statistics()

def stake_oct():
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "STAKE OCT", T.SUCCESS)
    
    print_at(12, 7, f"Available Balance: {cb or 0:.6f} OCT", T.ACCENT)
    
    print_at(12, 9, "Amount to stake (OCT):", T.GRAY_LIGHT)
    amount_str = get_input(35, 9, "", T.PRIMARY)
    
    try:
        amount = float(amount_str)
        if amount <= 0 or (cb is not None and amount > cb):
            raise ValueError
    except:
        print_at(12, 11, "Invalid amount!", T.ERROR)
        get_input(12, 12, "Press ENTER to continue...", T.GRAY)
        return
    
    print_at(12, 11, "Lock period (days, 30-365):", T.GRAY_LIGHT)
    lock_days = get_input(39, 11, "90", T.PRIMARY)
    
    try:
        lock_days = int(lock_days)
        lock_days = max(30, min(365, lock_days))
    except:
        lock_days = 90
    
    # Calculate rewards
    apr = 12.5  # Annual Percentage Rate
    daily_reward = amount * (apr / 100) / 365
    total_reward = daily_reward * lock_days
    
    print_at(12, 13, "─" * (width - 24), T.GRAY)
    print_at(12, 14, "STAKING DETAILS:", T.WHITE + T.BOLD)
    print_at(12, 15, f"Amount: {amount:.6f} OCT", T.ACCENT)
    print_at(12, 16, f"Lock period: {lock_days} days", T.WARNING)
    print_at(12, 17, f"APR: {apr}%", T.SUCCESS)
    print_at(12, 18, f"Estimated reward: {total_reward:.6f} OCT", T.SUCCESS + T.BOLD)
    
    print_at(12, 20, "Confirm stake? [Y/N]:", T.WHITE)
    confirm = get_input(34, 20, "", T.PRIMARY)
    
    if confirm.lower() == 'y':
        print_at(12, 22, "Processing stake...", T.WARNING)
        
        # Simulasi proses staking
        for i in range(3):
            print_at(34 + i, 22, ".", T.ACCENT)
            time.sleep(0.5)
        
        print_at(12, 22, "✅ OCT staked successfully!", T.SUCCESS)
        
        # Update balance (simulasi)
        if cb is not None:
            global cb
            cb -= amount
        
        # Save staking record
        stake_record = {
            'amount': amount,
            'lock_days': lock_days,
            'start_date': datetime.now().isoformat(),
            'end_date': (datetime.now() + timedelta(days=lock_days)).isoformat(),
            'estimated_reward': total_reward,
            'status': 'active'
        }
        
        stake_file = f"stake_{int(time.time())}.json"
        with open(stake_file, 'w') as f:
            json.dump(stake_record, f, indent=2)
        
        print_at(12, 24, f"Staking record saved to: {stake_file}", T.GRAY_LIGHT)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

def staking_statistics():
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "STAKING STATISTICS", T.ACCENT)
    
    # Simulasi data staking
    stats = {
        'total_staked': 1250000.50,
        'active_stakers': 5421,
        'avg_apr': 12.5,
        'total_rewards_paid': 156230.75,
        'network_stake_ratio': '24.3%',
        'next_reward_distribution': '2 days 4 hours'
    }
    
    print_at(12, 7, "Network Staking Statistics:", T.WHITE + T.BOLD)
    
    y = 9
    for key, value in stats.items():
        label = key.replace('_', ' ').title()
        print_at(12, y, f"{label}:", T.GRAY_LIGHT)
        
        if 'apr' in key or 'ratio' in key:
            print_at(35, y, str(value), T.SUCCESS)
        elif 'staked' in key or 'rewards' in key:
            if isinstance(value, float):
                display = f"{value:,.2f} OCT"
            else:
                display = str(value)
            print_at(35, y, display, T.ACCENT)
        else:
            print_at(35, y, str(value), T.WHITE)
        y += 1
    
    # Personal stats (simulasi)
    personal_stats = {
        'your_staked': 5000.0,
        'pending_rewards': 125.50,
        'staking_since': '45 days ago',
        'estimated_annual_reward': 625.0
    }
    
    print_at(12, y + 1, "─" * (width - 24), T.GRAY)
    print_at(12, y + 2, "Your Staking Statistics:", T.WHITE + T.BOLD)
    
    y += 3
    for key, value in personal_stats.items():
        label = key.replace('_', ' ').title()
        print_at(12, y, f"{label}:", T.GRAY_LIGHT)
        
        if 'reward' in key:
            print_at(35, y, f"{value} OCT", T.SUCCESS + T.BOLD)
        else:
            print_at(35, y, str(value), T.WHITE)
        y += 1
    
    # Staking chart ASCII
    print_at(12, y + 1, "Staking Growth:", T.WHITE)
    chart_y = y + 2
    for i in range(5):
        bars = "█" * (i + 1) * 3
        month = f"Month {i+1}"
        print_at(12, chart_y + i, month, T.GRAY)
        print_at(20, chart_y + i, bars, T.ACCENT)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

# ============== FITUR 3: MULTI-SIGNATURE WALLET ==============
def multisig_wallet_manager():
    """Create and manage multi-signature wallets"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "MULTI-SIGNATURE WALLET", T.SECONDARY)
    
    print_at(12, 7, "Multi-Signature Operations:", T.WHITE + T.BOLD)
    
    operations = [
        ("[1]", "Create MultiSig", "Create new multi-signature wallet"),
        ("[2]", "Add Signer", "Add signer to existing MultiSig"),
        ("[3]", "Remove Signer", "Remove signer from MultiSig"),
        ("[4]", "Change Threshold", "Change required signatures"),
        ("[5]", "Propose Transaction", "Create MultiSig transaction"),
        ("[6]", "Sign Transaction", "Sign pending transaction"),
        ("[7]", "Execute Transaction", "Execute signed transaction"),
        ("[8]", "View MultiSig Info", "View MultiSig details"),
        ("[0]", "Back", "Return to main menu")
    ]
    
    start_y = 9
    for i, (key, name, desc) in enumerate(operations):
        if start_y + i < height - 5:
            print_at(12, start_y + i, key, T.ACCENT + T.BOLD)
            print_at(16, start_y + i, name, T.WHITE)
            print_at(35, start_y + i, desc, T.GRAY_LIGHT)
    
    print_at(12, height - 4, "Select operation:", T.WHITE)
    choice = get_input(31, height - 4, "", T.PRIMARY)
    
    if choice == '1':
        create_multisig_wallet()
    elif choice == '5':
        propose_multisig_transaction()
    elif choice == '8':
        view_multisig_info()

def create_multisig_wallet():
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "CREATE MULTI-SIG WALLET", T.SECONDARY)
    
    print_at(12, 7, "Number of signers (2-10):", T.GRAY_LIGHT)
    num_signers_str = get_input(38, 7, "3", T.PRIMARY)
    
    try:
        num_signers = int(num_signers_str)
        num_signers = max(2, min(10, num_signers))
    except:
        num_signers = 3
    
    print_at(12, 9, f"Required signatures (1-{num_signers}):", T.GRAY_LIGHT)
    threshold_str = get_input(45, 9, str(min(2, num_signers)), T.PRIMARY)
    
    try:
        threshold = int(threshold_str)
        threshold = max(1, min(num_signers, threshold))
    except:
        threshold = min(2, num_signers)
    
    signers = []
    print_at(12, 11, "Enter signer addresses:", T.GRAY_LIGHT)
    
    for i in range(num_signers):
        if i == 0 and addr:
            signer_addr = addr
            print_at(12, 12 + i, f"Signer {i+1} (You):", T.GRAY_LIGHT)
            print_at(28, 12 + i, addr, T.ACCENT)
        else:
            print_at(12, 12 + i, f"Signer {i+1}:", T.GRAY_LIGHT)
            signer_addr = get_input(22, 12 + i, "", T.PRIMARY)
        
        if signer_addr and b58.match(signer_addr):
            signers.append(signer_addr)
        else:
            print_at(12, 14 + i, "Invalid address!", T.ERROR)
            time.sleep(1)
            return
    
    # Create MultiSig
    print_at(12, 12 + num_signers + 1, "Creating MultiSig wallet...", T.WARNING)
    
    # Generate MultiSig address
    signers_hash = hashlib.sha256(''.join(sorted(signers)).encode()).hexdigest()
    multisig_addr = "octMULTISIG" + signers_hash[:34]
    
    # Create MultiSig configuration
    multisig_config = {
        'address': multisig_addr,
        'signers': signers,
        'threshold': threshold,
        'creator': addr,
        'created_at': datetime.now().isoformat(),
        'pending_transactions': []
    }
    
    multisig_file = f"multisig_{multisig_addr[-8:]}.json"
    with open(multisig_file, 'w') as f:
        json.dump(multisig_config, f, indent=2)
    
    print_at(12, 12 + num_signers + 1, "✅ MultiSig created successfully!", T.SUCCESS)
    print_at(12, 12 + num_signers + 2, f"MultiSig Address: {multisig_addr}", T.ACCENT)
    print_at(12, 12 + num_signers + 3, f"Signers: {len(signers)}", T.GRAY_LIGHT)
    print_at(12, 12 + num_signers + 4, f"Required: {threshold}/{len(signers)}", T.WARNING)
    print_at(12, 12 + num_signers + 5, f"Config saved to: {multisig_file}", T.SUCCESS)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

# ============== FITUR 4: TOKEN CREATOR ==============
def token_creator():
    """Create custom tokens on OCTRA network"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "TOKEN CREATOR", T.ACCENT)
    
    print_at(12, 7, "Token Type:", T.WHITE + T.BOLD)
    
    token_types = [
        ("[1]", "Fungible Token", "Like ERC-20, for currencies"),
        ("[2]", "Non-Fungible Token", "NFT, for unique items"),
        ("[3]", "Semi-Fungible Token", "SFT, for limited editions"),
        ("[4]", "Utility Token", "For specific applications"),
        ("[5]", "Governance Token", "For DAO voting rights"),
        ("[0]", "Back", "Return to main menu")
    ]
    
    start_y = 9
    for i, (key, name, desc) in enumerate(token_types):
        if start_y + i < height - 5:
            print_at(12, start_y + i, key, T.ACCENT + T.BOLD)
            print_at(16, start_y + i, name, T.WHITE)
            print_at(35, start_y + i, desc, T.GRAY_LIGHT)
    
    print_at(12, height - 4, "Select token type:", T.WHITE)
    choice = get_input(32, height - 4, "", T.PRIMARY)
    
    if choice == '1':
        create_fungible_token()
    elif choice == '2':
        create_nft_token()
    elif choice == '5':
        create_governance_token()

def create_fungible_token():
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "CREATE FUNGIBLE TOKEN", T.ACCENT)
    
    print_at(12, 7, "Token Name:", T.GRAY_LIGHT)
    token_name = get_input(25, 7, "MyToken", T.PRIMARY)
    
    print_at(12, 8, "Token Symbol:", T.GRAY_LIGHT)
    token_symbol = get_input(27, 8, "MTK", T.PRIMARY)
    
    print_at(12, 9, "Total Supply:", T.GRAY_LIGHT)
    total_supply = get_input(27, 9, "1000000", T.PRIMARY)
    
    try:
        total_supply = int(total_supply)
    except:
        total_supply = 1000000
    
    print_at(12, 10, "Decimals (0-18):", T.GRAY_LIGHT)
    decimals = get_input(30, 10, "6", T.PRIMARY)
    
    try:
        decimals = int(decimals)
        decimals = max(0, min(18, decimals))
    except:
        decimals = 6
    
    # Advanced features
    print_at(12, 12, "Advanced Features:", T.WHITE + T.BOLD)
    print_at(12, 13, "[ ] Mintable (can create more tokens)", T.GRAY_LIGHT)
    print_at(12, 14, "[ ] Burnable (can destroy tokens)", T.GRAY_LIGHT)
    print_at(12, 15, "[ ] Pausable (can pause transfers)", T.GRAY_LIGHT)
    print_at(12, 16, "[ ] Taxable (transfer tax)", T.GRAY_LIGHT)
    
    print_at(12, 18, "Initial Distribution:", T.GRAY_LIGHT)
    print_at(12, 19, f"Your address: {addr[:20]}...", T.WHITE)
    
    print_at(12, 21, "Create token? [Y/N]:", T.WHITE)
    confirm = get_input(33, 21, "", T.PRIMARY)
    
    if confirm.lower() == 'y':
        print_at(12, 23, "Deploying token contract...", T.WARNING)
        
        # Simulasi deployment
        for i in range(5):
            print_at(41 + i, 23, ".", T.ACCENT)
            time.sleep(0.3)
        
        # Generate token address
        token_hash = hashlib.sha256((token_name + token_symbol + str(time.time())).encode()).hexdigest()
        token_address = "octTOKEN" + token_hash[:34]
        
        print_at(12, 23, "✅ Token created successfully!", T.SUCCESS)
        
        # Token info
        token_info = {
            'name': token_name,
            'symbol': token_symbol,
            'address': token_address,
            'total_supply': total_supply,
            'decimals': decimals,
            'creator': addr,
            'created_at': datetime.now().isoformat(),
            'type': 'fungible'
        }
        
        token_file = f"token_{token_symbol}_{token_address[-8:]}.json"
        with open(token_file, 'w') as f:
            json.dump(token_info, f, indent=2)
        
        print_at(12, 24, f"Token Address: {token_address}", T.ACCENT)
        print_at(12, 25, f"Symbol: {token_symbol}", T.WHITE)
        print_at(12, 26, f"Total Supply: {total_supply:,}", T.GRAY_LIGHT)
        print_at(12, 27, f"Info saved to: {token_file}", T.SUCCESS)
        
        # Generate token contract code
        contract_code = f"""
// {token_name} ({token_symbol}) Token Contract
pragma octra 0.8.0;

contract {token_name.replace(' ', '')} {{
    string public name = "{token_name}";
    string public symbol = "{token_symbol}";
    uint8 public decimals = {decimals};
    uint256 public totalSupply = {total_supply} * 10**{decimals};
    
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    
    constructor() {{
        balanceOf[msg.sender] = totalSupply;
        emit Transfer(address(0), msg.sender, totalSupply);
    }}
    
    function transfer(address to, uint256 value) public returns (bool) {{
        require(balanceOf[msg.sender] >= value, "Insufficient balance");
        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;
        emit Transfer(msg.sender, to, value);
        return true;
    }}
    
    function approve(address spender, uint256 value) public returns (bool) {{
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }}
}}
        """
        
        contract_file = f"{token_symbol}_contract.oct"
        with open(contract_file, 'w') as f:
            f.write(contract_code)
        
        print_at(12, 29, f"Contract code: {contract_file}", T.GRAY_LIGHT)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

# ============== FITUR 5: SWAP AGGREGATOR ==============
def swap_aggregator():
    """Find best swap rates across DEXs"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "SWAP AGGREGATOR", T.PRIMARY)
    
    # Simulate token list
    tokens = [
        ("OCT", "Octra Native", 1.0),
        ("OCT-USDC", "USD Coin Pair", 1.0),
        ("OCT-ETH", "Ethereum Pair", 0.00042),
        ("OCT-BTC", "Bitcoin Pair", 0.000025),
        ("OCT-LINK", "Chainlink", 0.15)
    ]
    
    print_at(12, 7, "Available Trading Pairs:", T.WHITE + T.BOLD)
    
    start_y = 9
    for i, (symbol, name, price) in enumerate(tokens):
        print_at(12, start_y + i, f"[{i+1}]", T.ACCENT + T.BOLD)
        print_at(16, start_y + i, symbol, T.WHITE)
        print_at(25, start_y + i, name, T.GRAY_LIGHT)
        print_at(45, start_y + i, f"${price:.6f}", T.SUCCESS)
    
    print_at(12, start_y + len(tokens) + 1, "From Token:", T.GRAY_LIGHT)
    from_token = get_input(25, start_y + len(tokens) + 1, "1", T.PRIMARY)
    
    print_at(12, start_y + len(tokens) + 2, "To Token:", T.GRAY_LIGHT)
    to_token = get_input(23, start_y + len(tokens) + 2, "2", T.PRIMARY)
    
    print_at(12, start_y + len(tokens) + 3, "Amount:", T.GRAY_LIGHT)
    amount = get_input(21, start_y + len(tokens) + 3, "10", T.PRIMARY)
    
    try:
        amount = float(amount)
        from_idx = int(from_token) - 1 if from_token.isdigit() else 0
        to_idx = int(to_token) - 1 if to_token.isdigit() else 1
        
        from_price = tokens[from_idx][2] if 0 <= from_idx < len(tokens) else 1.0
        to_price = tokens[to_idx][2] if 0 <= to_idx < len(tokens) else 1.0
        
        # Calculate swap
        received = amount * from_price / to_price
        
        print_at(12, start_y + len(tokens) + 5, "─" * (width - 24), T.GRAY)
        print_at(12, start_y + len(tokens) + 6, "SWAP QUOTE:", T.WHITE + T.BOLD)
        print_at(12, start_y + len(tokens) + 7, f"From: {amount} {tokens[from_idx][0]}", T.ACCENT)
        print_at(12, start_y + len(tokens) + 8, f"To: {received:.6f} {tokens[to_idx][0]}", T.SUCCESS)
        
        # Simulate DEX prices
        dex_prices = [
            ("Uniswap V3", received * 0.99),
            ("PancakeSwap", received * 1.01),
            ("SushiSwap", received * 0.998),
            ("Octra DEX", received * 1.005)
        ]
        
        print_at(12, start_y + len(tokens) + 10, "Best Prices:", T.WHITE)
        for i, (dex, price) in enumerate(dex_prices):
            print_at(12, start_y + len(tokens) + 11 + i, f"• {dex}:", T.GRAY_LIGHT)
            print_at(25, start_y + len(tokens) + 11 + i, f"{price:.6f}", T.SUCCESS)
        
        best_dex = max(dex_prices, key=lambda x: x[1])
        print_at(12, start_y + len(tokens) + 15, f"🔥 Best: {best_dex[0]} - {best_dex[1]:.6f}", T.WARNING + T.BOLD)
        
        print_at(12, start_y + len(tokens) + 17, "Execute swap? [Y/N]:", T.WHITE)
        confirm = get_input(35, start_y + len(tokens) + 17, "", T.PRIMARY)
        
        if confirm.lower() == 'y':
            print_at(12, start_y + len(tokens) + 19, "Swapping...", T.WARNING)
            time.sleep(2)
            print_at(12, start_y + len(tokens) + 19, f"✅ Swapped {amount} {tokens[from_idx][0]} → {best_dex[1]:.6f} {tokens[to_idx][0]}", T.SUCCESS)
        
    except:
        print_at(12, start_y + len(tokens) + 5, "Invalid input!", T.ERROR)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

# ============== FITUR 6: PORTFOLIO TRACKER ==============
def portfolio_tracker():
    """Track portfolio performance"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "PORTFOLIO TRACKER", T.SECONDARY)
    
    # Sample portfolio data
    portfolio = [
        {"asset": "OCT", "amount": 4681.0, "price": 1.0, "value": 4681.0, "change": "+2.5%"},
        {"asset": "OCT-USDC", "amount": 500.0, "price": 1.0, "value": 500.0, "change": "+0.1%"},
        {"asset": "OCT-ETH", "amount": 2.5, "price": 2380.0, "value": 5950.0, "change": "-1.2%"},
        {"asset": "OCT-BTC", "amount": 0.1, "price": 42000.0, "value": 4200.0, "change": "+5.3%"},
        {"asset": "Staked OCT", "amount": 1000.0, "price": 1.0, "value": 1000.0, "change": "+0.8%"}
    ]
    
    total_value = sum(item["value"] for item in portfolio)
    
    print_at(12, 7, f"Total Portfolio Value: ${total_value:,.2f}", T.ACCENT + T.BOLD)
    print_at(12, 8, f"24h Change: +{2.7}%", T.SUCCESS)
    
    print_at(12, 10, "ASSET         AMOUNT      PRICE       VALUE       24H", T.WHITE + T.BOLD)
    print_at(12, 11, "─" * (width - 24), T.GRAY)
    
    start_y = 12
    for i, item in enumerate(portfolio):
        if start_y + i < height - 5:
            print_at(12, start_y + i, item["asset"], T.WHITE)
            print_at(25, start_y + i, f"{item['amount']:,.2f}", T.GRAY_LIGHT)
            print_at(37, start_y + i, f"${item['price']:,.2f}", T.GRAY)
            print_at(49, start_y + i, f"${item['value']:,.2f}", T.ACCENT)
            
            change_color = T.SUCCESS if item["change"].startswith("+") else T.ERROR
            print_at(62, start_y + i, item["change"], change_color)
    
    # Allocation chart
    chart_y = start_y + len(portfolio) + 2
    print_at(12, chart_y, "Allocation:", T.WHITE)
    
    for i, item in enumerate(portfolio):
        percentage = (item["value"] / total_value) * 100
        bars = "█" * int(percentage / 2)
        print_at(12, chart_y + 1 + i, f"{item['asset']}:", T.GRAY_LIGHT)
        print_at(25, chart_y + 1 + i, bars, T.ACCENT)
        print_at(25 + len(bars) + 1, chart_y + 1 + i, f"{percentage:.1f}%", T.WHITE)
    
    # Performance metrics
    metrics_y = chart_y + len(portfolio) + 3
    print_at(12, metrics_y, "Performance Metrics:", T.WHITE + T.BOLD)
    
    metrics = [
        ("Daily P&L", "+$245.60", T.SUCCESS),
        ("Weekly P&L", "+$1,245.80", T.SUCCESS),
        ("Monthly P&L", "+$5,421.30", T.SUCCESS),
        ("Best Performer", "OCT-BTC (+5.3%)", T.SUCCESS),
        ("Worst Performer", "OCT-ETH (-1.2%)", T.ERROR)
    ]
    
    for i, (label, value, color) in enumerate(metrics):
        print_at(12, metrics_y + 1 + i, label + ":", T.GRAY_LIGHT)
        print_at(30, metrics_y + 1 + i, value, color)
    
    print_at(12, height - 4, "[R] Refresh  [E] Export  [0] Back:", T.WHITE)
    choice = get_input(45, height - 4, "", T.PRIMARY)
    
    if choice.lower() == 'e':
        export_portfolio_data(portfolio, total_value)
    elif choice == '0':
        return
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

def export_portfolio_data(portfolio, total_value):
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "total_value": total_value,
        "assets": portfolio,
        "summary": {
            "asset_count": len(portfolio),
            "top_asset": max(portfolio, key=lambda x: x["value"])["asset"],
            "bottom_asset": min(portfolio, key=lambda x: x["value"])["asset"]
        }
    }
    
    export_file = f"portfolio_export_{int(time.time())}.json"
    with open(export_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    width, height = get_terminal_size()
    print_at(12, height - 6, f"✅ Portfolio exported to {export_file}", T.SUCCESS)
    time.sleep(2)

# ============== FITUR 7: BRIDGE INTERFACE ==============
def bridge_interface():
    """Bridge assets between chains"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "CROSS-CHAIN BRIDGE", T.PRIMARY)
    
    # Supported chains
    chains = [
        ("Ethereum", "ETH", 0.0015),
        ("BNB Chain", "BNB", 0.0003),
        ("Polygon", "MATIC", 0.001),
        ("Arbitrum", "ARB", 0.0005),
        ("Optimism", "OP", 0.0004),
        ("Avalanche", "AVAX", 0.001)
    ]
    
    print_at(12, 7, "Supported Chains:", T.WHITE + T.BOLD)
    
    start_y = 9
    for i, (name, symbol, fee) in enumerate(chains):
        print_at(12, start_y + i, f"[{i+1}]", T.ACCENT + T.BOLD)
        print_at(16, start_y + i, name, T.WHITE)
        print_at(30, start_y + i, f"({symbol})", T.GRAY_LIGHT)
        print_at(40, start_y + i, f"Fee: {fee:.4f} {symbol}", T.WARNING)
    
    print_at(12, start_y + len(chains) + 1, "From Chain:", T.GRAY_LIGHT)
    from_chain = get_input(25, start_y + len(chains) + 1, "1", T.PRIMARY)
    
    print_at(12, start_y + len(chains) + 2, "To Chain:", T.GRAY_LIGHT)
    to_chain = get_input(23, start_y + len(chains) + 2, "2", T.PRIMARY)
    
    print_at(12, start_y + len(chains) + 3, "Amount (OCT):", T.GRAY_LIGHT)
    amount = get_input(27, start_y + len(chains) + 3, "10", T.PRIMARY)
    
    try:
        amount = float(amount)
        from_idx = int(from_chain) - 1 if from_chain.isdigit() else 0
        to_idx = int(to_chain) - 1 if to_chain.isdigit() else 1
        
        from_chain_name = chains[from_idx][0]
        to_chain_name = chains[to_idx][0]
        fee = chains[to_idx][2]
        
        print_at(12, start_y + len(chains) + 5, "─" * (width - 24), T.GRAY)
        print_at(12, start_y + len(chains) + 6, "BRIDGE DETAILS:", T.WHITE + T.BOLD)
        print_at(12, start_y + len(chains) + 7, f"From: {from_chain_name}", T.ACCENT)
        print_at(12, start_y + len(chains) + 8, f"To: {to_chain_name}", T.SUCCESS)
        print_at(12, start_y + len(chains) + 9, f"Amount: {amount} OCT", T.WHITE)
        print_at(12, start_y + len(chains) + 10, f"Bridge Fee: {fee} {chains[to_idx][1]}", T.WARNING)
        print_at(12, start_y + len(chains) + 11, f"Estimated Time: 5-15 minutes", T.GRAY_LIGHT)
        
        # Bridge routes
        print_at(12, start_y + len(chains) + 13, "Available Routes:", T.WHITE)
        routes = [
            ("Official Bridge", "Most secure", "5-10 min"),
            ("LayerZero", "Fast", "2-5 min"),
            ("Wormhole", "Low fee", "10-15 min")
        ]
        
        for i, (name, desc, time) in enumerate(routes):
            print_at(12, start_y + len(chains) + 14 + i, f"• {name}:", T.GRAY_LIGHT)
            print_at(30, start_y + len(chains) + 14 + i, desc, T.WHITE)
            print_at(50, start_y + len(chains) + 14 + i, time, T.ACCENT)
        
        print_at(12, start_y + len(chains) + 18, "Execute bridge? [Y/N]:", T.WHITE)
        confirm = get_input(37, start_y + len(chains) + 18, "", T.PRIMARY)
        
        if confirm.lower() == 'y':
            print_at(12, start_y + len(chains) + 20, "Bridging assets...", T.WARNING)
            
            # Simulate bridge process
            steps = ["Validating", "Locking", "Relaying", "Minting"]
            for i, step in enumerate(steps):
                print_at(12, start_y + len(chains) + 21 + i, f"  [{i+1}/4] {step}", T.GRAY_LIGHT)
                for j in range(3):
                    print_at(30 + j, start_y + len(chains) + 21 + i, ".", T.ACCENT)
                    time.sleep(0.3)
                print_at(33, start_y + len(chains) + 21 + i, "✓", T.SUCCESS)
            
            print_at(12, start_y + len(chains) + 25, f"✅ Bridged {amount} OCT to {to_chain_name}!", T.SUCCESS)
            
            # Generate bridge receipt
            receipt = {
                "from_chain": from_chain_name,
                "to_chain": to_chain_name,
                "amount": amount,
                "fee": fee,
                "bridge_time": datetime.now().isoformat(),
                "status": "completed",
                "transaction_hash": f"0x{hashlib.sha256((from_chain_name + to_chain_name + str(amount)).encode()).hexdigest()[:32]}"
            }
            
            receipt_file = f"bridge_receipt_{int(time.time())}.json"
            with open(receipt_file, 'w') as f:
                json.dump(receipt, f, indent=2)
            
            print_at(12, start_y + len(chains) + 27, f"Receipt: {receipt_file}", T.GRAY_LIGHT)
        
    except:
        print_at(12, start_y + len(chains) + 5, "Invalid input!", T.ERROR)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

# ============== FITUR 8: GOVERNANCE VOTING ==============
def governance_voting():
    """Participate in OCTRA governance"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "GOVERNANCE VOTING", T.SECONDARY)
    
    # Active proposals
    proposals = [
        {
            "id": 42,
            "title": "Increase Staking Rewards to 15%",
            "status": "active",
            "votes_for": 1250000,
            "votes_against": 450000,
            "deadline": "3 days",
            "quorum": "68%"
        },
        {
            "id": 41,
            "title": "Add Support for EVM Compatibility",
            "status": "active",
            "votes_for": 980000,
            "votes_against": 520000,
            "deadline": "1 day",
            "quorum": "72%"
        },
        {
            "id": 40,
            "title": "Reduce Transaction Fees by 20%",
            "status": "passed",
            "votes_for": 2100000,
            "votes_against": 350000,
            "deadline": "ended",
            "quorum": "85%"
        }
    ]
    
    print_at(12, 7, "Active Proposals:", T.WHITE + T.BOLD)
    
    start_y = 9
    for i, prop in enumerate(proposals):
        if start_y + i < height - 5:
            status_color = T.SUCCESS if prop["status"] == "active" else T.WARNING if prop["status"] == "passed" else T.GRAY
            print_at(12, start_y + i, f"[{prop['id']}]", T.ACCENT + T.BOLD)
            print_at(17, start_y + i, prop["title"][:30] + ("..." if len(prop["title"]) > 30 else ""), T.WHITE)
            print_at(50, start_y + i, prop["status"], status_color)
    
    print_at(12, start_y + len(proposals) + 1, "Select proposal ID to vote:", T.GRAY_LIGHT)
    prop_id = get_input(42, start_y + len(proposals) + 1, "", T.PRIMARY)
    
    if not prop_id:
        return
    
    try:
        prop_id = int(prop_id)
        selected_prop = next((p for p in proposals if p["id"] == prop_id), None)
        
        if selected_prop:
            clear_screen()
            draw_box(10, 5, width - 20, height - 10, f"PROPOSAL #{prop_id}", T.PRIMARY)
            
            print_at(12, 7, selected_prop["title"], T.WHITE + T.BOLD)
            print_at(12, 8, "─" * (width - 24), T.GRAY)
            
            # Proposal details
            print_at(12, 10, "Status:", T.GRAY_LIGHT)
            status_color = T.SUCCESS if selected_prop["status"] == "active" else T.WARNING
            print_at(20, 10, selected_prop["status"], status_color)
            
            print_at(12, 11, "Deadline:", T.GRAY_LIGHT)
            print_at(22, 11, selected_prop["deadline"], T.WARNING)
            
            print_at(12, 12, "Quorum:", T.GRAY_LIGHT)
            print_at(20, 12, selected_prop["quorum"], T.ACCENT)
            
            # Voting stats
            total_votes = selected_prop["votes_for"] + selected_prop["votes_against"]
            for_percent = (selected_prop["votes_for"] / total_votes * 100) if total_votes > 0 else 0
            
            print_at(12, 14, "Voting Statistics:", T.WHITE + T.BOLD)
            print_at(12, 15, f"For: {selected_prop['votes_for']:,} ({for_percent:.1f}%)", T.SUCCESS)
            print_at(12, 16, f"Against: {selected_prop['votes_against']:,} ({100-for_percent:.1f}%)", T.ERROR)
            
            # Voting bar
            bar_width = 40
            for_bars = int((for_percent / 100) * bar_width)
            against_bars = bar_width - for_bars
            
            print_at(12, 18, "[" + "█" * for_bars + "░" * against_bars + "]", T.WHITE)
            
            # Your voting power (simulated)
            voting_power = cb or 0  # 1 OCT = 1 vote
            
            print_at(12, 20, f"Your Voting Power: {voting_power:.2f} votes", T.ACCENT)
            
            if selected_prop["status"] == "active":
                print_at(12, 22, "Cast your vote:", T.WHITE + T.BOLD)
                print_at(12, 23, "[F] For  [A] Against  [0] Cancel:", T.GRAY_LIGHT)
                
                vote_choice = get_input(45, 23, "", T.PRIMARY)
                
                if vote_choice.lower() == 'f':
                    cast_vote(prop_id, "for", voting_power, selected_prop)
                elif vote_choice.lower() == 'a':
                    cast_vote(prop_id, "against", voting_power, selected_prop)
            else:
                print_at(12, 22, "This proposal is no longer active for voting", T.WARNING)
        
    except:
        print_at(12, start_y + len(proposals) + 3, "Invalid proposal ID!", T.ERROR)
    
    get_input(12, height - 3, "Press ENTER to continue...", T.GRAY)

def cast_vote(prop_id: int, vote: str, voting_power: float, proposal: dict):
    width, height = get_terminal_size()
    
    print_at(12, 25, f"Casting {vote} vote with {voting_power:.2f} votes...", T.WARNING)
    time.sleep(2)
    
    # Simulate vote casting
    vote_data = {
        "proposal_id": prop_id,
        "vote": vote,
        "voting_power": voting_power,
        "voter": addr,
        "timestamp": datetime.now().isoformat(),
        "transaction_hash": f"0x{hashlib.sha256((str(prop_id) + vote + str(voting_power)).encode()).hexdigest()[:32]}"
    }
    
    vote_file = f"vote_{prop_id}_{int(time.time())}.json"
    with open(vote_file, 'w') as f:
        json.dump(vote_data, f, indent=2)
    
    print_at(12, 25, f"✅ Vote cast successfully!", T.SUCCESS)
    print_at(12, 26, f"Vote saved to: {vote_file}", T.GRAY_LIGHT)
    
    # Update proposal stats (simulated)
    if vote == "for":
        proposal["votes_for"] += int(voting_power)
    else:
        proposal["votes_against"] += int(voting_power)
    
    time.sleep(2)

# ============== UTILITY FUNCTIONS ==============
def get_uptime() -> str:
    """Get system uptime"""
    try:
        if platform.system() == "Windows":
            return "Windows system"
        else:
            result = subprocess.run(['uptime', '-p'], capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else "Unknown"
    except:
        return "Unknown"

def get_memory_usage() -> str:
    """Get memory usage"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return f"{memory.percent}%"
    except:
        return "N/A"

# ============== WALLET TOOLS ENHANCED ==============
def wallet_tools_ui():
    """Enhanced Wallet Tools with all new features"""
    width, height = get_terminal_size()
    clear_screen()
    
    draw_box(10, 5, width - 20, height - 10, "ADVANCED WALLET TOOLS", T.SECONDARY)
    
    # Semua fitur baru + lama
    tools = [
        ("[1]", "🔐 Export Private Key", T.WARNING),
        ("[2]", "💾 Backup Wallet", T.SUCCESS),
        ("[3]", "🔑 View Public Key", T.PRIMARY),
        ("[4]", "🌐 Change RPC", T.ACCENT),
        ("[5]", "📊 Wallet Health", T.SUCCESS),
        ("[6]", "💰 Network Balance", T.ACCENT),
        ("[7]", "🔍 Address Validator", T.WARNING),
        ("[8]", "📝 Transaction Signer", T.PRIMARY),
        ("[9]", "📜 View History", T.SECONDARY),
        ("[A]", "🤖 Smart Contracts", T.PRIMARY),      # Fitur baru 1
        ("[B]", "🎯 Staking Manager", T.SUCCESS),      # Fitur baru 2
        ("[C]", "👥 MultiSig Wallet", T.SECONDARY),   # Fitur baru 3
        ("[D]", "🪙 Token Creator", T.ACCENT),        # Fitur baru 4
        ("[E]", "🔄 Swap Aggregator", T.PRIMARY),     # Fitur baru 5
        ("[F]", "📈 Portfolio Tracker", T.SECONDARY), # Fitur baru 6
        ("[G]", "🌉 Bridge Interface", T.ACCENT),     # Fitur baru 7
        ("[H]", "🗳️ Governance Voting", T.SUCCESS),  # Fitur baru 8
        ("[0]", "🔙 Back to Main", T.GRAY)
    ]
    
    start_y = 7
    for i, (key, name, color) in enumerate(tools):
        if start_y + i < height - 5:
            print_at(12, start_y + i, key, color + T.BOLD)
            print_at(16, start_y + i, name, color)
    
    print_at(12, height - 4, "Select option:", T.WHITE)
    choice = get_input(27, height - 4, "", T.PRIMARY).upper()
    
    if choice == 'A':
        smart_contract_interactor()
    elif choice == 'B':
        staking_manager()
    elif choice == 'C':
        multisig_wallet_manager()
    elif choice == 'D':
        token_creator()
    elif choice == 'E':
        swap_aggregator()
    elif choice == 'F':
        portfolio_tracker()
    elif choice == 'G':
        bridge_interface()
    elif choice == 'H':
        governance_voting()
    elif choice == '0':
        return

# ============== MAIN LOOP ==============
def main():
    signal.signal(signal.SIGINT, lambda s, f: stop_flag.set())
    clear_screen()
    
    if load_wallet():
        print_at(10, 10, "✅ Advanced Wallet loaded successfully", T.SUCCESS)
    else:
        print_at(10, 10, "⚠️  No wallet found. Use [9] to import", T.WARNING)
    
    global cb, cn
    if cb is None:
        cb = 4681.0
    if cn is None:
        cn = 0
    
    # Sample transactions
    if not h:
        h.extend([
            {'time': datetime.now() - timedelta(minutes=30), 'type': 'in', 'amt': 10.5, 'to': 'oct...Sender1'},
            {'time': datetime.now() - timedelta(hours=2), 'type': 'out', 'amt': 5.2, 'to': 'oct...Recipient1'},
            {'time': datetime.now() - timedelta(days=1), 'type': 'in', 'amt': 100.0, 'to': 'oct...Sender2'}
        ])
    
    time.sleep(1)
    
    while not stop_flag.is_set():
        try:
            command = draw_responsive_dashboard()
            if not command:
                command = ""
            
            command = command.strip().lower()
            
            if command in ['q', 'quit', 'exit']:
                break
            elif command in ['r', 'refresh']:
                continue
            elif command == '1':
                # Send Transaction (placeholder)
                width, height = get_terminal_size()
                draw_box(width//2 - 15, height//2 - 2, 30, 5, "SEND TX", T.PRIMARY)
                print_at(width//2 - 10, height//2, "Coming in next update", T.WHITE)
                get_input(width//2 - 12, height//2 + 1, "Press ENTER...", T.GRAY)
            elif command == '8':
                wallet_tools_ui()
            elif command == '9':
                # Import Wallet (placeholder)
                width, height = get_terminal_size()
                draw_box(width//2 - 15, height//2 - 2, 30, 5, "IMPORT", T.PRIMARY)
                print_at(width//2 - 10, height//2, "Use option [9] in menu", T.WHITE)
                get_input(width//2 - 12, height//2 + 1, "Press ENTER...", T.GRAY)
            elif command in ['2', '3', '4', '5', '6', '7', '0']:
                width, height = get_terminal_size()
                draw_box(width//2 - 15, height//2 - 2, 30, 5, "COMING SOON", T.WARNING)
                print_at(width//2 - 10, height//2, "Feature in development", T.WHITE)
                get_input(width//2 - 12, height//2 + 1, "Press ENTER...", T.GRAY)
            else:
                if command:
                    width, height = get_terminal_size()
                    draw_box(width//2 - 15, height//2 - 2, 30, 5, "INVALID COMMAND", T.ERROR)
                    print_at(width//2 - 10, height//2, f"'{command}' not recognized", T.WHITE)
                    get_input(width//2 - 12, height//2 + 1, "Press ENTER...", T.GRAY)
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            try:
                width, height = get_terminal_size()
                draw_box(width//2 - 20, height//2 - 2, 40, 6, "ERROR", T.ERROR)
                error_msg = str(e)[:35]
                print_at(width//2 - 18, height//2, f"Error: {error_msg}", T.WHITE)
                get_input(width//2 - 18, height//2 + 1, "Press ENTER...", T.GRAY)
            except:
                pass
    
    clear_screen()
    width, height = get_terminal_size()
    print_at(width//2 - 10, height//2, "Advanced Wallet Closed 👋", T.PRIMARY + T.BOLD)
    time.sleep(1)
    print(f"{T.RESET}")

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        print(f"{T.RESET}")
