from widgets.core import Plugin
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton
from utils import get_settings, write_settings
from database import Database
from threading import Thread
from kivy.clock import Clock
db = Database("games.db")

class Settings(Plugin):
    name = "Settings"
    icon = "cog"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings_yaml = get_settings()
        
        self.layout = MDBoxLayout(orientation="vertical", padding="12dp", pos_hint={"y": 0.05}, spacing="12dp")
        self.add_widget(self.layout)
        
        
        # settings label
        self.settings_label = MDLabel(text="Settings", halign="left", font_style="H4", size_hint=(1, 0.1))
        self.layout.add_widget(self.settings_label)
        
        # general settings
        self.save_path = MDTextField(text=self.settings_yaml["general"]["save_path"], hint_text="Save path", pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(0.8, 0.1))
        self.layout.add_widget(self.save_path)
        
        # buttons
        self.save_btn = MDRaisedButton(text="Save",on_press=self.save_settings, pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(0.8, 0.00001))
        self.layout.add_widget(self.save_btn)
        
        # update database button -- fast, incremental: only adds repacks
        # that aren't already in the local database. Safe to click
        # regularly to pick up newly-added releases from jc141x's feed.
        self.update_db_label = MDLabel(
            text="Check jc141x's feed for new repacks (fast, adds only what's new):",
            halign="left",
            theme_text_color="Secondary",
            size_hint=(1, 0.00001),
        )
        self.layout.add_widget(self.update_db_label)

        self.update_db_btn = MDRaisedButton(text="Check for New Repacks",pos_hint={"center_x": 0.5, "center_y": 0.5}, md_bg_color="#ff0000", size_hint=(0.8, 0.00001), text_color=(0, 0, 0, 1))
        self.update_db_btn.bind(on_press=self.update_db)
        self.layout.add_widget(self.update_db_btn)

        # full rescan button -- scrapes johncena141's entire 1337x upload
        # history directly, WIPES the database and rebuilds it from
        # scratch. Much slower (can take a while), used for a complete
        # historical rebuild or if the fast feed above is capped/down.
        self.full_scan_label = MDLabel(
            text="Full rebuild from 1337x directly (slow, wipes and replaces everything):",
            halign="left",
            theme_text_color="Secondary",
            size_hint=(1, 0.00001),
        )
        self.layout.add_widget(self.full_scan_label)

        self.full_scan_btn = MDRaisedButton(text="Full Rescan (1337x, slow)", pos_hint={"center_x": 0.5, "center_y": 0.5}, md_bg_color="#ff0000", size_hint=(0.8, 0.00001), text_color=(0, 0, 0, 1))
        self.full_scan_btn.bind(on_press=self.full_scan)
        self.layout.add_widget(self.full_scan_btn)

        # boxlayout as spacer
        self.layout.add_widget(MDBoxLayout(size_hint=(None, None), size=(1, 150)))
        
        
        
    def save_settings(self, instance):
        self.settings_yaml["general"]["save_path"] = self.save_path.text
        
        write_settings(self.settings_yaml)
            
        self.settings_yaml = get_settings()
        
        
    def _set_text(self, instance, text):
        Clock.schedule_once(lambda dt: setattr(instance, "text", text))

    def _set_disabled(self, instance, disabled):
        Clock.schedule_once(lambda dt: setattr(instance, "disabled", disabled))

    def update_db(self, instance):
        instance.disabled = True

        t = Thread(target=self.update_db_helper, args=(instance,))
        t.start()
        
    def update_db_helper(self, instance):
        from utils import ReleasesFeed
        
        self._set_text(instance, "Checking for new repacks, please DO NOT close the application.")

        try:
            updater = ReleasesFeed(db_object=db)
            new_count = updater.pipeline()
            if new_count:
                self._set_text(instance, f"Added {new_count} new repack(s)")
            else:
                self._set_text(instance, "No new repacks found -- already up to date")
        except Exception as e:
            print(f"Database update failed: {e}")
            self._set_text(instance, f"Update failed: {e}")
        finally:
            self._set_disabled(instance, False)

    def full_scan(self, instance):
        instance.disabled = True

        t = Thread(target=self.full_scan_helper, args=(instance,))
        t.start()

    def full_scan_helper(self, instance):
        import tempfile
        import os
        from utils import JohnCena141Scraper

        self._set_text(instance, "Full rescan running -- this can take a long time, please DO NOT close the application.")

        csv_path = os.path.join(tempfile.gettempdir(), "kane141_full_scan")

        try:
            scraper = JohnCena141Scraper(
                csv_name=csv_path,
                db_object=db,
            )
            scraper.run()
            self._set_text(instance, "Full rescan done")
        except Exception as e:
            print(f"Full rescan failed: {e}")
            self._set_text(instance, f"Full rescan failed: {e}")
        finally:
            self._set_disabled(instance, False)
