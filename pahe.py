#!/usr/bin/env python3

# python3 pahe.py "Grand Blue 1-12"


import os
import sys
import re
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import List, Dict
from pyrogram import Client, filters
from pyrogram.types import Message
import cloudscraper
import json
import subprocess
import time
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

Bot = "01581329242"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

JSON_FILE = "episodes_data.json"

class AnimepaheDownloader:
    """Main downloader class for animepahe.si"""

    def __init__(self, debug=False):
        self.debug = debug
        self.session = cloudscraper.create_scraper()
        self.session.headers.update({
            'authority': 'animepahe.si',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'en-US,en;q=0.9',
            'cookie': '__ddg2_=;',
            'dnt': '1',
            'sec-ch-ua': '"Not A(Brand)";v="99", "Microsoft Edge";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-requested-with': 'XMLHttpRequest',
            'referer': 'https://animepahe.si',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        })
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled")

    # --- Kwik bypass helpers ---
    def step_2(self, s, seperator, base=10):
        mapped_range = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
        numbers = mapped_range[0:base]
        max_iter = 0
        for index, value in enumerate(s[::-1]):
            max_iter += int(value if value.isdigit() else 0) * (seperator**index)
        mid = ''
        while max_iter > 0:
            mid = numbers[int(max_iter % base)] + mid
            max_iter = (max_iter - (max_iter % base)) / base
        return mid or '0'

    def step_1(self, data, key, load, seperator):
        payload = ""
        i = 0
        seperator = int(seperator)
        load = int(load)
        while i < len(data):
            s = ""
            while data[i] != key[seperator]:
                s += data[i]
                i += 1
            for index, value in enumerate(key):
                s = s.replace(value, str(index))
            payload += chr(int(self.step_2(s, seperator, 10)) - load)
            i += 1
        payload = re.findall(
            r'action="([^\"]+)" method="POST"><input type="hidden" name="_token"\s+value="([^\"]+)', payload
        )[0]
        return payload

    def bypass_kwik(self, link: str):
        try:
            logger.debug(f"Bypassing kwik link: {link}")
            kwik_session = cloudscraper.create_scraper()
            kwik_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            resp = kwik_session.get(link, headers=kwik_headers)
            matches = re.findall(r'\("(\S+)",\d+,"(\S+)",(\d+),(\d+)', resp.text)
            if not matches:
                return None
            data, key, load, seperator = matches[0]
            url, token = self.step_1(data=data, key=key, load=load, seperator=seperator)
            post_data = {"_token": token}
            post_headers = kwik_headers.copy()
            post_headers.update({
                'referer': link,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://kwik.si'
            })
            resp = kwik_session.post(url=url, data=post_data, headers=post_headers, allow_redirects=False)
            for header_name, header_value in resp.headers.items():
                if header_name.lower() == 'location':
                    return header_value
            return None
        except Exception as e:
            logger.debug(f"Error bypassing Kwik link: {e}")
            return None

    def extract_kwik_link(self, pahe_url: str):
        try:
            response = self.session.get(pahe_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup.find_all(['script', 'iframe']):
                if element.name == 'script' and element.get('type') == 'text/javascript':
                    match = re.search(r'https://kwik\.si/f/[\w\d]+', element.text)
                else:
                    match = re.search(r'https://kwik\.si/f/[\w\d]+', str(element))
                if match:
                    return match.group(0)
            return None
        except Exception as e:
            logger.debug(f"Error extracting Kwik link: {e}")
            return None

    # --- Animepahe API methods ---
    def search_anime(self, query: str):
        search_url = f"https://animepahe.si/api?m=search&q={query.replace(' ', '+')}"
        try:
            response = self.session.get(search_url)
            response.raise_for_status()
            data = response.json()
            results = []
            for anime in data.get('data', []):
                results.append({
                    'title': anime.get('title', ''),
                    'type': anime.get('type', ''),
                    'episodes': anime.get('episodes', ''),
                    'status': anime.get('status', ''),
                    'season': anime.get('season', ''),
                    'year': anime.get('year', ''),
                    'score': anime.get('score', ''),
                    'poster': anime.get('poster', ''),
                    'session': anime.get('session', ''),
                })
            return results
        except Exception as e:
            logger.error(f"Error searching anime: {e}")
            return []

    def get_episodes(self, session_id: str, page: int = 1):
        episodes_url = f"https://animepahe.si/api?m=release&id={session_id}&sort=episode_asc&page={page}"
        try:
            response = self.session.get(episodes_url)
            response.raise_for_status()
            data = response.json()
            return {
                'episodes': data.get('data', []),
                'current_page': data.get('current_page', 1),
                'last_page': data.get('last_page', 1),
                'total': data.get('total', 0)
            }
        except Exception as e:
            logger.error(f"Error getting episodes: {e}")
            return {'episodes': [], 'current_page': 1, 'last_page': 1, 'total': 0}

    def get_download_links(self, session_id: str, episode_session: str):
        episode_url = f"https://animepahe.si/play/{session_id}/{episode_session}"
        try:
            response = self.session.get(episode_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            download_links = soup.select("#pickDownload a.dropdown-item")
            links = []
            for link in download_links:
                links.append({
                    'text': link.get_text(strip=True),
                    'url': link.get('href', ''),
                })
            return links
        except Exception as e:
            logger.error(f"Error getting download links: {e}")
            return []

    def get_direct_download_url(self, pahe_download_url: str):
        kwik_link = self.extract_kwik_link(pahe_download_url)
        if not kwik_link:
            return None
        return self.bypass_kwik(kwik_link)

    def download_file(self, url: str, output_path: str, progress_callback=None):
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://kwik.cx/',
                'Accept': 'video/*,*/*;q=0.9'
            }
            with self.session.get(url, headers=headers, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress = (downloaded / total_size) * 100
                                progress_callback(progress, downloaded, total_size)
            return True
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return False

# ---------------- CLI ----------------
class AnimeCLI:
    def __init__(self):
        self.downloader = AnimepaheDownloader(debug=False)
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {}

    # Episode parsing
    def parse_episode_range(self, episode_str: str) -> List[int]:
        episodes = []
        parts = episode_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-', 1)
                    episodes.extend(range(int(start), int(end)+1))
                except ValueError:
                    continue
            else:
                try:
                    episodes.append(int(part))
                except ValueError:
                    continue
        return sorted(list(set(episodes)))

    def search_and_select_anime(self, anime_name: str) -> Dict:
        results = self.downloader.search_anime(anime_name)
        if not results:
            print(f"❌ No anime found for: {anime_name}")
            return None
        print(f"\n✅ Found {len(results)} result(s):")
        for i, anime in enumerate(results):
            print(f"{i + 1}. {anime['title']} | Episodes: {anime['episodes']} | Year: {anime['year']} | Score: {anime['score']}")
        while True:
            try:
                choice = input(f"Select anime (1-{len(results)}): ").strip()
                index = int(choice)-1
                if 0 <= index < len(results):
                    return results[index]
                print(f"❌ Enter number 1-{len(results)}")
            except Exception:
                print("❌ Invalid input")

    def get_all_episodes(self, session_id: str) -> List[Dict]:
        all_eps, page = [], 1
        while True:
            data = self.downloader.get_episodes(session_id, page)
            eps = data['episodes']
            if not eps: break
            all_eps.extend(eps)
            if page >= data['last_page']: break
            page += 1
        return all_eps

    def get_episode_direct_links(self, session_id: str, episode_session: str, episode_num: int) -> List[Dict]:
        download_links = self.downloader.get_download_links(session_id, episode_session)
        direct_links = []
        for link in download_links:
            direct_url = self.downloader.get_direct_download_url(link['url'])
            if direct_url:
                direct_links.append({'quality': link['text'], 'direct_url': direct_url})
        return direct_links

    def save_to_json(self, anime_data: Dict, episode_num: int, direct_links: List[Dict]):
        anime_key = anime_data['session']
        if anime_key not in self.data:
            self.data[anime_key] = {
                'anime_title': anime_data['title'],
                'poster_url': anime_data['poster'],
                'year': anime_data['year'],
                'type': anime_data['type'],
                'status': anime_data['status'],
                'total_episodes': anime_data['episodes'],
                'episodes': {}
            }
        self.data[anime_key]['episodes'][str(episode_num)] = direct_links
        
        anime_dir = Path(anime_data["title"]) 
        if not anime_dir.exists():
          anime_dir.mkdir(parents=True)
        
        json_path = anime_dir / "episodes_data.json"
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.data[anime_key], f, ensure_ascii=False, indent=4)
        print(f"💾 Saved episode {episode_num} to {json_path}")

    def process_request(self, anime_name: str, episode_range: str):
        episodes = self.parse_episode_range(episode_range)
        if not episodes:
            print("❌ Invalid episode format")
            return
        selected_anime = self.search_and_select_anime(anime_name)
        if not selected_anime: return
        session_id = selected_anime['session']
        all_episodes = self.get_all_episodes(session_id)
        episodes_to_process = [ep for ep in all_episodes if ep['episode'] in episodes]
        for ep in episodes_to_process:
            episode_num = ep['episode']
            episode_session = ep['session']
            direct_links = self.get_episode_direct_links(session_id, episode_session, episode_num)
            if direct_links:
                self.save_to_json(selected_anime, episode_num, direct_links)

# ---------------- Main ----------------
def main():
    if len(sys.argv) < 2:
        print("❌ Usage: python cli_script.py '<anime_name> <episode_range>'")
        sys.exit(1)
    input_str = ' '.join(sys.argv[1:])
    words = input_str.split()
    episode_str = words[-1]
    anime_name = ' '.join(words[:-1])
    cli = AnimeCLI()
    cli.process_request(anime_name, episode_str)

if __name__ == "__main__":
    main()