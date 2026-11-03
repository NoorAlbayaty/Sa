"""Make Chrome / Edge offer the Sahm extension automatically (like IDM and Adobe do).

Browsers check a registry key (Windows) or a small JSON file (macOS) at startup. When they find a
store extension ID there, they show "New extension added - Sahm Download Integration" with an
Enable button. This only works for extensions published in the browser's store.

>>> Fill in the IDs after publishing (the 32-letter ID from the store page / Partner Center). <<<
"""
import os
import sys
import json

EDGE_EXTENSION_ID = ""      # from Edge Add-ons, e.g. "abcdefghijklmnopabcdefghijklmnop"
CHROME_EXTENSION_ID = ""    # from the Chrome Web Store (optional)

EDGE_UPDATE_URL = "https://edge.microsoft.com/extensionwebstorebase/v1/crx"
CHROME_UPDATE_URL = "https://clients2.google.com/service/update2/crx"

# browser -> (extension id, update url, Windows registry key, macOS "External Extensions" folder)
BROWSERS = {
    "Edge": (EDGE_EXTENSION_ID, EDGE_UPDATE_URL, r"Software\Microsoft\Edge\Extensions",
             "~/Library/Application Support/Microsoft Edge/External Extensions"),
    "Chrome": (CHROME_EXTENSION_ID, CHROME_UPDATE_URL, r"Software\Google\Chrome\Extensions",
               "~/Library/Application Support/Google/Chrome/External Extensions"),
}


def _valid(ext_id):
    return len(ext_id) == 32 and ext_id.isalpha() and ext_id.islower()


def configured():
    """Browsers whose store ID has been filled in."""
    return [b for b, (ext_id, *_rest) in BROWSERS.items() if _valid(ext_id)]


def store_url(browser):
    ext_id = BROWSERS[browser][0]
    if browser == "Edge":
        return f"https://microsoftedge.microsoft.com/addons/detail/{ext_id}"
    return f"https://chromewebstore.google.com/detail/{ext_id}"


def register_external():
    """Tell the browsers about the extension (for the current user). Safe to call every start;
    returns the list of browsers newly registered."""
    done = []
    for browser in configured():
        ext_id, update_url, win_key, mac_dir = BROWSERS[browser]
        try:
            if sys.platform == "win32":
                import winreg
                key = win_key + "\\" + ext_id
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                        winreg.QueryValueEx(k, "update_url")
                        continue                                   # already registered
                except OSError:
                    pass
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
                    winreg.SetValueEx(k, "update_url", 0, winreg.REG_SZ, update_url)
                done.append(browser)
            elif sys.platform == "darwin":
                folder = os.path.expanduser(mac_dir)
                path = os.path.join(folder, ext_id + ".json")
                if os.path.exists(path):
                    continue
                if not os.path.isdir(os.path.dirname(folder)):     # browser not installed
                    continue
                os.makedirs(folder, exist_ok=True)
                with open(path, "w") as f:
                    json.dump({"external_update_url": update_url}, f)
                done.append(browser)
        except OSError:
            continue
    return done


def unregister_external():
    """Remove what register_external() added (used when uninstalling the portable/Mac version)."""
    for browser in configured():
        ext_id, _url, win_key, mac_dir = BROWSERS[browser]
        try:
            if sys.platform == "win32":
                import winreg
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, win_key + "\\" + ext_id)
            elif sys.platform == "darwin":
                os.remove(os.path.join(os.path.expanduser(mac_dir), ext_id + ".json"))
        except OSError:
            pass
