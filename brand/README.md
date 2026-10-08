# brand/

Source of truth for the TradeLogger logo and every icon/preview image.

- `build_brand_assets.py`: regenerates **all** brand PNG/ICO/SVG files across
  `frontend/public`, `desktop/build` and `mobile/assets` from one definition of
  the mark. Run `python brand/build_brand_assets.py` (needs Pillow only).
- `logo-*.svg`: vector masters (written by the script, so don't hand-edit them).
- `fonts/`: Geist and Geist Mono (SIL Open Font License 1.1, see `fonts/OFL.txt`),
  used only to render the wordmark and link-preview image.

Rules, meaning and the full asset inventory: [docs/BRAND.md](../docs/BRAND.md).
