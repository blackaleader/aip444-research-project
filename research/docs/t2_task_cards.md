# T2 proposed task cards

Version: t2_context_v1. Human relevance review and main inclusion are pending.
These behavior-focused cards disclose no solution paths or commit identifiers.
The frozen pilot keeps its original prompts. Evaluator annotations are stored separately.

## pi_lazy_extension_loading

Importing the coding-agent SDK should not initialize the extension compiler or bundled extension-only modules before a filesystem extension is actually loaded. Preserve filesystem-extension loading in ordinary Node, source TypeScript, Bun-compiled binaries, Node SEA binaries, and the bundled Node distribution. Existing extension module resolution and caching behaviour must continue to work. Find the pre-existing repository context needed to make this change; return ranked code evidence and do not implement a patch.

## pi_package_filtering

Users need a dedicated packages setting for npm and Git package sources, separate from local extension, skill, prompt and theme paths. Accept a plain package source or an object that selects resources by type. An omitted resource selection keeps that type's normal package discovery; an empty selection loads none of that type. Preserve existing package sources by migrating them from the old extension configuration, retain local extension paths, and ensure package install, remove and list commands use the new configuration in the appropriate scope. Find the pre-existing repository context needed to make this change; return ranked code evidence and do not implement a patch.

## pi_package_progress_conflicts

Package install, remove and update operations need observable start, completion and error feedback, with useful feedback in the CLI. Package sources should also accept common Git-host URLs without requiring a special prefix. When different loaded extensions register the same tool, command or flag name, report the conflict with the responsible extension paths. Preserve existing source handling. Find the pre-existing repository context needed to make these changes; return ranked code evidence and do not implement a patch.

## pi_package_dedup_collisions

The same package may be configured globally and in a project. Resolve each package identity once, with the project configuration taking precedence, while preserving resource filtering. Report collisions among named skills, prompts and themes with the retained and discarded resource paths. Startup and reload resource listings should make package origin and scope understandable. Preserve local resource discovery, including configured extension directories. Find the pre-existing repository context needed for this behaviour; return ranked code evidence and do not implement a patch.

## pi_network_retry

A provider response can fail with the message 'Network connection lost.' and the current session stops instead of recovering. Treat this transient failure consistently with existing automatic retries. Preserve retry-disable and retry-limit settings, recovery events, and the separate handling of context overflow. Find the pre-existing repository context needed to fix this behaviour; return ranked code evidence and do not implement a patch.

## pi_rpc_context_statistics

An RPC client requesting session statistics needs current context usage alongside cumulative token and cost totals. Include the available context token count, model context window and percentage. Immediately after compaction, do not present stale pre-compaction usage as the current value; preserve the existing representation for unknown usage until a fresh response is available. Find the pre-existing repository context needed to expose this information consistently; return ranked code evidence and do not implement a patch.

## pi_session_directory_config

Allow a session storage directory to be configured through an application-named environment variable independently of the agent configuration directory. An explicit --session-dir option must take precedence, followed by the environment setting and then the existing settings/default behaviour. Support home-directory shorthand and make the CLI help distinguish agent configuration storage from session storage. Preserve existing session selection behaviour. Find the pre-existing repository context needed to implement this feature; return ranked code evidence and do not implement a patch.

## pi_cli_mode_validation

The --mode option should accept only text, json and rpc. Report invalid or missing values as argument errors instead of silently ignoring them or treating them as normal messages. When another option follows --mode, preserve that option for normal parsing. Valid values and repeated options must continue to work, while any invalid occurrence still produces a diagnostic. Find the pre-existing repository context needed to fix this behaviour; return ranked code evidence and do not implement a patch.
