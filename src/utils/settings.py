import getpass
import yaml
import os
from bs4 import BeautifulSoup
import requests
from github import Github

def get_settings_template():
    
    abs_path = os.path.dirname(__file__)
    abs_path = abs_path.split("/utils")[0]
    settings_path = os.path.join(abs_path, "settings.yaml")
    
    with open(settings_path) as f:
        settings = yaml.safe_load(f)
        settings["general"]["save_path"] = f"/home/{getpass.getuser()}/Downloads"
        return settings
    
def write_settings(settings):
    
    user_name = getpass.getuser()
    config_path = f"/home/{user_name}/.config/kane141"
    
    settings_path = os.path.join(config_path, "settings.yaml")
    
    with open(settings_path, "w") as f:
        yaml.dump(settings, f)
        
def check_config():
    user_name = getpass.getuser()
    config_path = f"/home/{user_name}/.config/kane141"
    
    # Check if config directory exists
    if not os.path.exists(config_path):
        os.makedirs(config_path)
        settings = get_settings_template()
        write_settings(settings)
    
    # Check if settings file exists
    settings_path = os.path.join(config_path, "settings.yaml")
    if not os.path.isfile(settings_path):
        settings = get_settings_template()
        write_settings(settings)
        
def get_settings():
    user_name = getpass.getuser()
    config_path = f"/home/{user_name}/.config/kane141"
    
    settings_path = os.path.join(config_path, "settings.yaml")
    
    with open(settings_path) as f:
        return yaml.safe_load(f)
    
def check_database():
    user_name = getpass.getuser()
    config_path = f"/home/{user_name}/.config/kane141"
    
    db_file_path = os.path.join(config_path, "games.db")
    
    # Check if database file exists
    if not os.path.isfile(db_file_path):
        abs_path = os.path.dirname(__file__)
        abs_path = abs_path.split("/utils")[0]
        db_template_path = os.path.join(abs_path, "database/games.db")
        
        # Copy template database file
        with open(db_template_path, "rb") as f:
            db_template = f.read()
            
        with open(db_file_path, "wb") as f:
            f.write(db_template)

def get_latest_release():
    try:
        g = Github()
        latest_release = g.get_repo("MustafaSofi/Kane141").get_latest_release()
        link = latest_release.url
        return latest_release.name, link
    except Exception as e:
        print(f"Could not check for latest release: {e}")
        return None, None
