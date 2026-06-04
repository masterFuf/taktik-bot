# Diagrammes de séquence

Cette page regroupe les séquences qui expliquent les grands flux du bot. Les diagrammes sont volontairement orientés architecture: ils montrent qui appelle qui, et où passent la config, les événements, le device et la base.

## Session Instagram classique

```mermaid
sequenceDiagram
    participant UI as Electron UI
    participant H as Handler bot.ts
    participant B as desktop_bridge
    participant C as Common services
    participant Compat as compat/clone
    participant A as InstagramAutomation
    participant R as WorkflowRunner
    participant W as Business workflow
    participant D as Android
    participant DB as SQLite

    UI->>H: start bot(config)
    H->>B: spawn bridge + config
    B->>C: setup_environment()
    B->>C: connect device
    C->>D: uiautomator2 connect
    B->>C: restart/open Instagram
    B->>Compat: version overrides + clone patch
    B->>A: InstagramAutomation(config)
    A->>R: run_workflow()
    loop chaque action config
        R->>W: run workflow step
        W->>D: navigation/detection/click/scroll
        W->>DB: save profiles/interactions/stats
        W-->>B: IPC stats/log/action
        B-->>H: stdout JSON
        H-->>UI: live updates
    end
```

## Interaction avec un profil

```mermaid
sequenceDiagram
    participant W as Workflow business
    participant F as FilteringBusiness
    participant P as ProfileBusiness
    participant L as LikeBusiness
    participant C as CommentBusiness
    participant S as StoryBusiness
    participant A as Atomic actions
    participant DB as SQLite
    participant IPC as IPCEmitter

    W->>A: navigate_to_profile(username)
    W->>P: extract profile data
    P-->>W: profile_data
    W->>F: filter(profile_data, criteria)
    alt profil refusé
        F-->>W: reject(reason)
        W->>DB: record filtered/skipped
    else profil accepté
        W->>L: like posts if configured
        L->>A: open post + like
        W->>C: comment if configured
        C->>A: open comment + type + post
        W->>S: watch/like stories if configured
        S->>A: story navigation
        W->>DB: record interactions
        W->>IPC: emit action events
    end
```

## Scraping Instagram

```mermaid
sequenceDiagram
    participant UI as Electron UI
    participant B as scraping_bridge
    participant W as ScrapingWorkflow
    participant List as list_scraping.py
    participant Profile as ProfileBusiness
    participant AI as AIService
    participant DB as SQLite

    UI->>B: scraping config
    B->>W: run(config)
    W->>DB: create scraping session
    W->>List: scrape target/hashtag/post
    loop usernames visibles
        List->>Profile: extract/enrich profile
        opt qualification IA
            Profile->>AI: classify/analyze
        end
        Profile->>DB: upsert profile
        List-->>B: profile_captured
        B-->>UI: stdout JSON
    end
    W->>DB: complete session
    B-->>UI: final result
```

## TikTok For You / Search

```mermaid
sequenceDiagram
    participant UI as Electron UI
    participant B as TikTok bridge
    participant W as ForYou/Search workflow
    participant Base as BaseVideoWorkflow
    participant Actions as TikTok atomic actions
    participant D as TikTok app
    participant IPC as stdout JSON

    UI->>B: config probabilities/limits
    B->>W: run(config)
    loop vidéos
        W->>Actions: get_video_info()
        W->>Base: _handle_stuck_video()
        W->>Base: _decide_and_execute_actions()
        Base->>Actions: like/follow/favorite
        W->>Actions: scroll_to_next_video()
        W->>Base: _check_pause_needed()
        W-->>IPC: stats/action/pause
    end
    B-->>UI: completed
```

## YouTube upload

```mermaid
sequenceDiagram
    participant UI as Electron UI
    participant B as youtube_upload_bridge
    participant WF as YouTubeUploadWorkflow
    participant Media as media_store
    participant Perm as PermissionHandler
    participant KB as Taktik Keyboard
    participant YT as YouTube app

    UI->>B: upload config
    B->>WF: set_callbacks(log,status)
    B->>WF: execute(local_path,title,description,type,visibility)
    WF->>Media: push_and_scan()
    WF->>YT: restart app
    WF->>Perm: grant/deny permissions
    WF->>YT: create + gallery + first item
    WF->>YT: next until details
    WF->>KB: type title/description
    WF->>YT: set visibility
    WF->>YT: upload/post
    WF-->>B: success/message
```

## Gmail OTP

```mermaid
sequenceDiagram
    participant B as gmail_account_bridge
    participant G as GmailWorkflow
    participant Gmail as Gmail app
    participant GMS as Google Play Services

    B->>G: ensure_account_added(email,password)
    G->>Gmail: open Gmail
    G->>Gmail: account switcher
    alt compte absent
        G->>GMS: Google Sign-In WebView
        G->>GMS: email/password/terms
    end
    B->>G: get_latest_verification_code(email)
    G->>Gmail: switch account
    loop jusqu'au timeout
        G->>Gmail: read inbox dump
        alt code trouvé
            G-->>B: code
        else
            G->>Gmail: search/open first result
        end
    end
```

## Versioned selectors + clones

```mermaid
sequenceDiagram
    participant B as Bridge
    participant App as AppService
    participant Compat as compat.setup
    participant Clone as clone.selector_patcher
    participant S as Selector singletons
    participant W as Workflow

    B->>App: get installed version
    App-->>B: versionName
    B->>Compat: apply_version_overrides(app, version)
    Compat->>S: patch fields from YAML
    alt packageName clone
        B->>Clone: patch_selectors_for_package(app, packageName)
        Clone->>S: rewrite package prefixes
    end
    B->>W: run workflow
    W->>S: use patched selectors
```

## Workflow compat test

```mermaid
sequenceDiagram
    participant UI as Debug Panel
    participant B as workflow_test_bridge
    participant T as SelectorTracer
    participant W as Real workflow
    participant R as Report

    UI->>B: test config
    B->>B: connect + apply overrides + language detect
    B->>T: attach(device_facade)
    B->>W: run real workflow
    W->>T: traced xpath calls
    B->>T: detach()
    B->>R: report()
    B-->>UI: test_report
```
