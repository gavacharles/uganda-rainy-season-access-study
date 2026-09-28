"""Record a tour of the interactive map (../figures/animations/).

  a4_interactive_map.gif   for Substack and slides
  a4_interactive_map.mp4   for LinkedIn and other sites that do not animate GIFs

Each scene is a screenshot of web/index.html in headless Chrome, set up through a
temporary copy of the page that reads the scene from the URL hash (layer, month,
zoom, overlays, a selected place and a caption). The published page is not changed.
Edit SCENES to change the tour.
"""
import os, subprocess, tempfile, urllib.parse
import numpy as np
import imageio.v2 as imageio
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")
FIG = os.path.join(HERE, "..", "figures", "animations")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SIZE = (1280, 760)

# (seconds on screen, scene). Keys: view, month, at="lat,lon,zoom", on="catch,hc4",
# off="cross,hosp", sub="Sub-county|District", cross=rank, cap=caption.
SCENES = [
    (1.0, dict(view="month_raster", month=1, cap="Travel time to the nearest hospital, January")),
    (1.0, dict(view="month_raster", month=4, cap="April: the long rains push 2.3 million more people beyond 1 hour")),
    (1.0, dict(view="month_raster", month=8, cap="August: the northern rains")),
    (1.0, dict(view="month_raster", month=10, cap="October: the short rains")),
    (2.2, dict(view="month_sub", month=4, cap="The same, by sub-county")),
    (2.2, dict(view="hosp_extra", cap="Minutes the April rains add to the trip")),
    (2.2, dict(view="emoc_walk", cap="On foot: 44% of women 15–49 are more than 2 hours from an HC IV or hospital in April")),
    (2.2, dict(view="any_walk", cap="On foot to any health facility, April")),
    (2.0, dict(view="sec_apr", cap="Beyond health: secondary schools")),
    (2.0, dict(view="mkt_apr", cap="…and markets")),
    (2.2, dict(view="rwi", cap="Relative wealth: the poorest areas lose most")),
    (2.2, dict(view="s_season", cap="Which season is worst, by sub-county")),
    (2.2, dict(view="s_increase", cap="Where the rains add most people beyond 1 hour")),
    (3.2, dict(view="s_increase", sub="Malongo|Mayuge",
               cap="Zoom: Malongo, Mayuge — 59% beyond 1 hour on a dry day, 93% in April")),
    (2.6, dict(view="hosp_dry", on="catch", off="cross",
               cap="Hospital catchments cut off most in April")),
    (3.2, dict(view="hosp_wet", at="1.35,34.45,9.5", cross=1,
               cap="Priority crossing 1: Riwo, Bukwo — a bridge brings ~7,000 people within 1 hour")),
]

HOOK = """<style>
.rec-cap { position: absolute; left: 50%; bottom: 20px; transform: translateX(-50%); z-index: 600;
  background: var(--ink); color: var(--panel); font: 600 15px/1.35 var(--sans); padding: 9px 16px;
  border-radius: 6px; max-width: 70%; text-align: center; box-shadow: var(--shadow); }
</style>
<script>
(function () {
  const q = new URLSearchParams(decodeURIComponent(location.hash.slice(1)));
  if (!q.has("view")) return;
  state.view = q.get("view");
  if (q.has("month")) state.month = +q.get("month");
  const set = (id, on) => { const el = document.getElementById(id); if (el.checked !== on) { el.checked = on; el.dispatchEvent(new Event("change")); } };
  const ids = { catch: "t-catch", hc4: "t-hc4", cross: "t-cross", hosp: "t-hosp", dist: "t-dist" };
  (q.get("on") || "").split(",").filter(Boolean).forEach(k => set(ids[k], true));
  (q.get("off") || "").split(",").filter(Boolean).forEach(k => set(ids[k], false));
  render();
  if (q.has("at")) { const [la, lo, z] = q.get("at").split(",").map(Number); map.setView([la, lo], z, { animate: false }); }
  if (q.has("sub")) {
    const [n, d] = q.get("sub").split("|");
    subs.eachLayer(l => { if (l.feature.properties.n === n && l.feature.properties.d === d) {
      selectSub(l.feature.properties, l); map.fitBounds(l.getBounds().pad(1.2), { animate: false, maxZoom: 10 }); } });
    document.getElementById("details").scrollIntoView({ block: "start" });
  }
  if (q.has("cross")) {
    const c = DATA.crossings.find(x => x.rank === +q.get("cross"));
    crossings.eachLayer(l => { const p = l.getLatLng(); if (p.lat === c.lat && p.lng === c.lon) l.fire("click"); });
    document.getElementById("details").scrollIntoView({ block: "start" });
  }
  if (q.has("cap")) {
    const cap = document.createElement("div"); cap.className = "rec-cap"; cap.textContent = q.get("cap");
    document.querySelector(".mapwrap").appendChild(cap);
    document.querySelector(".mapkey").style.bottom = "72px";
  }
})();
</script>
</body>"""

page = open(os.path.join(WEB, "index.html")).read()
tmp = tempfile.mkdtemp()
rec = os.path.join(tmp, "record.html")
open(rec, "w").write(page.replace("</body>", HOOK, 1))

frames, holds = [], []
for k, (hold, scene) in enumerate(SCENES):
    shot = os.path.join(tmp, f"s{k:02d}.png")
    frag = urllib.parse.quote(urllib.parse.urlencode({key: str(v) for key, v in scene.items()}))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", f"--window-size={SIZE[0]},{SIZE[1]}",
                    "--virtual-time-budget=5000", f"--screenshot={shot}", f"file://{rec}#{frag}"],
                   check=True, capture_output=True)
    frames.append(np.asarray(Image.open(shot).convert("RGB")))
    holds.append(hold)
    print("scene", k + 1, scene.get("cap", ""), flush=True)

os.makedirs(FIG, exist_ok=True)
gif = os.path.join(FIG, "a4_interactive_map.gif")
small = [np.asarray(Image.fromarray(f).resize((960, int(960 * SIZE[1] / SIZE[0])), Image.LANCZOS))
         for f in frames]
imageio.mimsave(gif, small, duration=[h * 1000 for h in holds], loop=0)
mp4 = os.path.join(FIG, "a4_interactive_map.mp4")
fps = 10
with imageio.get_writer(mp4, fps=fps, codec="libx264", quality=8, pixelformat="yuv420p",
                        macro_block_size=8) as w:
    for f, h in zip(frames, holds):
        for _ in range(int(round(h * fps))):
            w.append_data(f)
print(f"wrote {gif} ({os.path.getsize(gif) / 1e6:.1f} MB) and {mp4} ({os.path.getsize(mp4) / 1e6:.1f} MB), "
      f"{sum(holds):.0f} s")
