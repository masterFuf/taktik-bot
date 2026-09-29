# Instagram workflows

One folder per feature, named with the vocabulary the platforms and their bridges share (the tree gate,
`scripts/audits/audit_tree_layout.py`, holds the list). Each feature keeps its launcher, `agent_handler.py`:
the `run_*` function a bridge and the CLI both call, and the handlers the workflow registry resolves by id.

```text
workflows/
  automation/      the automation of a run (targets, hashtags, post URL, feed, unfollow, syncs):
                   its launcher, InstagramAutomation, the step runner, its config
                   (config.py, config_builder.py, workflow_defaults.py) and its workflows,
                   one folder each (feed/, followers/, hashtag/, messaging/, post_url/,
                   profile_list/, unfollow/)
  account/         log in, log out, sign up, switch account, change the app language
  agent/           the Taktik Agent session (autopilot.py)
  cold_dm/         the cold DM
  dm/              the DM inbox: read it, read its requests, reply
  notifications/   the notifications pass
  publish/         a publication (post, reel, carousel, story)
  scraping/        the scraping of lists, hashtags, post URLs and profile posts
  tasks/           the one-shots with no target list (story relay)
  ads/             reading the ads a feed run collected, out of any run
  common/          what the workflows share: the start of Instagram (startup.py), the
                   selectors matched to the phone (runtime_setup.py), the Instagram device
                   base (device.py), the AI hooks, the session of a run (session/: its limits,
                   its stop reasons, its warmup budget), the helpers of the workflows
```

A workflow composes the actions of `../actions/` (gestures and readings) and the services of `../services/`;
an action never imports a workflow (rule `actions-no-workflows` of `scripts/audits/audit_import_layers.py`).
