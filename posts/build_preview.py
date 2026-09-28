"""Render the Substack draft, the LinkedIn text and the two X posts into one preview page
(posts/preview.html) with the images embedded, for reading and copying."""
import os, re, base64, html
import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
MIME = {".png": "image/png", ".gif": "image/gif"}
LABELS = ["Post 1: the Substack story", "Post 2: the interactive map"]

body = markdown.markdown(open(os.path.join(HERE, "substack_post.md")).read(), extensions=["tables"])


def embed(m):
    path = os.path.join(HERE, m.group(1))
    data = base64.b64encode(open(path, "rb").read()).decode()
    return f'src="data:{MIME[os.path.splitext(path)[1]]};base64,{data}"'


body = re.sub(r'src="(images/[^"]+)"', embed, body)
body = re.sub(r'(https://gavacharles\.github\.io/uganda-rainy-season-access/)(?![^<]*</a>)',
              r'<a href="\1">\1</a>', body)
# Captions: an <em> paragraph right after an image paragraph becomes its caption
body = re.sub(r'<p>(<img [^>]+>)</p>\s*<p><em>(.*?)</em></p>',
              r'<figure>\1<figcaption>\2</figcaption></figure>', body, flags=re.S)
body = re.sub(r'<p>(<img [^>]+>)</p>', r'<figure>\1</figure>', body)

li = open(os.path.join(HERE, "linkedin_post.md")).read().split("\n---\n")[0].strip()
li_note = open(os.path.join(HERE, "linkedin_post.md")).read().split("\n---\n")[1].strip()
li_note = markdown.markdown(li_note)

page = open(os.path.join(HERE, "preview_template.html")).read()
page = (page.replace("<!--SUBSTACK-->", body)
        .replace("<!--LINKEDIN-->", html.escape(li))
        .replace("<!--LINKEDIN_NOTE-->", li_note)
        .replace("<!--LINKEDIN_CHARS-->", f"{len(li):,}"))
xs = open(os.path.join(HERE, "x_posts.md")).read().split("\n---\n")
blocks = []
for i, raw in enumerate(xs, 1):
    att = re.findall(r"\[attach: ([^\]]+)\]", raw)
    text = re.sub(r"\n*\[attach:[^\]]*\]\n*", "\n", raw).strip()
    media = f"attach <code>{html.escape(att[0])}</code>" if att else "no image"
    if att and att[0].endswith(".png"):
        data = base64.b64encode(open(os.path.join(HERE, att[0]), "rb").read()).decode()
        media += f'<img class="xmedia" alt="Cover image for the post" src="data:image/png;base64,{data}">'
    blocks.append(f'''<div class="xpost"><h3>{LABELS[i - 1] if i <= len(LABELS) else f"Post {i}"}</h3><pre>{html.escape(text)}</pre>
      <div class="row"><button type="button" class="xcopy">Copy post {i}</button><span>{media}</span>
      <span class="copied" aria-live="polite"></span></div></div>''')
page = page.replace("<!--X_POSTS-->", "\n".join(blocks)).replace("<!--X_COUNT-->", str(len(xs)))
out = os.path.join(HERE, "preview.html")
open(out, "w").write(page)
print(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
