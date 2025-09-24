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
