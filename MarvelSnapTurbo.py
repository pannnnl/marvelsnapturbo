import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import os
import re
import shutil
import threading
import time
import webbrowser
import zlib
from PIL import Image, ImageDraw
import customtkinter as ctk
from playwright.sync_api import sync_playwright
import requests
import pystray
from pystray import MenuItem as item

# 啟用 CustomTkinter 深色模式與主題
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

RENDER_API_URL = "https://msnap-bot.onrender.com/notify"
RENDER_PING_URL = "https://msnap-bot.onrender.com"
GITHUB_CARDS_URL = "https://raw.githubusercontent.com/pannnnl/marvel-snap-cards-api/main/marvel_snap_cards.json"
BOT_INVITE_URL = "https://discord.com/oauth2/authorize?client_id=1560327479711764603&permissions=117760&integration_type=0&scope=bot"

# 🚀 使用 GitHub 官方 Releases API 進行版本檢查
GITHUB_RELEASE_API = "https://api.github.com/repos/pannnnl/marvelsnapturbo/releases/latest"

CURRENT_VERSION = "8.2"  # 版本號維持 v8.2
AUTHOR_GITHUB = "https://github.com/pannnnl/marvelsnapturbo"  # 專案 GitHub 連結

# 自動在用戶的「文件 (Documents)」建立專屬資料夾
BASE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "MS_BOT")
os.makedirs(BASE_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
HISTORY_FILE = os.path.join(BASE_DIR, "shop_history.json")
USER_DATA_DIR = os.path.join(BASE_DIR, "browser_profile")

# 🌐 多國語言介面字典
LANG_DATA = {
    "en": {
        "badge": "⚡ TURBO v8.2 [Optimized Web Login & Session Guard]",
        "switch_btn": "文/A",
        "clear_session_btn": "🗑 Clear Web Session",
        "refresh_btn": "↻ Refresh Local Data",
        "title": "Marvel Snap Turbo",
        "subtitle": "Collection Gallery & Sharing • Auto 100 Credits • Web Shop Bundle Alerts",
        "account_status": "🎮 Game Account: Not Logged In\n🕒 Last Login: Unknown",
        "id_label": "Discord User ID",
        "id_placeholder": "Enter Discord User ID (e.g. 123456789)",
        "invite_bot_link": "🔗 Invite Bot to Discord",
        "shop_cb": "Enable shop bundle alerts (8-day smart filter)",
        "start_btn": "🚀 Auto-Claim 100 Credits",
        "stop_btn": "⏹ Stop Automation",
        "collection_btn": "📊 Sync Data & Generate Card Gallery",
        "share_export_btn": "📤 Generate Share Code",
        "share_import_btn": "📥 Import",
        "share_placeholder": "Paste friend's card collection code here...",
        "log_title": " 💻 System Terminal Log (English)",
        "ready_msg": "💡 Marvel Snap Turbo v8.2 ready. Enhanced login state handler active.",
    },
    "zh": {
        "badge": "⚡ TURBO v8.2 [優化首次登入網店版本]",
        "switch_btn": "文/A",
        "clear_session_btn": "🗑 清除網頁授權快取",
        "refresh_btn": "↻ 重新整理本地數據",
        "title": "Marvel Snap Turbo",
        "subtitle": "卡片收藏展覽與分享 • 自動領取 100 點數 • 網絡商店新禮包通知",
        "account_status": "🎮 遊戲帳號: 尚未登入 (Not Logged In)\n🕒 上次登入: 未知",
        "id_label": "Discord 使用者 ID",
        "id_placeholder": "請輸入你的 Discord ID (例如 123456789)",
        "invite_bot_link": "🔗 邀請 Bot 加入 Discord",
        "shop_cb": "啟用禮包商店通知 (8天智慧過濾)",
        "start_btn": "🚀 自動領取 100 點數",
        "stop_btn": "⏹ 停止自動化",
        "collection_btn": "📊 同步數據並產生卡片展覽館",
        "share_export_btn": "📤 產生卡片庫代碼",
        "share_import_btn": "📥 導入",
        "share_placeholder": "在此貼上好友的卡片庫代碼...",
        "log_title": " 💻 System Terminal Log (English)",
        "ready_msg": "💡 Marvel Snap Turbo v8.2 已就緒。已啟用優化登入狀態攔截與 Bot 喚醒防護。",
    }
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"discord_user_id": "", "check_shop": True, "lang": "en"}


def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save config: {e}")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%d")
                return {h: d for h, d in history.items() if d >= cutoff_date}
        except:
            return {}
    return {}


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save history: {e}")


def get_text_hash(text):
    cleaned_text = re.sub(
        r"\d+\s*[dhms]\s*(\d+\s*[dhms])?\s*(後可用|後結束|後|left|remaining)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    final_text = "\n".join(
        [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    )
    return hashlib.md5(final_text.encode("utf-8")).hexdigest()


def stitch_shop_images(image_paths, output_path):
    if not image_paths:
        return None
    try:
        num_images = len(image_paths)
        items_per_row = min(num_images, 4)

        images = [Image.open(p) for p in image_paths]
        img_width, img_height = images[0].size
        padding = 20
        margin = 25
        num_rows = math.ceil(num_images / items_per_row)

        total_width = (
            margin * 2 + img_width * items_per_row + padding * (items_per_row - 1)
        )
        total_height = margin * 2 + img_height * num_rows + padding * (num_rows - 1)

        combined_img = Image.new("RGB", (total_width, total_height), (15, 17, 23))

        for idx, img in enumerate(images):
            row = idx // items_per_row
            col = idx % items_per_row
            x = margin + col * (img_width + padding)
            y = margin + row * (img_height + padding)

            if img.size != (img_width, img_height):
                img = img.resize((img_width, img_height))

            combined_img.paste(img, (x, y))

        combined_img.save(output_path, quality=95)
        for img in images:
            img.close()
        return output_path
    except Exception as e:
        print(f"Failed to stitch images in grid: {e}")
        return None


def get_local_snap_id():
    """從 AnalyticState.json 複製快照後解析 SnapId（支援遊戲運行中同步讀取）"""
    try:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if not local_app_data:
            local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")

        base_low = os.path.abspath(os.path.join(local_app_data, "..", "LocalLow"))
        analytic_path = os.path.join(
            base_low, "Second Dinner", "SNAP", "Standalone", "States", "nvprod", "AnalyticState.json"
        )

        if not os.path.exists(analytic_path):
            return None

        temp_path = os.path.join(BASE_DIR, "temp_AnalyticState.json")
        try:
            shutil.copy2(analytic_path, temp_path)
            read_target = temp_path
        except PermissionError:
            read_target = analytic_path

        with open(read_target, "r", encoding="utf-8-sig", errors="ignore") as f:
            data = json.load(f)

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

        flushing_batches = data.get("BatchState", {}).get("FlushingBatches", [])
        for batch in flushing_batches:
            events = batch.get("Events", [])
            for event in events:
                snap_id = event.get("Metadata", {}).get("SnapId", "")
                if snap_id:
                    return snap_id.strip()
    except Exception as e:
        print(f"Failed to parse AnalyticState.json via snapshot: {e}")
    return None


def get_local_last_login_time():
    """從 AccountState.json 複製快照後解析 LastLoginTime（支援遊戲運行中同步讀取）"""
    try:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if not local_app_data:
            local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")

        base_low = os.path.abspath(os.path.join(local_app_data, "..", "LocalLow"))
        account_path = os.path.join(
            base_low, "Second Dinner", "SNAP", "Standalone", "States", "nvprod", "AccountState.json"
        )

        if not os.path.exists(account_path):
            return "Unknown"

        temp_path = os.path.join(BASE_DIR, "temp_AccountState.json")
        try:
            shutil.copy2(account_path, temp_path)
            read_target = temp_path
        except PermissionError:
            read_target = account_path

        with open(read_target, "r", encoding="utf-8-sig", errors="ignore") as f:
            data = json.load(f)

        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

        utc_time_str = data.get("ClientState", {}).get("LastLoginTime", "")
        if not utc_time_str:
            return "Unknown"

        if utc_time_str.endswith("Z"):
            utc_time_str = utc_time_str[:-1] + "+00:00"

        utc_dt = datetime.fromisoformat(utc_time_str)
        local_dt = utc_dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Failed to parse LastLoginTime via snapshot: {e}")
        return "Unknown"


def launch_browser_context(p, user_data_dir, headless=False):
    lock_file = os.path.join(user_data_dir, "SingletonLock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            print("[Browser] Detected leftover SingletonLock file, automatically cleared.")
        except Exception as e:
            print(f"[Browser] Lock file cleanup note: {e}")

    channels = ["chrome", "msedge"]

    for channel in channels:
        try:
            print(f"[Browser] Attempting to launch system {channel.upper()}...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel=channel,
                headless=headless,
                viewport={"width": 1920, "height": 1080},
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            print(f"[Browser] Successfully launched system {channel.upper()}!")
            return context
        except Exception as e:
            print(f"[Browser] Failed to launch {channel.upper()} ({e}), trying backup channel...")
            continue

    raise RuntimeError(
        "No available Google Chrome or Microsoft Edge detected on your system!\n"
        "Please install Google Chrome or Microsoft Edge and try again."
    )


def encode_bitmask_data(game_id, owned_bool_list):
    byte_count = (len(owned_bool_list) + 7) // 8
    bit_bytes = bytearray(byte_count)
    for idx, is_owned in enumerate(owned_bool_list):
        if is_owned:
            byte_idx = idx // 8
            bit_idx = idx % 8
            bit_bytes[byte_idx] |= (1 << bit_idx)

    payload = game_id.encode("utf-8") + b"\x00" + bytes(bit_bytes)
    compressed = zlib.compress(payload, level=9)
    return base64.b64encode(compressed).decode("utf-8")


def decode_bitmask_data(share_code, total_cards):
    try:
        compressed = base64.b64decode(share_code.strip().encode("utf-8"))
        payload = zlib.decompress(compressed)

        null_pos = payload.find(b"\x00")
        if null_pos == -1:
            return None

        game_id = payload[:null_pos].decode("utf-8")
        bit_bytes = payload[null_pos + 1:]

        owned_indices = []
        for idx in range(total_cards):
            byte_idx = idx // 8
            bit_idx = idx % 8
            if byte_idx < len(bit_bytes):
                if bit_bytes[byte_idx] & (1 << bit_idx):
                    owned_indices.append(idx)

        return {"player": game_id, "indices": owned_indices}
    except Exception as e:
        print(f"Bitmask decode error: {e}")
        return None


def get_global_game_reset_date():
    """全球統一以 UTC 19:00（香港時間凌晨 3:00）作為遊戲換日週期基準"""
    now_utc = datetime.now(timezone.utc)
    if now_utc.hour < 19:
        return (now_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        return now_utc.strftime("%Y-%m-%d")


class MarvelSnapApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Marvel Snap Turbo Center [Pro Ultimate]")
        self.geometry("600x")
        self.resizable(False, False)
        self.configure(fg_color="#0b0e14")

        self.bind("<Unmap>", self.check_minimize)
        self.protocol("WM_DELETE_WINDOW", self.real_exit)

        self.config = load_config()
        self.current_lang = self.config.get("lang", "en")
        self.stop_event = threading.Event()
        self.is_running = False
        self.active_browser_context = None

        t = LANG_DATA[self.current_lang]

        # --- Header Banner ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(15, 5))

        top_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        top_row.pack(fill="x")

        self.badge_label = ctk.CTkLabel(
            top_row,
            text=t["badge"],
            font=ctk.CTkFont(family="Microsoft JhengHei", size=10, weight="bold"),
            text_color="#34d399",
        )
        self.badge_label.pack(side="left")

        btn_group = ctk.CTkFrame(top_row, fg_color="transparent")
        btn_group.pack(side="right")

        self.lang_btn = ctk.CTkButton(
            btn_group,
            text=t["switch_btn"],
            command=self.toggle_language,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold"),
            fg_color="#1f2937",
            hover_color="#374151",
            text_color="#38bdf8",
            corner_radius=6,
            width=38,
            height=32,
        )
        self.lang_btn.pack(side="right")

        self.title_label = ctk.CTkLabel(
            header_frame,
            text=t["title"],
            font=ctk.CTkFont(family="Microsoft JhengHei", size=22, weight="bold"),
            text_color="#f9fafb",
        )
        self.title_label.pack(anchor="w", pady=(4, 0))

        self.subtitle_label = ctk.CTkLabel(
            header_frame,
            text=t["subtitle"],
            font=ctk.CTkFont(family="Microsoft JhengHei", size=11),
            text_color="#9ca3af",
        )
        self.subtitle_label.pack(anchor="w")

        # ==========================================
        # --- 第一部分：卡片收藏展覽區 (Collection Card) ---
        # ==========================================
        collection_card_frame = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color="#131722",
            border_width=1,
            border_color="#1f293d",
        )
        collection_card_frame.pack(padx=25, pady=5, fill="x", ipady=12, ipadx=10)

        status_row = ctk.CTkFrame(collection_card_frame, fg_color="transparent")
        status_row.pack(fill="x", pady=(12, 10), padx=12)

        self.account_status_label = ctk.CTkLabel(
            status_row,
            text=t["account_status"],
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold"),
            text_color="#34d399",
            justify="left"
        )
        self.account_status_label.pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            status_row,
            text=t["refresh_btn"],
            command=self.refresh_local_data,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=11, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#38bdf8",
            corner_radius=6,
            width=150,
            height=26,
        )
        self.refresh_btn.pack(side="right")

        coll_btn_container = ctk.CTkFrame(collection_card_frame, fg_color="transparent")
        coll_btn_container.pack(fill="x", padx=12, pady=(8, 10))

        coll_btn_container.grid_columnconfigure(0, weight=1)
        coll_btn_container.grid_columnconfigure(1, weight=1)

        self.collection_btn = ctk.CTkButton(
            coll_btn_container,
            text=t["collection_btn"],
            command=self.scan_collection_async,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            corner_radius=10,
            height=40,
        )
        self.collection_btn.grid(row=0, column=0, padx=(0, 6))

        self.share_export_btn = ctk.CTkButton(
            coll_btn_container,
            text=t["share_export_btn"],
            command=self.generate_my_share_code,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold"),
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            corner_radius=10,
            height=40
        )
        self.share_export_btn.grid(row=0, column=1, padx=(6, 0))

        self.expansion_frame = ctk.CTkFrame(collection_card_frame, fg_color="transparent")
        self.expansion_frame.pack(fill="x", padx=12, pady=(6, 12))

        share_grid = ctk.CTkFrame(self.expansion_frame, fg_color="transparent")
        share_grid.pack(fill="x")
        share_grid.grid_columnconfigure(0, weight=1)

        self.share_entry = ctk.CTkEntry(
            share_grid,
            placeholder_text=t["share_placeholder"],
            font=ctk.CTkFont(family="Consolas", size=11),
            height=32,
            corner_radius=6,
            fg_color="#0a0c10",
            border_color="#2b374d",
            text_color="#f3f4f6"
        )
        self.share_entry.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.share_import_btn = ctk.CTkButton(
            share_grid,
            text=t["share_import_btn"],
            command=self.load_friend_collection_code,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=11, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=6,
            width=70,
            height=32
        )
        self.share_import_btn.grid(row=0, column=1)

        # ==========================================
        # --- 第二部分：自動化機器人區 (Automation Card) ---
        # ==========================================
        automation_card_frame = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color="#131722",
            border_width=1,
            border_color="#1f293d",
        )
        automation_card_frame.pack(padx=25, pady=5, fill="x", ipady=0, ipadx=10)

        id_container = ctk.CTkFrame(automation_card_frame, fg_color="transparent")
        id_container.pack(fill="x", pady=(6, 4), padx=12)

        id_top_row = ctk.CTkFrame(id_container, fg_color="transparent")
        id_top_row.pack(fill="x", pady=(0, 4))

        left_label_frame = ctk.CTkFrame(id_top_row, fg_color="transparent")
        left_label_frame.pack(side="left")

        self.id_label = ctk.CTkLabel(
            left_label_frame,
            text=t["id_label"],
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold"),
            text_color="#e5e7eb",
        )
        self.id_label.pack(side="left")

        self.invite_bot_link = ctk.CTkButton(
            left_label_frame,
            text=t["invite_bot_link"],
            command=lambda: webbrowser.open(BOT_INVITE_URL),
            font=ctk.CTkFont(family="Microsoft JhengHei", size=11, underline=True),
            text_color="#38bdf8",
            fg_color="transparent",
            hover_color="#1f2937",
            height=20,
            width=0
        )
        self.invite_bot_link.pack(side="left", padx=(8, 0))

        self.clear_session_btn = ctk.CTkButton(
            id_top_row,
            text=t["clear_session_btn"],
            command=self.clear_web_session,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=11, weight="bold"),
            fg_color="#1f2937",
            hover_color="#374151",
            text_color="#9ca3af",
            corner_radius=6,
            width=150,
            height=26,
        )
        self.clear_session_btn.pack(side="right")

        self.id_entry = ctk.CTkEntry(
            id_container,
            placeholder_text=t["id_placeholder"],
            font=ctk.CTkFont(family="Consolas", size=12),
            height=38,
            corner_radius=8,
            fg_color="#0a0c10",
            border_color="#2b374d",
            text_color="#f3f4f6",
        )
        self.id_entry.pack(fill="x")

        saved_id = self.config.get("discord_user_id", "")
        if saved_id:
            self.id_entry.insert(0, saved_id)

        self.check_shop_var = ctk.BooleanVar(value=self.config.get("check_shop", True))
        self.shop_cb = ctk.CTkCheckBox(
            automation_card_frame,
            text=t["shop_cb"],
            variable=self.check_shop_var,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12),
            text_color="#d1d5db",
            corner_radius=6,
            fg_color="#059669",
            hover_color="#047857",
        )
        self.shop_cb.pack(anchor="w", pady=8, padx=15)

        # --- Control Buttons ---
        btn_frame = ctk.CTkFrame(automation_card_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(4, 12))

        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.start_btn = ctk.CTkButton(
            btn_frame,
            text=t["start_btn"],
            command=self.start_automation,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            corner_radius=10,
            height=40,
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text=t["stop_btn"],
            command=self.stop_automation,
            font=ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            corner_radius=10,
            height=40,
            state="disabled",
        )
        self.stop_btn.grid(row=0, column=1, padx=(6, 0))

        # ==========================================
        # --- 第三部分：System Terminal Log ---
        # ==========================================
        log_container = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color="#0f131c",
            border_width=1,
            border_color="#1a2230",
        )
        log_container.pack(padx=25, pady=(5, 5), fill="x", expand=False)

        self.log_title = ctk.CTkLabel(
            log_container,
            text=t["log_title"],
            font=ctk.CTkFont(family="Microsoft JhengHei", size=11, weight="bold"),
            text_color="#60a5fa",
        )
        self.log_title.pack(anchor="w", padx=12, pady=(8, 4))

        self.log_area = ctk.CTkTextbox(
            log_container,
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
            fg_color="#07090f",
            text_color="#38bdf8",
            height=150,
        )
        self.log_area.pack(fill="x", padx=12, pady=(0, 8))
        self.log(t["ready_msg"])

        # --- Footer ---
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=25, pady=(2, 10))

        self.footer_label = ctk.CTkButton(
            footer_frame,
            text=f"🐙 GitHub: {AUTHOR_GITHUB}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#94a3b8",
            fg_color="transparent",
            hover_color="#1f2937",
            height=22,
            command=lambda: webbrowser.open(AUTHOR_GITHUB)
        )
        self.footer_label.pack(side="right")

        self.update_idletasks()
        self.geometry(f"600x{self.winfo_reqheight()}")

        self.tray_icon = None
        threading.Thread(target=self.setup_tray_icon, daemon=True).start()

        self.init_load_local_snap_id()
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def generate_my_share_code(self):
        import tkinter.messagebox as mb
        try:
            cards_db_path = os.path.join(BASE_DIR, "marvel_snap_cards.json")
            self.sync_cards_database_from_github(cards_db_path)
            if not os.path.exists(cards_db_path):
                mb.showerror("Error", "marvel_snap_cards.json not found!")
                return

            with open(cards_db_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)

            all_def_ids = []
            for series_name, card_list in db_data.get("series_groups", {}).items():
                for item in card_list:
                    def_id = item.get("def_id", "").strip()
                    if def_id and def_id not in all_def_ids:
                        all_def_ids.append(def_id)

            local_app_data = os.environ.get("LOCALAPPDATA", "")
            if not local_app_data:
                local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")

            base_low = os.path.abspath(os.path.join(local_app_data, "..", "LocalLow"))
            collection_path = os.path.join(
                base_low, "Second Dinner", "SNAP", "Standalone", "States", "nvprod", "CollectionState.json"
            )

            if not os.path.exists(collection_path):
                mb.showerror("Error", "CollectionState.json not found! Please launch Marvel Snap on Steam first.")
                return

            temp_path = os.path.join(BASE_DIR, "temp_CollectionState.json")
            try:
                shutil.copy2(collection_path, temp_path)
                read_target = temp_path
            except PermissionError:
                read_target = collection_path

            with open(read_target, "r", encoding="utf-8-sig", errors="ignore") as f:
                data = json.load(f)

            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

            owned_raw_cards = data.get("ServerState", {}).get("Cards", [])
            owned_set = {c.get("CardDefId", "").strip() for c in owned_raw_cards if c.get("CardDefId")}
            owned_lower_set = {x.lower() for x in owned_set}

            owned_bool_list = [(def_id in owned_set or def_id.lower() in owned_lower_set) for def_id in all_def_ids]

            game_id = get_local_snap_id() or "Player"
            code = encode_bitmask_data(game_id, owned_bool_list)

            dialog = ctk.CTkToplevel(self)
            dialog.title("Share Code")
            dialog.geometry("500x260")
            dialog.resizable(False, False)
            dialog.attributes("-topmost", True)

            lbl = ctk.CTkLabel(dialog, text=f"🎉 Share Code Generated ({len(code)} chars):", font=("Microsoft JhengHei", 12, "bold"))
            lbl.pack(pady=(15, 5), padx=15, anchor="w")

            txt = ctk.CTkTextbox(dialog, font=("Consolas", 10), height=130)
            txt.pack(fill="x", padx=15, pady=5)
            txt.insert("1.0", code)

            def copy_to_clipboard():
                self.clipboard_clear()
                self.clipboard_append(code)
                self.log(f"Share code copied ({len(code)} chars)!")
                mb.showinfo("Copied", f"Share code copied ({len(code)} chars)!")
                dialog.destroy()

            btn = ctk.CTkButton(dialog, text="📋 Copy to Clipboard", command=copy_to_clipboard, fg_color="#059669", hover_color="#047857")
            btn.pack(pady=10)

        except Exception as e:
            self.log(f"Failed to generate share code: {e}")
            mb.showerror("Error", f"Failed to generate code: {e}")

    def load_friend_collection_code(self):
        import tkinter.messagebox as mb
        code = self.share_entry.get().strip()
        if not code:
            mb.showerror("Error", "Please paste a valid share code into the text field!")
            return

        cards_db_path = os.path.join(BASE_DIR, "marvel_snap_cards.json")
        if not os.path.exists(cards_db_path):
            mb.showerror("Error", "marvel_snap_cards.json not found!")
            return

        with open(cards_db_path, "r", encoding="utf-8") as f:
            db_data = json.load(f)

        all_def_ids = []
        for series_name, card_list in db_data.get("series_groups", {}).items():
            for item in card_list:
                def_id = item.get("def_id", "").strip()
                if def_id and def_id not in all_def_ids:
                    all_def_ids.append(def_id)

        self.log("Decoding share code...")
        decoded = decode_bitmask_data(code, len(all_def_ids))

        if not decoded or "indices" not in decoded:
            mb.showerror("Error", "Invalid or corrupted Share Code!")
            self.log("Share code decoding failed.")
            return

        friend_game_id = decoded.get("player", "Friend")
        card_indexes = decoded.get("indices", [])

        friend_card_ids = [all_def_ids[idx] for idx in card_indexes if idx < len(all_def_ids)]

        self.log(f"Share code decoded! Player: [{friend_game_id}], Cards: {len(friend_card_ids)} (Code length: {len(code)})")
        self.render_gallery_from_card_ids(friend_game_id, friend_card_ids)

    def render_gallery_from_card_ids(self, game_id, owned_def_ids):
        import tkinter.messagebox as mb
        try:
            cards_db_path = os.path.join(BASE_DIR, "marvel_snap_cards.json")
            self.sync_cards_database_from_github(cards_db_path)

            if not os.path.exists(cards_db_path):
                mb.showerror("Error", "marvel_snap_cards.json not found!")
                return

            with open(cards_db_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)

            series_groups = db_data.get("series_groups", {})
            card_meta_map = {}
            for series_name, card_list in series_groups.items():
                for item in card_list:
                    c_name = item.get("name", "").strip()
                    art_url = item.get("image_url", "")
                    cost = item.get("cost", 0)
                    power = item.get("power", 0)
                    def_id = item.get("def_id", "").strip()

                    try:
                        parsed_cost = int(cost)
                    except:
                        parsed_cost = 0

                    try:
                        parsed_power = int(power)
                    except:
                        parsed_power = 0

                    card_info = {
                        "name": c_name,
                        "series": series_name,
                        "cost": parsed_cost,
                        "power": parsed_power,
                        "art_url": art_url,
                        "def_id": def_id,
                    }
                    if def_id:
                        card_meta_map[def_id] = card_info
                        card_meta_map[def_id.lower()] = card_info

            safe_game_id = re.sub(r'[\\/*?:"<>|#]', "_", game_id)

            s5_cards = []
            s4_cards = []
            s3_cards = []
            unclassified_cards = []
            processed_def_ids = set()

            for clean_def_id in owned_def_ids:
                clean_def_id = clean_def_id.strip()
                matched_meta = card_meta_map.get(clean_def_id) or card_meta_map.get(clean_def_id.lower())

                if matched_meta:
                    unique_id = matched_meta["def_id"] or clean_def_id
                    if unique_id not in processed_def_ids:
                        processed_def_ids.add(unique_id)
                        target_series = matched_meta["series"]
                        if "Series 5" in target_series:
                            s5_cards.append(matched_meta)
                        elif "Series 4" in target_series:
                            s4_cards.append(matched_meta)
                        elif "Unclassified" in target_series:
                            unclassified_cards.append(matched_meta)
                        else:
                            s3_cards.append(matched_meta)

            s5_cards.sort(key=lambda x: (x["cost"], x["power"], x["name"]))
            s4_cards.sort(key=lambda x: (x["cost"], x["power"], x["name"]))
            s3_cards.sort(key=lambda x: (x["cost"], x["power"], x["name"]))
            unclassified_cards.sort(key=lambda x: (x["cost"], x["power"], x["name"]))

            total_owned = len(s5_cards) + len(s4_cards) + len(s3_cards) + len(unclassified_cards)

            gallery_html_path = os.path.join(BASE_DIR, f"shared_gallery_{safe_game_id}.html")

            def make_cards_html(card_list):
                items = []
                for c in card_list:
                    art = c["art_url"]
                    name = c["name"]
                    items.append(f"""
                    <div class="card-item">
                        <img src="{art}" onerror="this.onerror=null; this.src='https://via.placeholder.com/130x180/1e293b/60a5fa?text={name}';">
                        <div class="card-name">{name}</div>
                    </div>
                    """)
                return "".join(items)

            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="utf-8">
                <title>Marvel Snap Collection Gallery - {game_id}</title>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0b0e14; color: #f8fafc; padding: 30px; margin: 0; }}
                    .header {{ text-align: center; margin-bottom: 30px; border-bottom: 1px solid #1e293b; padding-bottom: 20px; }}
                    h1 {{ color: #38bdf8; font-size: 2.2em; margin-bottom: 8px; }}
                    .stats {{ font-size: 1.1em; color: #94a3b8; }}
                    .stats span {{ color: #34d399; font-weight: bold; }}
                    .series-title {{ font-size: 1.4em; font-weight: bold; margin-top: 35px; margin-bottom: 15px; display: flex; align-items: center; border-left: 4px solid #38bdf8; padding-left: 10px; }}
                    .s5-title {{ border-color: #f43f5e; color: #fda4af; }}
                    .s4-title {{ border-color: #fbbf24; color: #fde68a; }}
                    .s3-title {{ border-color: #3b82f6; color: #bfdbfe; }}
                    .unclassified-title {{ border-color: #a855f7; color: #d8b4fe; }}
                    .grid {{ display: grid; grid-template-columns: repeat(10, 1fr); gap: 12px; }}
                    .card-item {{ background: #131722; border-radius: 8px; padding: 8px; text-align: center; border: 1px solid #1f293d; transition: transform 0.2s; position: relative; }}
                    .card-item:hover {{ transform: translateY(-4px); border-color: #38bdf8; }}
                    .card-item img {{ width: 100%; height: auto; border-radius: 4px; display: block; }}
                    .card-name {{ margin-top: 8px; font-weight: 600; font-size: 0.75em; color: #e2e8f0; word-wrap: break-word; }}
                    .footer {{ text-align: center; margin-top: 50px; color: #64748b; font-size: 0.9em; border-top: 1px solid #1e293b; padding-top: 20px; }}
                    .footer a {{ color: #38bdf8; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🃏 Shared Marvel Snap Collection Gallery</h1>
                    <div class="stats" style="font-size: 1.3em; margin-bottom: 10px; color: #f3f4f6;">Shared Player: <span>{game_id}</span></div>
                    <div class="stats">Total Owned: <span>{total_owned}</span> | 🔥 Series 5: <span style="color:#f43f5e">{len(s5_cards)}</span> | ⚡ Series 4: <span style="color:#fbbf24">{len(s4_cards)}</span> | 📦 Series 1~3: <span style="color:#3b82f6">{len(s3_cards)}</span> | ❓ Unclassified: <span style="color:#a855f7">{len(unclassified_cards)}</span></div>
                </div>

                <div class="series-title s5-title">🔥 Series 5 Owned Cards ({len(s5_cards)})</div>
                <div class="grid">{make_cards_html(s5_cards)}</div>

                <div class="series-title s4-title">⚡ Series 4 Owned Cards ({len(s4_cards)})</div>
                <div class="grid">{make_cards_html(s4_cards)}</div>

                <div class="series-title s3-title">📦 Series 1 ~ 3 Owned Cards ({len(s3_cards)})</div>
                <div class="grid">{make_cards_html(s3_cards)}</div>

                <div class="series-title unclassified-title">❓ Unclassified Owned Cards ({len(unclassified_cards)})</div>
                <div class="grid">{make_cards_html(unclassified_cards)}</div>

                <div class="footer">
                    Generated by Marvel Snap Turbo | <a href="{AUTHOR_GITHUB}" target="_blank">GitHub Repository</a>
                </div>
            </body>
            </html>
            """

            with open(gallery_html_path, "w", encoding="utf-8") as hf:
                hf.write(html_content)

            self.log(f"Shared gallery rendered successfully: {gallery_html_path}")

            abs_gallery_path = os.path.abspath(gallery_html_path)
            if os.name == "nt":
                os.startfile(abs_gallery_path)
            else:
                webbrowser.open(f"file://{abs_gallery_path}")

            mb.showinfo("Success", f"Loaded gallery for [{game_id}]!\nPath: {gallery_html_path}")

        except Exception as e:
            self.log(f"Failed to render shared gallery: {e}")
            mb.showerror("Error", f"Failed to render shared gallery: {e}")

    def create_tray_image(self):
        image = Image.new("RGB", (64, 64), (11, 14, 20))
        dc = ImageDraw.Draw(image)
        dc.ellipse((8, 8, 56, 56), fill="#059669")
        dc.text((22, 22), "S", fill="#ffffff")
        return image

    def setup_tray_icon(self):
        menu = (
            item("Show Window", self.show_window_from_tray, default=True),
            item("Exit Application", self.exit_app_from_tray)
        )
        self.tray_icon = pystray.Icon(
            "marvel_snap_turbo",
            self.create_tray_image(),
            "Marvel Snap Turbo",
            menu
        )
        self.tray_icon.run()

    def check_minimize(self, event):
        if event.widget == self and self.state() == "iconic":
            self.withdraw()
            self.log("Window minimized to system tray. Program is running in background.")

    def show_window_from_tray(self, icon, item):
        self.after(0, self.deiconify)
        self.after(0, lambda: self.state("normal"))
        self.log("Window restored from system tray.")

    def real_exit(self):
        if self.tray_icon:
            self.tray_icon.stop()
        self.stop_event.set()
        if self.active_browser_context:
            try:
                self.active_browser_context.close()
            except:
                pass
        self.destroy()

    def exit_app_from_tray(self, icon, item):
        if self.tray_icon:
            self.tray_icon.stop()
        self.stop_event.set()
        if self.active_browser_context:
            try:
                self.active_browser_context.close()
            except:
                pass
        self.after(0, self.destroy)

    def refresh_local_data(self):
        self.log("Manual refresh triggered: Scanning local states...")
        snap_id = get_local_snap_id()
        login_time = get_local_last_login_time()
        
        if snap_id:
            status_text = f"🎮 Game Account: {snap_id}\n🕒 Last Login: {login_time}"
            self.account_status_label.configure(text=status_text)
            self.log(f"Successfully refreshed! Account: {snap_id} (Last Login: {login_time})")
        else:
            self.account_status_label.configure(text=LANG_DATA[self.current_lang]["account_status"])
            self.log("Refresh note: Local SnapId not found or game not launched yet.")

    def clear_web_session(self):
        import tkinter.messagebox as mb
        if mb.askyesno("Clear Web Session", "Are you sure you want to clear web login session?\nThis will clear browser cookies and cache."):
            if os.path.exists(USER_DATA_DIR):
                try:
                    shutil.rmtree(USER_DATA_DIR)
                    self.log("Web session cache cleared! Ready for a new web login.")
                    mb.showinfo("Success", "Web session cleared successfully!")
                except Exception as e:
                    self.log(f"Failed to clear web session: {e}")
            else:
                self.log("No active web session found.")
                mb.showinfo("Info", "No active web session found.")

    def init_load_local_snap_id(self):
        snap_id = get_local_snap_id()
        login_time = get_local_last_login_time()
        if snap_id:
            status_text = f"🎮 Game Account: {snap_id}\n🕒 Last Login: {login_time}"
            self.account_status_label.configure(text=status_text)
            self.log(f"Successfully loaded SnapId: {snap_id} (Last Login: {login_time})")
        else:
            self.log("AnalyticState.json SnapId not found yet. Please ensure Marvel Snap has been launched.")

    def check_for_updates(self):
        try:
            self.log("Checking for software updates via GitHub Releases API...")
            headers = {"Accept": "application/vnd.github.v3+json"}
            response = requests.get(GITHUB_RELEASE_API, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                raw_tag = data.get("tag_name", "").strip()
                remote_version = raw_tag.lstrip("vV")
                release_notes = data.get("body", "")
                download_url = data.get("html_url", AUTHOR_GITHUB)

                if remote_version and remote_version != CURRENT_VERSION:
                    self.log(f"New version available: v{remote_version} (Current: v{CURRENT_VERSION})")
                    self.after(0, lambda: self.show_update_dialog(remote_version, release_notes, download_url))
                else:
                    self.log("Software is up to date.")
            else:
                self.log(f"Could not check for updates (GitHub API status: {response.status_code}).")
        except Exception as e:
            self.log(f"Update check failed: {e}")

    def show_update_dialog(self, version, notes, url):
        import tkinter.messagebox as mb
        msg = f"New version v{version} available!\n\nRelease Notes:\n{notes}\n\nWould you like to open GitHub to download?"
        if mb.askyesno("Update Available", msg):
            webbrowser.open(url)

    def toggle_language(self):
        self.current_lang = "en" if self.current_lang == "zh" else "zh"
        self.config["lang"] = self.current_lang
        save_config(self.config)

        t = LANG_DATA[self.current_lang]

        self.badge_label.configure(text=t["badge"])
        self.lang_btn.configure(text=t["switch_btn"])
        self.clear_session_btn.configure(text=t["clear_session_btn"])
        self.refresh_btn.configure(text=t["refresh_btn"])
        self.title_label.configure(text=t["title"])
        self.subtitle_label.configure(text=t["subtitle"])

        current_status = self.account_status_label.cget("text")
        if "Game Account" in current_status or "遊戲帳號" in current_status:
            pass
        else:
            self.account_status_label.configure(text=t["account_status"])

        self.id_label.configure(text=t["id_label"])
        self.id_entry.configure(placeholder_text=t["id_placeholder"])
        self.invite_bot_link.configure(text=t["invite_bot_link"])
        self.shop_cb.configure(text=t["shop_cb"])
        self.collection_btn.configure(text=t["collection_btn"])
        self.share_export_btn.configure(text=t["share_export_btn"])
        self.share_import_btn.configure(text=t["share_import_btn"])
        self.share_entry.configure(placeholder_text=t["share_placeholder"])
        self.start_btn.configure(text=t["start_btn"])
        self.stop_btn.configure(text=t["stop_btn"])
        self.log_title.configure(text=t["log_title"])

        self.log(f"Language switched to {'English' if self.current_lang == 'en' else 'Traditional Chinese'}.")

    def log(self, message):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_area.insert("end", f"{timestamp} {message}\n")
        self.log_area.see("end")

    def scan_collection_async(self):
        self.collection_btn.configure(state="disabled")
        threading.Thread(target=self.scan_collection, daemon=True).start()

    def sync_cards_database_from_github(self, cards_db_path):
        self.log("Checking for card database updates from GitHub...")
        try:
            response = requests.get(GITHUB_CARDS_URL, timeout=15)
            if response.status_code == 200:
                remote_data = response.json()
                remote_last_updated = remote_data.get("last_updated", "")

                if not os.path.exists(cards_db_path):
                    self.log("Card database not found locally. Downloading from GitHub...")
                    with open(cards_db_path, "w", encoding="utf-8") as f:
                        json.dump(remote_data, f, ensure_ascii=False, indent=2)
                    self.log("Card database downloaded successfully!")
                else:
                    with open(cards_db_path, "r", encoding="utf-8") as f:
                        local_data = json.load(f)
                    local_last_updated = local_data.get("last_updated", "")

                    if remote_last_updated and remote_last_updated != local_last_updated:
                        self.log(f"New card version found! (Local: {local_last_updated} -> Remote: {remote_last_updated})")
                        with open(cards_db_path, "w", encoding="utf-8") as f:
                            json.dump(remote_data, f, ensure_ascii=False, indent=2)
                        self.log("Local card database updated to the latest version!")
                    else:
                        self.log("Local card database is already up to date.")
            else:
                self.log(f"Failed to fetch updates from GitHub (Status: {response.status_code}), using local file.")
        except Exception as e:
            self.log(f"Failed to connect to GitHub: {e}, using local file.")

    def scan_collection(self):
        import tkinter.messagebox as mb
        try:
            cards_db_path = os.path.join(BASE_DIR, "marvel_snap_cards.json")
            self.sync_cards_database_from_github(cards_db_path)

            if not os.path.exists(cards_db_path):
                mb.showerror("Error", "marvel_snap_cards.json not found!")
                self.after(0, lambda: self.collection_btn.configure(state="normal"))
                return

            with open(cards_db_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)

            all_def_ids = []
            for series_name, card_list in db_data.get("series_groups", {}).items():
                for item in card_list:
                    def_id = item.get("def_id", "").strip()
                    if def_id and def_id not in all_def_ids:
                        all_def_ids.append(def_id)

            local_app_data = os.environ.get("LOCALAPPDATA", "")
            if not local_app_data:
                local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")

            base_low = os.path.abspath(os.path.join(local_app_data, "..", "LocalLow"))
            collection_path = os.path.join(
                base_low, "Second Dinner", "SNAP", "Standalone", "States", "nvprod", "CollectionState.json"
            )

            if not os.path.exists(collection_path):
                mb.showerror("Error", "CollectionState.json not found!")
                self.after(0, lambda: self.collection_btn.configure(state="normal"))
                return

            temp_path = os.path.join(BASE_DIR, "temp_CollectionState.json")
            try:
                shutil.copy2(collection_path, temp_path)
                read_target = temp_path
            except PermissionError:
                read_target = collection_path

            with open(read_target, "r", encoding="utf-8-sig", errors="ignore") as f:
                data = json.load(f)

            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

            owned_raw_cards = data.get("ServerState", {}).get("Cards", [])
            owned_set = {c.get("CardDefId", "").strip() for c in owned_raw_cards if c.get("CardDefId")}

            friend_card_ids = []
            for def_id in all_def_ids:
                if def_id in owned_set or def_id.lower() in {x.lower() for x in owned_set}:
                    friend_card_ids.append(def_id)

            game_id = get_local_snap_id() or "Player"
            self.render_gallery_from_card_ids(game_id, friend_card_ids)

        except Exception as e:
            self.log(f"Scan failed: {e}")
            mb.showerror("Error", f"Scan failed: {e}")
        finally:
            self.after(0, lambda: self.collection_btn.configure(state="normal"))

    def start_automation(self):
        discord_id = self.id_entry.get().strip()
        if not discord_id:
            import tkinter.messagebox as mb
            mb.showerror("Error", "Please enter your Discord User ID first!")
            return

        self.config["discord_user_id"] = discord_id
        self.config["check_shop"] = self.check_shop_var.get()
        save_config(self.config)

        self.stop_event.clear()
        self.start_btn.configure(state="disabled", fg_color="#374151")
        self.stop_btn.configure(state="normal")
        self.id_entry.configure(state="disabled")
        self.shop_cb.configure(state="disabled")
        self.collection_btn.configure(state="normal")
        self.lang_btn.configure(state="disabled")
        self.clear_session_btn.configure(state="disabled")
        self.refresh_btn.configure(state="disabled")

        self.log("Automation scheduled & started! Running first check immediately...")

        threading.Thread(target=self.automation_loop, args=(discord_id,), daemon=True).start()

    def stop_automation(self):
        self.stop_event.set()
        self.log("Stopping automation... Force closing active browser process...")
        if self.active_browser_context:
            try:
                self.active_browser_context.close()
                self.log("Active browser process terminated instantly.")
            except Exception as e:
                self.log(f"Browser cleanup note: {e}")

    def reset_ui(self):
        self.start_btn.configure(state="normal", fg_color="#059669")
        self.stop_btn.configure(state="disabled")
        self.id_entry.configure(state="normal")
        self.shop_cb.configure(state="normal")
        self.collection_btn.configure(state="normal")
        self.lang_btn.configure(state="normal")
        self.clear_session_btn.configure(state="normal")
        self.refresh_btn.configure(state="normal")
        self.log("Automation completely stopped.")

    def automation_loop(self, discord_id):
        self.run_once(discord_id)
        last_reset_date = get_global_game_reset_date()

        while not self.stop_event.is_set():
            current_reset_date = get_global_game_reset_date()

            if current_reset_date != last_reset_date:
                self.log(f"Reached global shop reset time (19:00 UTC). Starting scheduled daily check & shop alert...")
                self.run_once(discord_id)
                last_reset_date = current_reset_date

            for _ in range(10):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

        self.reset_ui()

    def run_once(self, discord_id):
        if self.stop_event.is_set():
            return

        status_screenshot = os.path.join(BASE_DIR, "status_screenshot.png")
        stitched_shop_image = os.path.join(BASE_DIR, "shop_stitched_overview.png")
        history = load_history()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        check_shop = self.check_shop_var.get()

        temp_captured_files = []

        try:
            self.log("Launching browser in background (using system Chrome/Edge)...")
            with sync_playwright() as p:
                if self.stop_event.is_set():
                    return

                browser = launch_browser_context(p, USER_DATA_DIR, headless=False)
                self.active_browser_context = browser

                page = browser.new_page()

                self.log("Navigating to Marvel Snap web shop...")
                page.goto("https://shop.marvelsnap.com/", timeout=90000)

                self.log("Checking login status...")
                time.sleep(3)

                # ==========================================
                # 🔒 登入狀態檢測與等待登入防護機制 (v8.2)
                # ==========================================
                login_btn_locator = page.locator("button:has-text('Log in')").or_(page.locator("text=Log in"))
                
                max_wait_login = 180  # 最多等待 3 分鐘讓用戶登入
                waited_time = 0
                
                while login_btn_locator.count() > 0 and waited_time < max_wait_login:
                    if self.stop_event.is_set():
                        break
                    if waited_time == 0:
                        self.log("⚠️ Not logged in or session cookie expired! Please log in via the browser window...")
                    
                    time.sleep(3)
                    waited_time += 3
                    
                    if login_btn_locator.count() == 0:
                        self.log("✅ Login detected successfully! Continuing automation...")
                        break
                
                if login_btn_locator.count() > 0:
                    self.log("❌ Login timeout or not logged in. Sending notification and aborting this run.")
                    try:
                        self.send_notification(discord_id, "⚠️ [Marvel Snap Turbo] Not logged in or web session cookie expired. Please open the app and log in to continue.")
                    except:
                        pass
                    browser.close()
                    self.active_browser_context = None
                    return
                # ==========================================

                if self.stop_event.is_set():
                    browser.close()
                    self.active_browser_context = None
                    return

                local_snap_id = get_local_snap_id()
                login_time = get_local_last_login_time()
                if local_snap_id:
                    self.log(f"Successfully obtained local game account ID: {local_snap_id}")
                    self.after(0, lambda gid=local_snap_id, lt=login_time: self.account_status_label.configure(text=f"🎮 Game Account: {gid}\n🕒 Last Login: {lt}"))

                reward_card = page.locator("img[alt='Credits']").locator("xpath=ancestor::div[contains(@class, 'sc-5f135772-0')][1]")
                claim_btn_locator = page.locator("text=免費!").or_(page.locator("text=Free!"))

                self.log("Checking daily free reward status...")

                if reward_card.count() > 0:
                    reward_card.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    page.evaluate("window.scrollBy(0, -120)")
                    time.sleep(0.3)

                    if claim_btn_locator.count() > 0:
                        self.log("Found claimable free reward! Claiming...")
                        reward_card.screenshot(path=status_screenshot)
                        claim_btn_locator.first.click(timeout=5000)
                        time.sleep(3)

                        self.log("Waiting 3s for reward popup modal and checking 'Back to Shop' button...")
                        time.sleep(3)
                        try:
                            back_to_shop_btn = page.locator("button.sc-79dab32c-0.iMOeor:has(span.reward-result-button-text)")
                            if back_to_shop_btn.is_visible(timeout=3000):
                                self.log("Detected 'Back to Shop' reward result popup modal! Clicking it...")
                                back_to_shop_btn.first.click(timeout=3000)
                                time.sleep(1.5)
                                self.log("Successfully returned to shop from popup modal.")
                            else:
                                self.log("No 'Back to Shop' modal popup detected after claiming.")
                        except Exception as pop_ex:
                            self.log(f"Could not find or click 'Back to Shop' button: {pop_ex}")

                        reward_card.screenshot(path=status_screenshot)
                        self.send_notification_with_image(discord_id, "🎉 [Marvel Snap Turbo] Daily free reward claimed!", status_screenshot)
                        self.log("Free reward claimed and notification sent!")
                    else:
                        self.log("Reward is currently on cooldown.")
                        reward_card.screenshot(path=status_screenshot)
                        self.send_notification_with_image(discord_id, "ℹ️ [Marvel Snap Turbo] Reward is on cooldown.", status_screenshot)
                else:
                    self.log("Could not find daily reward card.")

                new_shop_image_paths = []
                if check_shop and not self.stop_event.is_set():
                    self.log("Scanning shop items and bundles...")
                    page.evaluate("window.scrollBy(0, 700)")
                    time.sleep(1.5)

                    shop_cards = page.locator(".cjGdRj")
                    card_count = shop_cards.count()
                    self.log(f"Found {card_count} shop item cards on screen.")

                    if card_count > 0:
                        for i in range(card_count):
                            if self.stop_event.is_set():
                                break
                            try:
                                card = shop_cards.nth(i)
                                card.scroll_into_view_if_needed()
                                time.sleep(0.4)
                                page.evaluate("window.scrollBy(0, -100)")
                                time.sleep(0.2)

                                card_text = card.inner_text()
                                if not card_text.strip():
                                    card_text = f"unknown_card_{i}_{time.time()}"

                                text_hash = get_text_hash(card_text)
                                item_path = os.path.join(BASE_DIR, f"temp_item_{i}.png")
                                temp_captured_files.append(item_path)

                                if text_hash in history:
                                    self.log(f"Item #{i+1} skipped (within 8 days).")
                                else:
                                    self.log(f"New item detected! Item #{i+1} added.")
                                    card.screenshot(path=item_path)
                                    history[text_hash] = today_str
                                    new_shop_image_paths.append(item_path)

                            except Exception as ex:
                                self.log(f"Error processing item #{i+1}: {ex}")

                        save_history(history)

                        if new_shop_image_paths and not self.stop_event.is_set():
                            self.log(f"Stitching {len(new_shop_image_paths)} items dynamically into {min(len(new_shop_image_paths), 4)}-column grid...")
                            stitched_path = stitch_shop_images(new_shop_image_paths, stitched_shop_image)

                            if stitched_path and os.path.exists(stitched_path):
                                msg = f"🛒 [Marvel Snap Turbo Shop Alert] New Bundles Grid Overview (Total {len(new_shop_image_paths)} items):"
                                self.send_notification_with_image(discord_id, msg, stitched_path)
                                self.log("Grid shop overview sent to Discord!")
                        elif not new_shop_image_paths and not self.stop_event.is_set():
                            self.send_notification(discord_id, "🛒 [Marvel Snap Turbo Shop Alert] No new shop items found.")
                    else:
                        self.log("No shop item cards found.")
                else:
                    self.log("Shop check skipped or task stopped.")

                browser.close()
                self.active_browser_context = None
                self.log("Task completed successfully!")

        except Exception as e:
            self.active_browser_context = None
            if self.stop_event.is_set():
                self.log("Task manually interrupted and stopped by user.")
            else:
                self.log(f"Execution error: {e}")
                try:
                    self.send_notification(discord_id, f"❌ Error occurred: {e}")
                except:
                    pass

        for p_file in [status_screenshot, stitched_shop_image] + temp_captured_files:
            if os.path.exists(p_file):
                try:
                    os.remove(p_file)
                except:
                    pass

    def send_notification_with_image(self, user_id, message, image_path):
        try:
            with open(image_path, "rb") as f:
                files = {"file": ("screenshot.png", f, "image/png")}
                data = {"user_id": user_id, "message": message}
                response = requests.post(RENDER_API_URL, data=data, files=files, timeout=45)
                if response.status_code == 200:
                    return
        except Exception as e:
            self.log(f"Failed to send image notification (Render might be sleeping): {e}")

        self.wake_up_render_server()
        try:
            self.log("Retrying to send image notification...")
            with open(image_path, "rb") as f:
                files = {"file": ("screenshot.png", f, "image/png")}
                data = {"user_id": user_id, "message": message}
                requests.post(RENDER_API_URL, data=data, files=files, timeout=60)
                self.log("Retry image send successful!")
        except Exception as e2:
            self.log(f"Retry image send failed: {e2}")

    def send_notification(self, user_id, message):
        try:
            payload = {"user_id": user_id, "message": message}
            response = requests.post(RENDER_API_URL, json=payload, timeout=20)
            if response.status_code == 200:
                return
        except Exception as e:
            self.log(f"Failed to send message notification (Render might be sleeping): {e}")

        self.wake_up_render_server()
        try:
            self.log("Retrying to send message notification...")
            payload = {"user_id": user_id, "message": message}
            requests.post(RENDER_API_URL, json=payload, timeout=30)
            self.log("Retry message send successful!")
        except Exception as e2:
            self.log(f"Retry message send failed: {e2}")

    def wake_up_render_server(self):
        try:
            self.log("Detected Render server sleeping, executing extended wake-up sequence...")
            for i in range(3):
                try:
                    requests.get(RENDER_PING_URL, timeout=10)
                    self.log(f"   Wake-up ping #{i+1} sent.")
                except:
                    pass
                if i < 2:
                    time.sleep(3)
            self.log("Waiting for server startup completion (6s)...")
            time.sleep(6)
        except Exception as ex:
            self.log(f"Failed to wake up server: {ex}")


if __name__ == "__main__":
    app = MarvelSnapApp()
    app.mainloop()
