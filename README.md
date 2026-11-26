# NBA Prediction App

Historical NBA data builder for seasons 2010–11 through 2026–27.

Run `pip install duckdb pandas pyarrow` and `python build_dataset.py` to create player, season, game and team datasets and a SQLite database. The 2026–27 season is incomplete.

A player qualifies if they played at least 30 games in any season through 2025–26, or at least one game in 2026–27. Retain all seasons for qualified players; deduplicate by NBA player ID.

The full historical dataset has **not yet been downloaded or audited**. The builder depends on external data access and source licensing review. Advanced impact statistics may need separate sources.

Source: https://github.com/llimllib/nba_data
