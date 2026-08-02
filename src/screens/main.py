from widgets.core import Plugin
from widgets.game import GameCard
from widgets.gamelist import Gamelist
from database import Database

# database
db = Database("games.db")

PAGE_SIZE = 50

class Main(Plugin):
    name = "Main"
    icon = "controller"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = "main"

        self.search_text = ""
        self.current_page = 0

        self.gamelist = Gamelist()
        self.gamelist.search_bind(self.update_grid_on_search)
        self.gamelist.pagination_bind(self.prev_page, self.next_page)
        self.add_widget(self.gamelist)

        # load first page of games
        self.load_page()

    def total_pages(self):
        if self.search_text:
            count = db.count_game_search(self.search_text)
        else:
            count = db.count_games()
        return max(1, -(-count // PAGE_SIZE))  # ceil division

    # load the current page into the grid
    def load_page(self):
        self.gamelist.clear_list()
        offset = self.current_page * PAGE_SIZE
        if self.search_text:
            games = db.get_game_page(self.search_text, offset, PAGE_SIZE)
        else:
            games = db.get_games_page(offset, PAGE_SIZE)
        for i in games:
            self.gamelist.add_game(GameCard(i))
        self.gamelist.update_page_controls(self.current_page, self.total_pages())

    # callback for searchbar
    def update_grid_on_search(self, instance):
        text = instance.text
        instance.text = ""

        self.search_text = text
        self.current_page = 0
        self.load_page()

    def next_page(self, instance=None):
        if self.current_page < self.total_pages() - 1:
            self.current_page += 1
            self.load_page()

    def prev_page(self, instance=None):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_page()
