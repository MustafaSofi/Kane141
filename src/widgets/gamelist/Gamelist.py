from kivymd.uix.recycleview import MDRecycleView
from kivymd.uix.stacklayout import MDStackLayout
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.label import MDLabel
from widgets.searchbar import SearchBar

class CenteredStackLayout(MDStackLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.adaptive_height = True
    
    def on_size(self, instance, value):
        width, height = self.size
        card_width = getattr(next(iter(self.children), None), "width", None)
        if not card_width:
            return
        number_of_cards = width//card_width
        padding = (width - (card_width * number_of_cards)) / (number_of_cards + 1) 
        self.padding = padding
        self.spacing = padding

class Gamelist(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # main layout
        self.orientation="vertical"

        # searchbar
        self.searchbar = SearchBar()
        self.searchbar.bind(on_text_validate=self.update_list_on_search)
        self.add_widget(self.searchbar)

        # games grid
        self.scrollview = MDRecycleView()
        self.stack = CenteredStackLayout()
        self.scrollview.add_widget(self.stack)
        self.add_widget(self.scrollview) 

        # pagination bar
        self.pagination_bar = MDBoxLayout(
            orientation="horizontal",
            adaptive_height=True,
            padding="12dp",
            spacing="12dp",
            pos_hint={"center_x": 0.5},
        )
        self.prev_btn = MDIconButton(icon="chevron-left")
        self.page_label = MDLabel(text="Page 1 of 1", halign="center", adaptive_height=True)
        self.next_btn = MDIconButton(icon="chevron-right")
        self.pagination_bar.add_widget(self.prev_btn)
        self.pagination_bar.add_widget(self.page_label)
        self.pagination_bar.add_widget(self.next_btn)
        self.add_widget(self.pagination_bar)

    def clear_list(self):
        self.stack.clear_widgets()
        
    def add_game(self, game):
        self.stack.add_widget(game)

    def search_bind(self, call_on_text_change):
        self.call_on_text_change = call_on_text_change
    
    def update_list_on_search(self, instance):
        self.call_on_text_change(instance)
    
    def game_count(self):
        return len(self.stack.children)

    def pagination_bind(self, on_prev_page, on_next_page):
        """Wire up the Prev/Next buttons to callbacks provided by the screen."""
        self.prev_btn.bind(on_press=on_prev_page)
        self.next_btn.bind(on_press=on_next_page)

    def update_page_controls(self, current_page, total_pages):
        """Refresh the page label and enable/disable Prev/Next as needed.
        current_page is zero-indexed."""
        total_pages = max(total_pages, 1)
        self.page_label.text = f"Page {current_page + 1} of {total_pages}"
        self.prev_btn.disabled = current_page <= 0
        self.next_btn.disabled = current_page >= total_pages - 1
