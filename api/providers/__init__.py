# -*- coding: utf-8 -*-
"""Real macro data providers (Phase 65).

Each provider fetches authoritative economic data, normalizes it to the
canonical `macro_intelligence_engine.MacroReleaseRecord`, and registers it into
`EconomicDataRegistry` — the same lookahead-gated store the seed dataset uses.
The scoring / intelligence layer is unchanged and never knows which vendor
supplied the data.
"""
