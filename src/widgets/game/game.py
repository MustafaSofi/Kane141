import threading

from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivy.uix.image import AsyncImage
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton
from kivymd.color_definitions import colors
from kivymd.toast.kivytoast.kivytoast import toast
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from kivy.metrics import dp

from widgets.border import BorderBehavior
from utils import get_system_requirements


class GameCard(MDCard, BorderBehavior):
    def __init__(self, game_obj, **kwargs):
        super().__init__(**kwargs)
        
        self.borders = (1, 'solid', get_color_from_hex(colors["BlueGray"]["600"]))
        
        self.game_obj = game_obj
        
        self.orientation = "vertical"
        self.size_hint = (None, None)
        self.size = (200, 300)
        
        self.md_bg_color = "#00000000"
        
        # name (left) + size (right) on the same row
        self.info_row = MDBoxLayout(orientation="horizontal", size_hint=(1, 0.1), padding=(5, 0))
        
        self.name = MDLabel(
            text=game_obj.name if len(game_obj.name) < 18 else game_obj.name[:16] + "..",
            halign="left",
            size_hint_x=0.65,
        )
        self.size_tag = MDLabel(
            text=game_obj.size,
            halign="right",
            size_hint_x=0.35,
            theme_text_color="Secondary",
            font_style="Caption",
        )
        self.info_row.add_widget(self.name)
        self.info_row.add_widget(self.size_tag)
        
        self.cover = AsyncImage(source=game_obj.cover, size_hint=(0.9, 0.9), pos_hint={"center_x":0.5, "center_y":0.5})
        self.magnet = game_obj.magnet 
        
        self.add_widget(self.cover)
        self.add_widget(self.info_row)
                
    def on_press(self):

        header = self._build_header()

        # persistent label whose text we update in place -- the dialog frame
        # and its buttons are never rebuilt, so the button stays clickable
        self.info_label = MDLabel(
            text=header + "Minimum Requirements: Fetching from Steam...",
            halign="left",
            valign="top",
            size_hint_y=None,
        )
        self.info_label.bind(
            width=lambda inst, val: setattr(inst, "text_size", (val, None)),
            texture_size=lambda inst, val: setattr(inst, "height", val[1]),
        )

        scroll = MDScrollView(size_hint_y=None, height=dp(320))
        scroll.add_widget(self.info_label)

        content = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(320))
        content.add_widget(scroll)

        self.dia = MDDialog(
            title=self.game_obj.name,
            type="custom",
            content_cls=content,
            buttons=[
                MDRaisedButton(text="Copy Magnet Link", on_press=self.copy_magnet),
            ],
        )

        self.dia.open()

        # fetch requirements in the background so the UI doesn't freeze
        threading.Thread(target=self.fetch_requirements, daemon=True).start()

    def _build_header(self):
        parts = [f"Description: \n{self.game_obj.description}\n"]

        release_name = getattr(self.game_obj, "release_name", None)
        if release_name:
            # this is what actually distinguishes two entries with the
            # same display name -- e.g. two "Cuphead" results at
            # different sizes are usually different versions/updates/DLC
            # bundles, which only shows up in the original release title
            parts.append(f"Release: {release_name}\n")

        date_uploaded = getattr(self.game_obj, "date_uploaded", None)
        if date_uploaded:
            parts.append(f"Uploaded: {date_uploaded}\n")

        parts.append(f"Size: {self.game_obj.size}\n")
        parts.append(f"Platform: {self.game_obj.platform.title()}\n")

        return "\n".join(parts) + "\n"
        
    def copy_magnet(self, instance):
        Clipboard.copy(self.magnet)
        toast(f"Copied magnet link for {self.game_obj.name}", duration=3.0)

    def fetch_requirements(self):
        appid = getattr(self.game_obj, "steam_appid", None)
        reqs = get_system_requirements(self.game_obj.name, appid=appid)
        # UI updates must happen on the main thread
        Clock.schedule_once(lambda dt: self.update_requirements(reqs))

    def update_requirements(self, reqs):
        # dialog may have been closed/discarded already, nothing to update
        if not hasattr(self, "info_label"):
            return

        header = self._build_header()

        if reqs:
            self.info_label.text = f"{header}Minimum Requirements:\n{reqs}"
        else:
            self.info_label.text = f"{header}Minimum Requirements: Not found on Steam"
