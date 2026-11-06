# Execution Boundaries (CRITICAL)
- NEVER EXECUTE SOURCE CODE (python, bash, node, script tasks) without explicit standalone user permission in the current turn. **Scrapers, tests, skill plugins (e.g. graphify), research and directory listing are permitted.**
- NEVER implement CLI/Command Line Arguments (`--input`, `--mode`). Hardcode configurations directly into variables for manual tweaking.

# Feature File Automation
- Use feature files to track feature context (important bugs fixed, design philosophies, etc.)
- Feature files and graphify are designed to co-exist; graphify describes *where* things exist and feature files should describe *why* things exist
- Track active progress in `feature_files/{feature_name}.md`. 
- If missing, auto-generate on task initialization.
- Feature files define a feature's ownership boundary. A feature owns only the logic, configuration, and behavior it directly implements.
    - Files, scripts, modules, or features that are merely called, launched, imported, orchestrated, or referenced are dependencies, not part of the feature itself.
    - Do not absorb dependency-specific details into a feature file simply because the feature interacts with them.
    - Cross-feature references should describe the interface or relationship, not duplicate the dependency's internal configuration.
- Mandatory schema: H1 Title, ## Summary (architecture/tech), ## Key Points (critical edge conditions/logic), ## Relevant Files (source code, tightly paired features), ## Dev Mode, ## State Log.
    - Format feature files like this example:
        Start of content """
        # Crypto Data Client

        ## Summary
        The `crypto` data client provides utilities for fetching market data (candles and trades) from Coinbase, primarily for BTC-USD. It is used for price discovery and historical analysis.

        ## Key Points
        - **Candle Fetching**: Implements automatic pagination to overcome Coinbase's 350-candle limit per request, allowing for arbitrary time ranges and granularities.
        - **Trade Fetching**: Uses backwards pagination to retrieve all individual market trades starting from a specific timestamp.
        - **Timezone Alignment**: Integrates with `time_format` to align Coinbase UTC data with ET, ensuring consistency with other venue data.

        ## Relevant Files
        - `src/tooling/data_clients/crypto.py`: Logic for fetching candles and trades from Coinbase.

        ## Dev Mode
        TESTING

        ## State Log
        - 2026-06-07: Initialized feature file for the crypto data client.
        """ End of content
- YOU must append a 1-sentence engineering log to the State Log before marking tasks complete.
- When debugging, use the relevant feature files as another tool to reduce lookups because the summaries and key points can give you a good macro-understanding without reading thousands of lines

# Topics (when tagged)
- Optional `topic_files/{slug}.md` umbrellas group closely related tasks with shared memory (Topic Goal, Topic Status, State Log).
- When a topic is embedded in the prompt, follow those instructions: Topic Goal is immutable unless the user explicitly asks to change it; Topic Status stays `open` or `complete`; append one concise topic-scoped State Log entry after completing a coding task.
- Concurrent State Log appends on the same topic can race like concurrent feature-file edits.

# Parameter File Centralization
Each feature file must have a corresponding parameter file (`.toml`) located in a sibling directory named `parameter_files`. Create the `parameter_files` directory if it does not already exist.

Parameter files are used to centralize feature-level configuration values that may need to be tuned, experimented with, or adjusted without modifying source code. Features should load these values from their parameter file rather than defining them directly in the implementation.

Parameter files act as a read-only source of truth during execution. Source code may read and use parameter values, but must not modify parameter files or persist runtime state back to them.

A parameter belongs in the parameter file of the feature that owns the behavior being configured, not necessarily the feature that references, imports, starts, or coordinates that behavior.

Good candidates for parameter files include:
- Thresholds and limits
- Feature toggles
- Strategy settings
- Allocation percentages
- Model architecture settings
- Hyperparameters
- Simulation or experiment settings
- External configuration values

Parameter ownership rules:
- Keep parameters with the feature responsible for interpreting and acting on them.
- Orchestration features may store references to other features (enabled scripts, connection targets, registered modules, etc.).
- Orchestration features must not store the internal settings of the features they launch.
- If removing a referenced feature would make a parameter meaningless, that parameter likely belongs to the referenced feature instead.
- Avoid nested per-feature configuration blocks that recreate another feature's parameter file inside the current feature.

Example:
- A command daemon may store a list of approved scripts it is allowed to launch.
- The daemon should not store each script's tuning values, execution settings, model parameters, thresholds, or feature-specific behavior settings. Those belong to each script's own parameter file.

Do not move every constant into a parameter file. Constants that are purely implementation details, fixed mathematical values, formatting values, or values unlikely to ever require tuning should remain in the source code.

Parameter files may be empty. A parameter file should always be created for consistency, but unnecessary parameters should not be added simply to populate the file.

Prefer a minimal parameter file containing only meaningful configuration over a large file filled with implementation constants.

Example:
```toml
MIN_KALSHI_BALANCE = 20.0

# Simulated backtest latency used to approximate real-world execution conditions
simulated_network_latency = 150
```

Here is an example of what *NOT* to do:
```toml
[script_metadata."src/mission1.py"]
friendly_name = "Takeoff and Land"
restart_policy = "never"
log_rate_limit_hz = 2.0
```

This is not good because if adding the parameters requires sectioning off per file like this using the form: `[subsection]`, then that subsection is probably better allocated to a smaller feature file. Remember this: **Many uncluttured feature and parameter files over a few cluttured and crammed feature and parameter files**.

As a last note, because parameter files are public files shared with Supabase and sometimes GitHub: ***DO NOT PUT API KEYS IN PARAMETER FILES. THIS WOULD BE A TERRIBLE SECURITY ISSUE***

# 4-Stage Development Lifecycle
Adhere strictly to the execution style mandated by the active feature file's Dev Mode. Prefix your very first response with `> Active Mode: [Stage]`.

1. HACKING: Prototype phase. Omit error-handling, validation boundaries, typing setups, and algorithmic optimization. Maximize readability; write logic a high school CS student can completely parse line-by-line.
2. TESTING: Incremental hardening. Introduce structured unit tests, catch-blocks, and condition validations.
3. PRODUCTION-READY: Enterprise optimization. Implement full validation layers, robust documentation strings, edge-case coverage, and clean structural syntax (dataclasses, slots, performance optimizations).
4. DEBUGGING: Deep diagnostics. Strip defensive abstractions. Maximize structured event logging, granular print statements, and cross-feature execution tracking.

# Alignment
- Do not autonomously upgrade a feature's stage. Log changes in the feature file only after alignment.

# Debugging
- When debugging code, every suspected root cause should include supporting evidence: the file path, relevant line numbers, and function names. Do not present a debugging hypothesis without citing the code that led to it.
