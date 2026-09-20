import os
import json
import threading
from pathlib import Path

import requests
import yt_dlp

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.video import Video
from kivy.uix.widget import Widget

try:
    from android.storage import app_storage_path
    ANDROID = True
except Exception:
    ANDROID = False


APP_NAME = "PYTUBE"
API_KEY = "AIzaSyB86M1FF8FImNo9-H4zBbkaKU17VjwK7Zk"
API_URL = "https://www.googleapis.com/youtube/v3/search"


class AndroidTube(App):
    def build(self):
        self.title = APP_NAME
        self.user_dir = Path(app_storage_path()) if ANDROID else Path(self.user_data_dir)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.user_dir / "pytube_history.json"
        self.downloads_file = self.user_dir / "pytube_downloads.json"
        self.download_dir = self.user_dir / "Downloads"
        self.download_dir.mkdir(exist_ok=True)
        self.history = self.load_json(self.history_file)
        self.downloads = self.load_json(self.downloads_file)
        self.current_video = None

        Window.clearcolor = (0.055, 0.055, 0.055, 1)

        self.sm = ScreenManager()
        self.sm.add_widget(self.make_main_screen())
        self.sm.add_widget(self.make_player_screen())
        self.show_home()
        return self.sm

    # ---------------- JSON ----------------
    def load_json(self, path):
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def save_json(self, path, data):
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------------- API ----------------
    def youtube_search(self, query, search_type="video", channel_id=None,
                       video_duration=None, max_results=20):
        if not API_KEY or API_KEY == "BURAYA_YOUTUBE_API_KEY_YAZ":
            raise RuntimeError("main_android.py içindeki API_KEY alanına YouTube Data API anahtarını yaz.")

        params = {
            "part": "snippet",
            "q": query if query else " ",
            "type": search_type,
            "maxResults": max_results,
            "regionCode": "TR",
            "key": API_KEY,
        }
        if channel_id:
            params["channelId"] = channel_id
            params["type"] = "video"
        if video_duration:
            params["videoDuration"] = video_duration

        response = requests.get(API_URL, params=params, timeout=20)
        try:
            data = response.json()
        except Exception:
            raise RuntimeError("YouTube'dan geçerli cevap alınamadı.")
        if response.status_code != 200:
            err = data.get("error", {})
            raise RuntimeError(err.get("message", "YouTube API hatası."))
        return data.get("items", [])

    def convert_item(self, item):
        kind = item.get("id", {}).get("kind", "")
        snippet = item.get("snippet", {})
        thumbs = snippet.get("thumbnails", {})
        thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")

        if kind == "youtube#channel":
            return {
                "is_channel": True,
                "id": item.get("id", {}).get("channelId", ""),
                "title": snippet.get("channelTitle", snippet.get("title", "Kanal")),
                "description": snippet.get("description", "")[:220],
                "thumbnail": thumb,
            }
        return {
            "is_channel": False,
            "id": item.get("id", {}).get("videoId", ""),
            "title": snippet.get("title", "Başlıksız video"),
            "channel": snippet.get("channelTitle", "Bilinmeyen kanal"),
            "description": snippet.get("description", "")[:220],
            "published": snippet.get("publishedAt", "")[:10],
            "thumbnail": thumb,
        }

    # ---------------- UI ----------------
    def make_main_screen(self):
        screen = Screen(name="main")
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        self.search_box = TextInput(
            hint_text="YouTube'da video veya kanal ara...",
            multiline=False,
            size_hint_x=1,
            font_size=dp(16),
            background_color=(0.10, 0.10, 0.10, 1),
            foreground_color=(1, 1, 1, 1),
        )
        self.search_box.bind(on_text_validate=lambda *_: self.search())
        top.add_widget(self.search_box)
        btn = Button(text="🔍 Ara", size_hint_x=None, width=dp(82), font_size=dp(14))
        btn.bind(on_release=lambda *_: self.search())
        top.add_widget(btn)
        root.add_widget(top)

        nav = ScrollView(size_hint_y=None, height=dp(48), do_scroll_y=False)
        navbox = BoxLayout(size_hint_x=None, width=dp(610), spacing=dp(5))
        for text, callback in [
            ("🏠 Ana Sayfa", self.show_home),
            ("📱 Shorts", self.show_shorts),
            ("🕘 Geçmiş", self.show_history),
            ("📥 İndirilenler", self.show_downloads),
            ("🎮 Oyun", lambda: self.search_text("oyun")),
            ("🎵 Müzik", lambda: self.search_text("müzik")),
        ]:
            b = Button(text=text, size_hint_x=None, width=dp(100), font_size=dp(12))
            b.bind(on_release=lambda _, cb=callback: cb())
            navbox.add_widget(b)
        nav.add_widget(navbox)
        root.add_widget(nav)

        self.page_title = Label(
            text="Ana Sayfa", size_hint_y=None, height=dp(42),
            font_size=dp(21), bold=True, halign="left", valign="middle"
        )
        self.page_title.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        root.add_widget(self.page_title)

        self.scroll = ScrollView(do_scroll_x=False)
        self.results_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(0, 0, 0, dp(12)))
        self.results_box.bind(minimum_height=self.results_box.setter("height"))
        self.scroll.add_widget(self.results_box)
        root.add_widget(self.scroll)

        screen.add_widget(root)
        return screen

    def make_player_screen(self):
        screen = Screen(name="player")
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))
        toolbar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        back = Button(text="← Geri", size_hint_x=None, width=dp(80))
        back.bind(on_release=lambda *_: self.back_to_results())
        toolbar.add_widget(back)
        self.player_title = Label(text="Video", halign="left", valign="middle")
        self.player_title.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        toolbar.add_widget(self.player_title)
        download = Button(text="📥 İndir", size_hint_x=None, width=dp(90))
        download.bind(on_release=lambda *_: self.download_current_video())
        toolbar.add_widget(download)
        root.add_widget(toolbar)

        self.video = Video(state="stop", options={"eos": "stop"}, allow_stretch=True)
        root.add_widget(self.video)
        controls = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        play = Button(text="▶ / ⏸")
        play.bind(on_release=lambda *_: self.toggle_play())
        controls.add_widget(play)
        stop = Button(text="⏹ Durdur")
        stop.bind(on_release=lambda *_: self.stop_video())
        controls.add_widget(stop)
        root.add_widget(controls)
        screen.add_widget(root)
        return screen

    def clear_results(self):
        self.results_box.clear_widgets()

    def add_label(self, text):
        lbl = Label(text=text, size_hint_y=None, height=dp(36), font_size=dp(17), bold=True, halign="left")
        lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.results_box.add_widget(lbl)

    def add_card(self, data):
        card = BoxLayout(size_hint_y=None, height=dp(130), spacing=dp(8), padding=dp(6))
        if data.get("thumbnail"):
            img = AsyncImage(source=data["thumbnail"], size_hint_x=None, width=dp(150), allow_stretch=True, keep_ratio=False)
            card.add_widget(img)
        else:
            card.add_widget(Widget(size_hint_x=None, width=dp(150)))

        textbox = BoxLayout(orientation="vertical", spacing=dp(3))
        title = data.get("title", "Video")
        if data.get("is_channel"):
            title = "👤 " + title
        t = Label(text=title, font_size=dp(15), bold=True, halign="left", valign="top")
        t.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        textbox.add_widget(t)
        if not data.get("is_channel"):
            c = Label(text="📺 " + data.get("channel", ""), font_size=dp(12), color=(0.78,0.78,0.78,1), halign="left")
            c.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            textbox.add_widget(c)
        d = Label(text=data.get("description", ""), font_size=dp(11), color=(0.65,0.65,0.65,1), halign="left", valign="top")
        d.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        textbox.add_widget(d)
        open_btn = Button(text="Aç", size_hint_y=None, height=dp(34))
        open_btn.bind(on_release=lambda *_ , item=data: self.item_clicked(item))
        textbox.add_widget(open_btn)
        card.add_widget(textbox)
        self.results_box.add_widget(card)

    def show_message(self, text):
        self.clear_results()
        self.add_label(text)

    # ---------------- Pages ----------------
    def show_home(self):
        self.sm.current = "main"
        self.page_title.text = "🏠 Ana Sayfa"
        self.clear_results()
        if self.history:
            self.add_label("🕒 Son İzlediklerin")
            for item in self.history[:3]:
                self.add_card(item)
        self.add_label("⏳ Öneriler yükleniyor...")
        threading.Thread(target=self.fetch_home_content, daemon=True).start()

    def fetch_home_content(self):
        try:
            query = self.history[0].get("channel", "Minecraft") if self.history else "Minecraft"
            rec = self.youtube_search(query, "video", max_results=6)
            shorts = self.youtube_search("#shorts", "video", video_duration="short", max_results=5)
            recommendations = [self.convert_item(i) for i in rec if i.get("id", {}).get("kind") == "youtube#video"]
            short_items = [self.convert_item(i) for i in shorts if i.get("id", {}).get("kind") == "youtube#video"]
            Clock.schedule_once(lambda *_: self.populate_home(recommendations, short_items), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_: self.show_message("Hata: " + str(e)), 0)

    def populate_home(self, recommendations, shorts):
        for widget in list(self.results_box.children):
            if isinstance(widget, Label) and "Öneriler" in widget.text:
                self.results_box.remove_widget(widget)
                break
        if recommendations:
            self.add_label("✨ Sizin İçin Önerilenler")
            for item in recommendations:
                self.add_card(item)
        if shorts:
            self.add_label("📱 Popüler Shorts")
            for item in shorts:
                self.add_card(item)

    def search(self):
        query = self.search_box.text.strip()
        if query:
            self.search_text(query)

    def search_text(self, query):
        self.search_box.text = query
        self.page_title.text = f'"{query}" sonuçları'
        self.clear_results()
        self.add_label("⏳ Aranıyor...")
        threading.Thread(target=self.search_worker, args=(query,), daemon=True).start()

    def search_worker(self, query):
        try:
            items = self.youtube_search(query, "video,channel")
            parsed = [self.convert_item(x) for x in items]
            Clock.schedule_once(lambda *_: self.populate_results(parsed), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_: self.show_message("Hata: " + str(e)), 0)

    def populate_results(self, items):
        self.clear_results()
        if not items:
            self.add_label("Sonuç bulunamadı.")
            return
        for item in items:
            if item.get("id"):
                self.add_card(item)

    def show_shorts(self):
        self.page_title.text = "📱 Popüler Shorts"
        self.clear_results()
        self.add_label("⏳ Yükleniyor...")
        threading.Thread(target=self.shorts_worker, daemon=True).start()

    def shorts_worker(self):
        try:
            items = self.youtube_search("#shorts", "video", video_duration="short", max_results=15)
            parsed = [self.convert_item(x) for x in items]
            Clock.schedule_once(lambda *_: self.populate_results(parsed), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_: self.show_message("Hata: " + str(e)), 0)

    def show_history(self):
        self.page_title.text = "🕘 İzleme Geçmişi"
        self.clear_results()
        for item in self.history:
            self.add_card(item)
        if not self.history:
            self.add_label("Geçmiş boş.")

    def show_downloads(self):
        self.page_title.text = "📥 İndirilenler"
        self.clear_results()
        for item in self.downloads:
            self.add_card(item)
        if not self.downloads:
            self.add_label("İndirilen video yok.")

    def item_clicked(self, data):
        if data.get("is_channel"):
            self.page_title.text = "👤 " + data.get("title", "Kanal")
            self.clear_results()
            self.add_label("⏳ Kanal videoları yükleniyor...")
            threading.Thread(target=self.channel_worker, args=(data.get("id", ""),), daemon=True).start()
        else:
            self.play_video(data)

    def channel_worker(self, channel_id):
        try:
            items = self.youtube_search("", channel_id=channel_id, max_results=20)
            parsed = [self.convert_item(x) for x in items if x.get("id", {}).get("kind") == "youtube#video"]
            Clock.schedule_once(lambda *_: self.populate_results(parsed), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_: self.show_message("Hata: " + str(e)), 0)

    # ---------------- Playback ----------------
    def play_video(self, video):
        video_id = video.get("id")
        if not video_id:
            return
        self.current_video = video
        self.history = [x for x in self.history if x.get("id") != video_id]
        self.history.insert(0, video)
        self.history = self.history[:50]
        self.save_json(self.history_file, self.history)
        self.player_title.text = video.get("title", "Video")
        self.video.state = "stop"
        self.video.source = ""
        self.sm.current = "player"
        threading.Thread(target=self.stream_worker, args=(video_id,), daemon=True).start()

    def stream_worker(self, video_id):
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            opts = {
                "format": "best[ext=mp4]/best",
                "quiet": True,
                "noplaylist": True,
                "ignoreerrors": False,
                "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get("url") if info else None
                if not stream_url:
                    raise RuntimeError("Oynatılabilir akış bağlantısı bulunamadı.")
            Clock.schedule_once(lambda *_: self.start_stream(stream_url), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_: self.player_error(str(e)), 0)

    def start_stream(self, stream_url):
        self.video.source = stream_url
        self.video.state = "play"

    def toggle_play(self):
        if self.video.state == "play":
            self.video.state = "pause"
        else:
            self.video.state = "play"

    def stop_video(self):
        self.video.state = "stop"

    def player_error(self, message):
        self.video.state = "stop"
        self.player_title.text = "Hata: " + message

    def back_to_results(self):
        self.video.state = "stop"
        self.sm.current = "main"

    # ---------------- Download ----------------
    def download_current_video(self):
        if not self.current_video:
            return
        video = dict(self.current_video)
        threading.Thread(target=self.download_worker, args=(video,), daemon=True).start()
        self.player_title.text = "📥 İndirme başladı..."

    def download_worker(self, video):
        try:
            url = f"https://www.youtube.com/watch?v={video['id']}"
            opts = {
                "format": "best[ext=mp4]/best",
                "outtmpl": str(self.download_dir / "%(title)s.%(ext)s"),
                "quiet": True,
                "noplaylist": True,
                "merge_output_format": "mp4",
                "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            if video not in self.downloads:
                self.downloads.insert(0, video)
                self.downloads = self.downloads[:100]
                self.save_json(self.downloads_file, self.downloads)
            Clock.schedule_once(lambda *_: setattr(self.player_title, "text", "✅ İndirme tamamlandı"), 0)
        except Exception as e:
            Clock.schedule_once(lambda *_: setattr(self.player_title, "text", "❌ İndirme hatası: " + str(e)), 0)


if __name__ == "__main__":
    AndroidTube().run()
