# Copy this release into a fresh repository

This folder contains the artifact code, data, reference plots, and static
calculator. It excludes the paper PDF, LaTeX source, bibliography, and TeX
formatting files. It has no Git history. Copy its **contents** into the root of the
new repository, including the hidden `.gitignore` and `.nojekyll` files.
No repository URL is embedded in the website, so the repository name can change.

Before committing, verify the copied files from the repository root:

```sh
python3 tools/verify_fc27_artifact.py
```

Use Git or GitHub Desktop to commit and push the folder contents. The figure
PDFs are reference outputs of the analysis scripts, and remain included. Keep the compressed data files compressed.

## Preview locally

From the repository root:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open <http://127.0.0.1:8000/>. The root page opens `webapp/`; you can also
visit <http://127.0.0.1:8000/webapp/> directly. Stop the server with Ctrl+C.
Calculations and custom data remain in the browser.

## Enable GitHub Pages

After pushing the files, open the repository's **Settings → Pages**.
Choose **Deploy from a branch**, select your branch (usually `main`) and
**/(root)**, and save. GitHub shows the site URL when deployment is ready.
The root `index.html` opens the calculator; `.nojekyll` keeps the static files
from being processed as a Jekyll site.

See [GitHub's publishing-source instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

Creating this folder does not publish it or change the previous AFT repository.
The old repository and any previously published website remain separate until
you update them. Once a new repository is public, use its actual URL in the
paper's artifact statement.
