# NFL test fixtures

Sanitized ESPN payloads for the offline checks (`scripts/check_nfl.py`). ESPN data is used for testing only.
`scripts/nfl/make_fixture.py` builds them from raw captures kept outside the repo: it drops market data, news, media
and link data and every URL string, then fails if any denied term is left. Game data is kept as captured.
Regenerate with `make_fixture.py build --captures DIR` (see its docstring).

## Historical summaries (captured 2026-11-15)

| Fixture | Source event | Edge state |
| --- | --- | --- |
| `summary_ot_final_2025w2_nyg_dal` | 401772834, 2025-09-14, DAL 40 NYG 37 | Final after overtime; full drives and win probability |
| `summary_tie_final_2025w4_gb_dal` | 401772921, 2025-09-28, DAL 40 GB 40 | Final tie, equal scores |
| `summary_superbowl_lx` | 401772988, 2026-02-08, SEA 29 NE 13 | Neutral-site final, Super Bowl |
| `summary_probowl_2025` | 401831718, 2026-02-04, NFC 66 AFC 52 | Pro Bowl: AFC/NFC pseudo-teams, no drives |
| `summary_live_end_period_min_gb` | 401873060, 2026-11-15, MIN at GB, end of Q3 | Live summary at a quarter break; current drive opened by a kickoff with a placeholder start spot of 0 and no plays |
| `summary_live_two_minute_hou_cle` | 401873056, 2026-11-15, HOU at CLE, Q4 2:00 | Two-minute warning as the newest play (admin row carrying the real pending down) |
| `summary_final_fresh_hou_cle` | 401873056, 2026-11-15, CLE 27 HOU 24 | Summary captured at the switch to final; End of Game is the last play |
| `sb_live_end_period_w10` | 401873060, 2026-11-15 20:22Z | Scoreboard with STATUS_END_PERIOD (End of Q3) and the situation still present |

## Scoreboards

| Fixture | Source | Edge state |
| --- | --- | --- |
| `sb_2025_w1` | 2025 week 1 | Neutral Sao Paulo game, venue id 8748 (unknown to a venue table) |
| `sb_2025_w2`, `sb_2025_w4` | 2025 weeks 2, 4 | Ordinary finals; W4 has the Dublin neutral game |
| `sb_2025_post_w1`, `sb_2025_post_w2`, `sb_2025_post_w3`, `sb_2025_post_w4`, `sb_2025_post_w5` | 2025 postseason 1-5 | Wild Card (6), Divisional (4), Conference (2), Pro Bowl (1), Super Bowl LX (1) |
| `sb_2026_w10` | 2026 week 10 | 14 games, 4 teams on bye, Munich neutral game; 7 live, 2 final, 5 scheduled when captured |
| `sb_2026_w11` | 2026 week 11 | 13 games, 6 teams on bye, Mexico City neutral game |
| `sb_2026_w12` | 2026 week 12 | Thanksgiving Thursday plus the Wednesday evening game (2026-11-26T01Z) |
| `sb_2026_w16` | 2026 week 16 | Christmas games, 4 flex placeholders ("Flex Game: 12/26 or 12/27") |
| `sb_2026_w18` | 2026 week 18 | All 16 games flex placeholders (`isTBDFlex`) |
| `sb_2026_post_w1` | 2026 Wild Card | 6 placeholder games, both teams `TBD` |
| `sb_bare` | scoreboard with no params | `leagues[0].calendar`, current week |
| `teams` | teams list | 32 teams |

## Live capture, Sunday 2026-11-15 (week 10, late-window games)

| Fixture | What it shows |
| --- | --- |
| `live_sb_w10_mid` | Scoreboard at 19:59:36Z: 7 games in progress, two with `situation.down = -1` and no down text (401873055, 401873056) |
| `live_summary_early`, `live_summary_late` | KC at ATL (401873058) summary at 19:55:36Z and 20:01:06Z, 3rd quarter |
| `live_core_plays_early`, `live_core_plays_late` | Matching core plays pages (113 and later more items), for lag comparisons with the summary |
| `live_trigger_401873054_fg_good` | BUF at NYJ, 10:16 3rd; current drive ends on a 4th-down incompletion, down -1 sentinel tripped the capture |
| `live_trigger_401873054_timeout` | Same game, 10:02 3rd; Field Goal Good then Official Timeout, down -1 end state |
| `live_trigger_401873055_rush_td` | CAR at NO, 6:33 3rd; Rushing Touchdown, end down -1, extra point pending |
| `live_trigger_401873056_timeout` | HOU at CLE, 8:35 3rd; Official Timeout after a touchdown |
| `live_trigger_401873057_fg_good` | JAX at TEN, 12:35 3rd; 54-yard Field Goal Good, down -1 |
| `live_trigger_401873060_timeout` | MIN at GB, 10:02 3rd; Official Timeout after a field goal |

`gameInfo.weather` is kept on purpose: the board ignores it and the checks assert that.

## Not covered yet

- In-progress overtime (period 5+), halftime, end of period, two-minute warning, status changes to final
- Delayed, postponed, suspended or canceled games; flex time moved from a placeholder to a real kickoff
- A live game without `situation`, a pregame summary, a live neutral-site game
- SNF and MNF captures (add to the manifest, build with `--only`)
