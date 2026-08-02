import threading

from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivy.uix.image import AsyncImage
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton
from kivymd.color_definitions import colors
from kivymd.toast.kivytoast.kivytoast import toast
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock
from kivy.utils import get_color_from_hex

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
        
        self.name = MDLabel(text=game_obj.name if len(game_obj.name) < 22 else game_obj.name[:20] + "..", halign="left", size_hint=(1, 0.1), padding=(5, 0))
        self.cover = AsyncImage(source=game_obj.cover, size_hint=(0.9, 0.9), pos_hint={"center_x":0.5, "center_y":0.5})
        self.magnet = game_obj.magnet 
        
        self.add_widget(self.cover)
        self.add_widget(self.name)
                
    def on_press(self):
        
        self.base_text = f"Description: \n{self.game_obj.description}\n\n" \
                f"Size: {self.game_obj.size}\n\n" \
                f"Platform: {self.game_obj.platform.title()}\n\n" \
                f"Minimum Requirements: Fetching from Steam..."
        
        self.dia = MDDialog(title=self.game_obj.name, 
                       text=self.base_text,
                       buttons=[
                           MDRaisedButton(text="Copy Magnet Link", on_press=self.copy_magnet),
                        ],
                       )
        
        self.dia.open()

        # fetch requirements in the background so the UI doesn't freeze
        threading.Thread(target=self.fetch_requirements, daemon=True).start()
        
        
    def copy_magnet(self, instance):
        Clipboard.copy(self.magnet)
        toast(f"Copied magnet link for {self.game_obj.name}", duration=3.0)

    def fetch_requirements(self):
        reqs = get_system_requirements(self.game_obj.name)
        # UI updates must happen on the main thread
        Clock.schedule_once(lambda dt: self.update_requirements(reqs))

    def update_requirements(self, reqs):
        # dialog may have been closed/discarded already, nothing to update
        if not hasattr(self, "dia"):
            return

        header = f"Description: \n{self.game_obj.description}\n\n" \
                f"Size: {self.game_obj.size}\n\n" \
                f"Platform: {self.game_obj.platform.title()}\n\n"

        if reqs:
            self.dia.text = f"{header}Minimum Requirements:\n{reqs}"
        else:
            self.dia.text = f"{header}System Requirements: Not found on Steam"
