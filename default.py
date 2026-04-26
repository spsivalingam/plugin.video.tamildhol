import sys
import urllib.parse
import xbmcgui
import xbmcplugin
import xbmcaddon


handle = int(sys.argv[1])
params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
__addon_id__ = "plugin.video.tamildhol"


def build_url(action, query=None, url=None, page=None):
    args = {'action': action}
    if query is not None:
        args['query'] = query
    if url is not None:
        args['url'] = url
    if page is not None:
        args['page'] = str(page)
    qs = urllib.parse.urlencode(args)
    return "plugin://" + __addon_id__ + "/?" + qs


def add_video_item(title, video_url):
    item_url = build_url('play', url=video_url)
    listitem = xbmcgui.ListItem(label=title)
    xbmcplugin.addDirectoryItem(handle, item_url, listitem, False)


def add_folder_item(label, action, extra=None):
    if extra:
        folder_url = build_url(action, **extra)
    else:
        folder_url = build_url(action)
    listitem = xbmcgui.ListItem(label=label)
    listitem.setProperty('IsFolder', 'true')
    xbmcplugin.addDirectoryItem(handle, folder_url, listitem, True)


def show_notification(message, title="TamilDhol"):
    xbmcgui.Dialog().notification(title, message, xbmcgui.NOTIFICATION_ERROR)


def import_scraper():
    import os
    import sys
    lib_path = os.path.join(os.path.dirname(__file__), 'lib')
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)
    from scraper import TamilDholScraper
    return TamilDholScraper()


def show_home(page=1):
    scraper = import_scraper()

    add_folder_item("Search", "search_dialog")

    result = scraper.get_home_items(page)
    if not result['items']:
        show_notification("No content found. Check your connection.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    for item in result['items']:
        add_video_item(item['title'], item['url'])

    if result['has_next']:
        next_url = build_url('home', page=page + 1)
        listitem = xbmcgui.ListItem(label='[COLOR yellow]Next Page >>[/COLOR]')
        listitem.setProperty('IsFolder', 'true')
        xbmcplugin.addDirectoryItem(handle, next_url, listitem, True)

    xbmcplugin.endOfDirectory(handle)


def do_search_dialog():
    query = xbmcgui.Dialog().input("Search TamilDhol", "")
    if not query or len(query.strip()) == 0:
        return
    if len(query) > 200:
        show_notification("Query too long (max 200 chars)")
        return
    
    # Reload addon with search parameters instead of Container.Update
    sys.argv[2] = '?' + urllib.parse.urlencode({'action': 'search_results', 'query': query})
    params.clear()
    params.update({'action': 'search_results', 'query': query})
    show_search_results(query)

def show_search_results(query, page=1):
    scraper = import_scraper()

    add_folder_item("Back to Home", "home")

    result = scraper.search_items(query, page)
    if not result['items']:
        show_notification("No results found.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    for item in result['items']:
        add_video_item(item['title'], item['url'])

    if result['has_next']:
        next_url = build_url('search_results', query=query, page=page + 1)
        listitem = xbmcgui.ListItem(label='[COLOR yellow]Next Page >>[/COLOR]')
        listitem.setProperty('IsFolder', 'true')
        xbmcplugin.addDirectoryItem(handle, next_url, listitem, True)

    xbmcplugin.endOfDirectory(handle)


def play_video(video_url):
    if not video_url or not isinstance(video_url, str):
        show_notification("Invalid video URL")
        return
    if not (video_url.startswith('http://') or video_url.startswith('https://')):
        show_notification("Invalid URL scheme. Must start with http:// or https://")
        return

    scraper = import_scraper()
    result = scraper.get_stream_url(video_url)

    if result:
        stream_url = result['url']
        referer = result['referer']
        user_agent = result['user_agent']

        # Append HTTP headers to URL using Kodi's pipe syntax
        header_string = '|User-Agent=' + urllib.parse.quote(user_agent, safe='') + '&Referer=' + urllib.parse.quote(referer)
        play_url = stream_url + header_string

        print("[TamilDhol] Playing: " + play_url[:120])

        # Method 1: setResolvedUrl with ListItem
        listitem = xbmcgui.ListItem(path=stream_url)
        listitem.setPath(play_url)
        listitem.setMimeType('video/mp4')
        xbmcplugin.setResolvedUrl(handle, True, listitem)

        # Small delay to check if playback started
        import time
        time.sleep(0.5)
        player = xbmc.Player()
        if not player.isPlaying():
            print("[TamilDhol] setResolvedUrl failed, trying direct Player.play()")
            # Method 2: Direct Player().play() with URL string
            player.play(play_url, listitem)
    else:
        show_notification("Could not find a playable stream.")


def main():
    action = params.get('action')
    page = int(params.get('page', '1'))

    if action == 'search_dialog':
        do_search_dialog()
    elif action == 'search_results':
        query = params.get('query', '')
        show_search_results(query, page)
    elif action == 'play':
        video_url = params.get('url', '')
        play_video(video_url)
    elif action == 'home':
        show_home(page)
    else:
        show_home()


if __name__ == '__main__':
    main()
