# Slides

Presentation slides for the code review evaluation project, built with
[Slidev](https://sli.dev). Slides are written in Markdown in `slides.md` and
run in a web browser.

## Run

Requires Node.js 22.12 or later.

```sh
cd slides
npm install
npm run dev
```

`npm run dev` opens the slides at <http://localhost:3030>. Edits to
`slides.md` reload automatically.

| URL | View |
|---|---|
| <http://localhost:3030> | Slide show |
| <http://localhost:3030/presenter/> | Presenter mode, with speaker notes and a timer |
| <http://localhost:3030/overview/> | Overview of all slides |

In the slide show, use the arrow keys to move between slides. Press `f` for
full screen.

## Build and export

- `npm run build` writes a static site to `dist/`, which you can host on any
  web server.
- `npm run export` writes a PDF. It needs a headless browser; install one with
  `npm install -D playwright-chromium` first.
