"""User-interface text (English)."""
STRINGS = {
    'app_title': 'Sahm Download Manager',
    'add_url': 'Add URL',
    'resume': 'Resume',
    'pause': 'Pause',
    'pause_all': 'Pause all',
    'delete': 'Delete',
    'delete_with_file': 'Delete with file',
    'start_queue': 'Start queue',
    'stop_queue': 'Stop queue',
    'settings': 'Settings',
    'open': 'Open',
    'open_folder': 'Open folder',
    'copy_url': 'Copy URL',
    'redownload': 'Download again',
    'move_to_queue': 'Add to queue',
    'col_name': 'File name',
    'col_size': 'Size',
    'col_progress': 'Progress',
    'col_speed': 'Speed',
    'col_eta': 'Time left',
    'col_status': 'Status',
    'col_conn': 'Conn.',
    'st_queued': 'Queued',
    'st_connecting': 'Connecting…',
    'st_downloading': 'Downloading',
    'st_paused': 'Paused',
    'st_completed': 'Completed',
    'st_error': 'Error',
    'flt_all': 'All',
    'flt_active': 'Active',
    'flt_completed': 'Completed',
    'flt_unfinished': 'Unfinished',
    'url': 'URL',
    'save_to': 'Save to',
    'browse': 'Browse…',
    'filename': 'File name (optional)',
    'connections': 'Connections per file',
    'start_now': 'Start now',
    'later': 'Add to queue',
    'cancel': 'Cancel',
    'ok': 'Save',
    'max_concurrent': 'Max simultaneous downloads',
    'speed_limit': 'Speed limit (KB/s, 0 = unlimited)',
    'browser_dialog': 'Ask before starting browser downloads',
    'notify': 'Notify when a download completes',
    'close_tray': 'Closing the window keeps Sahm in the tray',
    'scheduler': 'Scheduler',
    'sched_enable': 'Start the queue automatically at',
    'sched_stop': 'Stop the queue at',
    'general': 'General',
    'tab_conn': 'Connection',
    'total_speed': 'Total speed',
    'active': 'Active',
    'queue_on': 'Queue running',
    'server_busy': 'Browser integration unavailable: port 9614 is in use',
    'server_ok': 'Browser integration ready',
    'done_title': 'Download complete',
    'show': 'Show Sahm',
    'quit': 'Quit',
    'confirm_delete': 'Delete the selected downloads?',
    'invalid_url': 'Please enter a valid http(s) link.',
    'no_resume': 'This server does not support resuming',
    'unknown': 'Unknown',
    'add_video': 'Add video',
    'st_waiting_net': 'No connection – retrying…',
    'theme': 'Appearance',
    'theme_system': 'Same as system',
    'theme_light': 'Light',
    'theme_dark': 'Dark',
    'ext_ok': 'Browser extension',
    'ext_add': 'Add Sahm to your browser',
    'ext_open_store': 'Get it for {browser}',
    'ext_manual': 'Open edge://extensions or chrome://extensions, turn on Developer mode, click “Load unpacked” and choose this folder:\n\n{folder}',
    'start_login': 'Start Sahm when I log in',
    'dup_title': 'Already downloaded',
    'dup_text': 'You already downloaded “{name}” on {when}.\n\nDownload it again?',
    'download_again': 'Download again',
    'already_listed': 'Already in your list',
    'added_on': 'Added',
    'src_browser': 'from the browser',
    'src_manual': 'by you',
    'video_url': 'Video page link (YouTube, Facebook, …)',
    'video_title': 'Download video',
    'video_searching': 'Looking for video qualities…',
    'video_pick': 'Choose a quality:',
    'video_none': 'No downloadable video was found on this page.',
    'video_signin': 'Open the video in your browser while signed in, then use the Sahm button on the video.',
    'direct_file': 'Direct file',
    'video_on_page': 'video on this page',
    'video_unsupported': "Sahm can't read this website's page directly, and no video file was detected yet.\n\nPlay the video in your browser for a few seconds, then click “Download this video” again - Sahm will pick up the video file while it plays.",
    'st_merging': 'Merging video + audio…',
    'video_preparing': 'Preparing video support (first time only)…',
    'video_tools_failed': 'Could not prepare video support. Check your internet connection and try again.',
}


def tr(key):
    return STRINGS.get(key, key)


def human_size(n):
    if n is None:
        return tr("unknown")
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.0f} {u}" if u == "B" else f"{f:.2f} {u}"
        f /= 1024


def human_speed(bps):
    return "" if bps < 1 else human_size(bps) + "/s"


def human_eta(sec):
    if sec is None:
        return ""
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
