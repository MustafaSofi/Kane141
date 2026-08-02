from kivymd.app import MDApp
from widgets.core import MainScreen
from utils import check_config, check_database
from __version__ import __version__
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

# Kivy auto-probes other input devices (like touchpads) via probesysfs/HIDInput
# on Linux and treats their movement as separate multitouch input, which causes
# unwanted scroll/zoom-like gestures. Disabling that auto-probing keeps input
# limited to normal mouse-style events.
Config.remove_option('input', '%(name)s')


class Kane141(MDApp):
    def build(self):
        
        check_config()
        check_database()
        
        self.theme_cls.material_style = "M3"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "BlueGray"

        return MainScreen(__version__)


Kane141().run()
