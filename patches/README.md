# Modular SBEC3 development

Scope: naturally aspirated 128 KB images 04887050 and 05293013AC. The stock source, diagnostic, synchronization and hardware event scheduler remain the reference. No hardware validation or ROM export from this experimental profile.

- `dinofuel/`: V1 retained, V2 Q11 selected.
- `spark/`: base spark lookup experiment; preserve stock angle exactly before considering a wider-angle ABI.
- `common/`: shared resource validation.
- `../profiles/modules.json`: profile dependencies and reserved resources; all ranges half-open, end excluded.
- Later modules: fuel corrections, knock, idle, lambda. Add each only when its interfaces and resource budget are understood.

Every module must declare exact supported ROM hashes, hook signatures, flash and persistent RAM, scratch ownership and calling convention; validate isolated and combined behaviour against the original; maintain separate XDFs when calibration formats differ. Checksums are computed on the composed image. Keep stock builds byte-identical. Never infer physical timing or safe calibration from a simulator alone.

The current manifest is a conservative reservation map, not a general-purpose linker. `common/resource_check.py` checks declared conflicts, dependency and erased-area constraints; the spark simulator exercises composition with the existing fuel generator. The existing V2 and its fork are unchanged.
