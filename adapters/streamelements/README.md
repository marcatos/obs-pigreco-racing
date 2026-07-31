# StreamElements / browser chat — PiGreco themes

Optional engagement pack (**P2-01**, **P2-02**). Core OBS pack works without a StreamElements account.

**Target:** StreamElements Custom CSS / AlertBox HTML (also usable as generic browser-chat CSS if markup matches SE class names).

Brand tokens: `#00C400` · `#009FE5` · `#080A0C` · `#11161A` · Orbitron / Rajdhani (Google Fonts).

## Files

| Path | Use |
|------|-----|
| [`chat.css`](chat.css) | Paste into SE **Chatbox → Custom CSS** |
| [`alerts.css`](alerts.css) | Shared alert look; paste into SE **AlertBox → Custom CSS** |
| [`alerts/follow.html`](alerts/follow.html) | Follow template stub (static preview) |
| [`alerts/sub.html`](alerts/sub.html) | Sub template stub |
| [`alerts/raid.html`](alerts/raid.html) | Raid template stub |
| [`preview.html`](preview.html) | Local demo for OBS Browser Source (`file://`) |

## Install — StreamElements chat (P2-01)

1. Open [StreamElements](https://streamelements.com/) → **Streaming Tools** → **Overlays** (or My Overlays).
2. Add / edit a **Chatbox** widget.
3. Open **Settings** → **CSS** (Custom CSS).
4. Replace contents with [`chat.css`](chat.css) (keep the `@import` for fonts).
5. Copy the overlay URL into OBS as a **Browser Source** (width ~400–450, height as needed). Position bottom-left / corner so it does not cover center FOV.

## Install — StreamElements alerts (P2-02)

1. In the same (or another) overlay, add an **AlertBox** widget.
2. For Follow / Subscriber / Raid: open each alert type → **Custom HTML / CSS**.
3. Paste matching markup from `alerts/*.html` (body inner `.pgr-alert` block) into Custom HTML.
4. Paste [`alerts.css`](alerts.css) into Custom CSS (or the rules you need).
5. Swap sample names for SE tokens, e.g. `{name}`, `{amount}`, `{tier}`.
6. Size the Browser Source large enough for the alert (~700×300+) and place it off-center (typical: mid-upper, clear of gameplay).

## Optional — OBS local preview (no SE)

1. OBS → **Sources** → **Browser** → **Local file** (or URL).
2. Point to this folder’s `preview.html`, e.g.  
   `file:///C:/Users/YOU/Documents/Projects/obs-pigreco-racing/adapters/streamelements/preview.html`
3. Width **1920**, height **1080**. Enable **Shutdown source when not visible** if you only use it for checks.
4. Click Follow / Sub / Raid tabs (or wait for auto-rotate) to review alert variants; sample chat sits bottom-left.

## Notes

- Do not commit StreamElements JWT / overlay secret URLs into the repo.
- Fonts load from Google Fonts; OBS needs network for first paint (same as other branded overlays).
- Generic “own” browser chat: reuse `chat.css` if your HTML uses `.message`, `.meta`, `.name`, `.colon`, `.content`.
