# Autopilot — hands-off content channels

Autopilot turns MoneyPrinterTurbo from a "click to generate one video" tool
into a **passive content machine**: you describe a channel once (niche,
language, cadence, style), and a background scheduler keeps producing fresh
videos for it — and, with Upload-Post enabled, publishing them to
TikTok/Instagram — with no human in the loop.

## How it works

```
┌────────────┐   every tick    ┌──────────────┐   fresh topic   ┌──────────────┐
│  Channel   │ ──────────────▶ │  Autopilot   │ ──────────────▶ │     LLM      │
│ definition │                 │  scheduler   │ ◀────────────── │ (your provider)│
└────────────┘                 └──────┬───────┘                 └──────────────┘
                                      │ VideoParams
                                      ▼
                               ┌──────────────┐    auto-upload   ┌──────────────┐
                               │ Task manager │ ───────────────▶ │ TikTok / IG  │
                               │ (existing    │   (Upload-Post)  │              │
                               │  pipeline)   │                  └──────────────┘
                               └──────────────┘
```

1. A channel stores a **niche** (e.g. `"stoic philosophy motivation"`), a
   **cadence** (`interval_hours`) and optional `VideoParams` overrides
   (voice, aspect ratio, subtitles, BGM…).
2. On every due run the scheduler asks your configured LLM for **one fresh
   topic** in that niche, steering it away from the last 20 topics the
   channel already covered.
3. The topic is submitted to the regular video pipeline (same task manager,
   same concurrency limits as manual API requests).
4. If `upload_post_auto_upload = true`, the finished video is cross-posted
   automatically.

Channels are persisted in `storage/autopilot/channels.json`, so schedules
survive restarts.

## Install from the published image

The app is published to GitHub Container Registry on every release:

```bash
docker pull ghcr.io/wirtualnybiznes/moneyprinterturbo:autopilot
docker run -v $(pwd)/config.toml:/MoneyPrinterTurbo/config.toml \
           -v $(pwd)/storage:/MoneyPrinterTurbo/storage \
           -p 8080:8080 \
           ghcr.io/wirtualnybiznes/moneyprinterturbo:autopilot \
           python main.py
```

## Setup

1. Configure your LLM provider and Pexels/Pixabay keys in `config.toml`
   (as for normal usage).
2. Enable the scheduler:

   ```toml
   [app]
   autopilot_enabled = true
   ```

3. (Optional, for fully hands-off publishing) configure Upload-Post:

   ```toml
   upload_post_enabled = true
   upload_post_api_key = "..."
   upload_post_username = "..."
   upload_post_platforms = ["tiktok", "instagram"]
   upload_post_auto_upload = true
   ```

4. Start the API server: `python main.py`

## API

All endpoints live under `/api/v1/autopilot`.

### Create a channel

```bash
curl -X POST http://localhost:8080/api/v1/autopilot/channels \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Stoic Wisdom Daily",
    "niche": "stoic philosophy motivation for young professionals",
    "language": "en",
    "interval_hours": 12,
    "videos_per_run": 1,
    "video_params": {
      "video_aspect": "9:16",
      "voice_name": "en-US-GuyNeural-Male",
      "subtitle_enabled": true,
      "bgm_type": "random"
    }
  }'
```

A newly created (enabled) channel produces its first video on the next
scheduler tick (≤30 s), then every `interval_hours`.

### Manage channels

| Method & path                                | Purpose                          |
| -------------------------------------------- | -------------------------------- |
| `GET /autopilot/channels`                     | List channels                    |
| `GET /autopilot/channels/{id}`                | Channel detail (incl. history)   |
| `PUT /autopilot/channels/{id}`                | Update niche/cadence/params      |
| `DELETE /autopilot/channels/{id}`             | Delete channel                   |
| `POST /autopilot/channels/{id}/run`           | Produce a video right now        |
| `GET /autopilot/status`                       | Scheduler status & totals        |
| `POST /autopilot/start` / `POST /autopilot/stop` | Control the scheduler         |

Each channel tracks `last_task_ids` (last 10 generated tasks — query them
via the regular `GET /tasks/{task_id}`), `recent_topics` and
`total_videos`.

## Tips for good channels

- **Be specific in the niche**: "5-second psychology facts that explain
  everyday behavior" beats "psychology".
- **One niche per channel.** Algorithms reward consistency.
- **Set `interval_hours` to 8–24.** 1–3 posts/day is the sweet spot for
  short-form growth; more looks like spam.
- **Pin the voice and style** in `video_params` so the channel feels
  coherent.
- Review platform Terms of Service for automated posting and AI-generated
  content disclosure rules in your jurisdiction — you are responsible for
  what your channels publish.
