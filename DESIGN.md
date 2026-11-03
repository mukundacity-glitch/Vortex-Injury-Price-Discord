# FPL VORTEX broadcast graphics

The approved blue master, original logos and social footer remain the source of truth. The supplied second reference defines the player layout: large proportional portraits, current club crests, compact five-row player tables, one advanced-statistics table, and a final verdict strip.

All table cells and headers use opaque light yellow `#FFEFA8` and black ink `#0C1014`; gold `#F7CD54` and cyan `#39DEF8` remain frame accents. Never copy the example players, club assignments, shirt colors, numbers or ranking claims from a reference image.

`src/comparison_board.py` is kept byte-identical to `Telegram-Bot/vortex/comparison_board.py`. It only draws supplied verified facts. The adapters own player identity, official current club joins and availability. No stretching portraits, substituted headshots, repeated numerical stats, invented missing values or unsourced best-pick labels.

Schedules, captions, data calculations and delivery deduplication are independent of this visual-only change. New art is used on the next eligible scheduled post; code releases do not trigger extra publication.
